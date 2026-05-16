from time import time

import pytest

from app.connectors.etherscan import EtherscanClient
from app.connectors.goplus import GoPlusClient
from app.domain.graph_builder import GraphBuilder
from app.domain.models import (
    GraphEdge,
    GraphNode,
    InvestigationGraph,
    InvestigationMode,
    RiskLevel,
    ScreeningTransactionCreate,
    WatchlistEntry,
)
from app.domain.patterns import PatternAnalyzer
from app.domain.risk_intel import RiskIntelAggregator
from app.domain.scoring import RiskScoringEngine
from app.domain.validators import detect_target_type
from app.ml.raindrop_scorer import RaindropAmlScorer
from app.services.screening import ScreeningService
from app.storage.memory import InMemoryStore


def test_detect_target_type():
    assert detect_target_type("0x" + "a" * 40) == "address"
    assert detect_target_type("0x" + "b" * 64) == "transaction_hash"
    with pytest.raises(ValueError):
        detect_target_type("not-an-ethereum-target")


@pytest.mark.asyncio
async def test_demo_graph_and_risk_are_generated():
    etherscan = EtherscanClient(api_key="", base_url="", demo_mode=True)
    graph_builder = GraphBuilder(etherscan, max_stable_nodes=20, max_experimental_nodes=40)
    result = await graph_builder.build_from_address(
        "inv-1",
        "0x" + "a" * 40,
        chain_id="1",
        depth=2,
        mode=InvestigationMode.stable,
    )
    assert result.graph.nodes
    assert result.graph.edges

    scoring = RiskScoringEngine(RiskIntelAggregator(GoPlusClient(demo_mode=True)), RaindropAmlScorer())
    risk = await scoring.score_graph("inv-1", result.graph, chain_id="1", watchlist={})
    assert risk.final_risk_score >= 0
    assert risk.feature_summary["node_count"] == len(result.graph.nodes)


def test_pattern_analyzer_detects_aggregation_and_dusting():
    now = int(time())
    sink = "0x" + "1" * 40
    dust_source = "0x" + "2" * 40
    source_addresses = [f"0x{idx:040x}" for idx in range(10, 15)]
    dust_targets = [f"0x{idx:040x}" for idx in range(20, 26)]
    nodes = [
        GraphNode(id=sink, address=sink, label="sink", hop=0),
        GraphNode(id=dust_source, address=dust_source, label="dust", hop=1),
        *(GraphNode(id=address, address=address, label=address[:6], hop=1) for address in source_addresses),
        *(GraphNode(id=address, address=address, label=address[:6], hop=1) for address in dust_targets),
    ]
    edges = [
        GraphEdge(
            id=f"agg-{idx}",
            source=address,
            target=sink,
            tx_hash=f"0x{idx:064x}",
            timestamp=now - idx,
            value_eth=1.2,
            hop=1,
            direction="in",
        )
        for idx, address in enumerate(source_addresses, start=1)
    ]
    edges.extend(
        GraphEdge(
            id=f"dust-{idx}",
            source=dust_source,
            target=address,
            tx_hash=f"0x{idx + 100:064x}",
            timestamp=now - idx,
            value_eth=0.00001,
            hop=1,
            direction="out",
        )
        for idx, address in enumerate(dust_targets, start=1)
    )

    graph = InvestigationGraph(investigation_id="pattern-test", nodes=nodes, edges=edges)
    names = {signal.name for signal in PatternAnalyzer().analyze_graph(graph)}

    assert "aggregation" in names
    assert "dusting" in names


@pytest.mark.asyncio
async def test_screening_direct_source_hit_forces_manual_hold():
    store = InMemoryStore()
    risky = "0x" + "b" * 40
    store.upsert_watchlist_entry(
        WatchlistEntry(
            address=risky,
            label="OFAC SDN demo",
            category="ofac",
            severity=RiskLevel.critical,
            notes="Authoritative sanctions list demo hit.",
        )
    )
    etherscan = EtherscanClient(api_key="", base_url="", demo_mode=True)
    graph_builder = GraphBuilder(etherscan, max_stable_nodes=20, max_experimental_nodes=40)
    patterns = PatternAnalyzer()
    scoring = RiskScoringEngine(RiskIntelAggregator(GoPlusClient(demo_mode=True)), RaindropAmlScorer(), patterns)
    service = ScreeningService(store, graph_builder, scoring, patterns)

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="USDC",
            direction="outbound",
            from_address="0x" + "a" * 40,
            to_address=risky,
            amount=9500,
        )
    )

    assert response.disposition.value == "hold_for_manual_review"
    assert response.risk_level == RiskLevel.critical
    assert any(hit.direct_hit and hit.category == "ofac" for hit in response.source_hits)

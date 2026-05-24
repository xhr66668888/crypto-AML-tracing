from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.graph_builder import GraphBuilder
from app.domain.models import (
    GraphEdge,
    GraphNode,
    InvestigationGraph,
    InvestigationMode,
    RiskDisposition,
    RiskLevel,
    RiskResponse,
    RiskSourceHit,
    ScreeningTransactionCreate,
)
from app.domain.patterns import PatternAnalyzer
from app.services.screening import SCREENING_CONTEXT_DEPTH, ScreeningService
from app.storage.memory import InMemoryStore


FROM_ADDRESS = "0x" + "a1" * 20
TO_ADDRESS = "0x" + "b2" * 20
RISKY_ADDRESS = "0x" + "c3" * 20
PEER_ADDRESS = "0x" + "d4" * 20


@pytest.mark.asyncio
async def test_graph_builder_stable_context_uses_two_hops_and_six_transactions():
    etherscan = _ManyTxEtherscan()
    builder = GraphBuilder(etherscan, max_stable_nodes=40, max_experimental_nodes=80)  # type: ignore[arg-type]

    result = await builder.build_from_address(
        "light-context",
        FROM_ADDRESS,
        chain_id="1",
        depth=SCREENING_CONTEXT_DEPTH,
        mode=InvestigationMode.stable,
    )

    assert etherscan.offsets
    assert all(offset == 6 for offset in etherscan.offsets)
    assert max(node.hop for node in result.graph.nodes) <= 2
    assert max(edge.hop for edge in result.graph.edges) <= 2


@pytest.mark.asyncio
async def test_screening_context_graph_expands_counterparty_address_only():
    graph_builder = _RecordingGraphBuilder()
    service = ScreeningService(
        InMemoryStore(),
        graph_builder,  # type: ignore[arg-type]
        _LowRiskScoring(),
        PatternAnalyzer(),
    )

    await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="ETH",
            direction="outbound",
            counterparty_address=TO_ADDRESS,
            amount=1,
        )
    )

    assert graph_builder.calls == [
        (TO_ADDRESS, SCREENING_CONTEXT_DEPTH, None, "ETH", "screening_counterparty"),
    ]


@pytest.mark.asyncio
async def test_one_hop_risky_context_exposure_becomes_pattern_signal():
    service = ScreeningService(
        InMemoryStore(),
        _RiskExposureGraphBuilder(),  # type: ignore[arg-type]
        _RiskExposureScoring(),
        PatternAnalyzer(),
    )

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="ETH",
            direction="outbound",
            counterparty_address=FROM_ADDRESS,
            amount=1,
        )
    )

    signal = next(signal for signal in response.pattern_signals if signal.name == "one_hop_risky_exposure")
    assert signal.subject == FROM_ADDRESS
    assert signal.metadata["risky_address"] == RISKY_ADDRESS
    assert signal.metadata["source_hit_evidence"] == "OFAC source hit for fixture risky address."
    assert "1-hop exposure" in signal.evidence
    assert any(item == signal.evidence for item in response.evidence_summary)
    assert response.source_hits == []
    assert response.disposition == RiskDisposition.review


@pytest.mark.asyncio
async def test_short_time_repeated_transfers_become_pattern_signal():
    service = ScreeningService(
        InMemoryStore(),
        _RepeatedTransferGraphBuilder(),  # type: ignore[arg-type]
        _LowRiskScoring(),
        PatternAnalyzer(),
    )

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="ETH",
            direction="outbound",
            counterparty_address=FROM_ADDRESS,
            amount=1,
        )
    )

    signal = next(signal for signal in response.pattern_signals if signal.name == "short_time_repeated_transfers")
    assert signal.subject == FROM_ADDRESS
    assert signal.metadata["transfer_count"] == 3
    assert "3 transfers" in signal.evidence


@pytest.mark.asyncio
async def test_direct_party_source_hit_still_forces_manual_hold():
    service = ScreeningService(
        InMemoryStore(),
        _RecordingGraphBuilder(),  # type: ignore[arg-type]
        _PartyDirectHitScoring(),
        PatternAnalyzer(),
    )

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="ETH",
            direction="outbound",
            counterparty_address=FROM_ADDRESS,
            amount=1,
        )
    )

    assert response.disposition == RiskDisposition.hold_for_manual_review
    assert len(response.source_hits) == 1
    assert response.source_hits[0].address == FROM_ADDRESS
    assert response.source_hits[0].direct_hit is True


class _ManyTxEtherscan:
    def __init__(self) -> None:
        self.offsets: list[int] = []

    async def get_transactions(self, address: str, page: int = 1, offset: int = 25, chain_id: str | None = None):
        self.offsets.append(offset)
        return [
            {
                "hash": f"0x{len(self.offsets):02x}{idx:062x}",
                "from": address,
                "to": f"0x{len(self.offsets):02x}{idx:038x}",
                "value_eth": 0.5,
                "timestamp": 1700000000 - idx,
                "block_number": str(19000000 + idx),
                "is_error": "0",
                "source": "fixture",
            }
            for idx in range(offset)
        ]


class _RecordingGraphBuilder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str | None, str | None, str]] = []

    async def build_from_address(
        self,
        investigation_id: str,
        root_address: str,
        chain_id: str,
        depth: int,
        mode,
        token_address: str | None = None,
        asset_symbol: str | None = None,
        root_source: str = "target",
    ):
        self.calls.append((root_address, depth, token_address, asset_symbol, root_source))
        graph = InvestigationGraph(
            investigation_id=investigation_id,
            nodes=[GraphNode(id=root_address, address=root_address, label="root", hop=0, source=root_source)],
            edges=[],
        )
        return SimpleNamespace(graph=graph)


class _RiskExposureGraphBuilder:
    async def build_from_address(
        self,
        investigation_id: str,
        root_address: str,
        chain_id: str,
        depth: int,
        mode,
        token_address: str | None = None,
        asset_symbol: str | None = None,
        root_source: str = "target",
    ):
        if root_address == FROM_ADDRESS:
            graph = InvestigationGraph(
                investigation_id=investigation_id,
                nodes=[
                    GraphNode(id=FROM_ADDRESS, address=FROM_ADDRESS, label="from", hop=0, source=root_source),
                    GraphNode(id=RISKY_ADDRESS, address=RISKY_ADDRESS, label="risky", hop=1),
                ],
                edges=[
                    GraphEdge(
                        id="risk-edge",
                        source=FROM_ADDRESS,
                        target=RISKY_ADDRESS,
                        tx_hash="0x" + "1" * 64,
                        timestamp=1700000000,
                        value_eth=1,
                        hop=1,
                        direction="out",
                        metadata={"source": "fixture", "asset_symbol": asset_symbol or "ETH"},
                    )
                ],
            )
        else:
            graph = InvestigationGraph(
                investigation_id=investigation_id,
                nodes=[GraphNode(id=root_address, address=root_address, label="to", hop=0, source=root_source)],
                edges=[],
            )
        return SimpleNamespace(graph=graph)


class _RepeatedTransferGraphBuilder:
    async def build_from_address(
        self,
        investigation_id: str,
        root_address: str,
        chain_id: str,
        depth: int,
        mode,
        token_address: str | None = None,
        asset_symbol: str | None = None,
        root_source: str = "target",
    ):
        edges = []
        if root_address == FROM_ADDRESS:
            edges = [
                GraphEdge(
                    id=f"repeat-{idx}",
                    source=FROM_ADDRESS,
                    target=PEER_ADDRESS,
                    tx_hash=f"0x{idx:064x}",
                    timestamp=1700000000 + idx * 600,
                    value_eth=0.5,
                    hop=1,
                    direction="out",
                    metadata={"source": "fixture", "asset_symbol": asset_symbol or "ETH"},
                )
                for idx in range(3)
            ]
        graph = InvestigationGraph(
            investigation_id=investigation_id,
            nodes=[
                GraphNode(id=root_address, address=root_address, label="root", hop=0, source=root_source),
                GraphNode(id=PEER_ADDRESS, address=PEER_ADDRESS, label="peer", hop=1),
            ],
            edges=edges,
        )
        return SimpleNamespace(graph=graph)


class _LowRiskScoring:
    async def score_graph(self, investigation_id: str, graph: InvestigationGraph, chain_id: str, watchlist: dict):
        return RiskResponse(
            investigation_id=investigation_id,
            rule_score=0,
            raindrop_score=0,
            final_risk_score=0,
            final_risk_level=RiskLevel.low,
            findings=[],
            top_risk_paths=[],
            feature_summary={},
            pattern_signals=[],
            source_hits=[],
        )


class _RiskExposureScoring:
    async def score_graph(self, investigation_id: str, graph: InvestigationGraph, chain_id: str, watchlist: dict):
        for node in graph.nodes:
            if node.address == RISKY_ADDRESS:
                node.risk_score = 95
                node.risk_level = RiskLevel.critical
        hit = RiskSourceHit(
            source="ofac_sdn",
            category="ofac",
            severity=RiskLevel.critical,
            address=RISKY_ADDRESS,
            label="OFAC SDN",
            evidence="OFAC source hit for fixture risky address.",
            direct_hit=True,
        )
        return RiskResponse(
            investigation_id=investigation_id,
            rule_score=95,
            raindrop_score=0,
            final_risk_score=95,
            final_risk_level=RiskLevel.critical,
            findings=[],
            top_risk_paths=[],
            feature_summary={},
            pattern_signals=[],
            source_hits=[hit],
        )


class _PartyDirectHitScoring:
    async def score_graph(self, investigation_id: str, graph: InvestigationGraph, chain_id: str, watchlist: dict):
        hit = RiskSourceHit(
            source="ofac_sdn",
            category="ofac",
            severity=RiskLevel.critical,
            address=FROM_ADDRESS,
            label="OFAC SDN",
            evidence="OFAC source hit for fixture sender address.",
            direct_hit=True,
        )
        return RiskResponse(
            investigation_id=investigation_id,
            rule_score=95,
            raindrop_score=0,
            final_risk_score=95,
            final_risk_level=RiskLevel.critical,
            findings=[],
            top_risk_paths=[],
            feature_summary={},
            pattern_signals=[],
            source_hits=[hit],
        )

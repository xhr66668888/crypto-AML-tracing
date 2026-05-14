import pytest

from app.connectors.etherscan import EtherscanClient
from app.connectors.goplus import GoPlusClient
from app.domain.graph_builder import GraphBuilder
from app.domain.models import InvestigationMode
from app.domain.risk_intel import RiskIntelAggregator
from app.domain.scoring import RiskScoringEngine
from app.domain.validators import detect_target_type
from app.ml.raindrop_aml import RaindropAmlScorer


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

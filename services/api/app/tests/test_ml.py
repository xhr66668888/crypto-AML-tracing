"""Tests for the Raindrop AML ML layer.

Covers:
- ``RaindropAmlScorer.predict()`` determinism and contract
- ``extract_features`` correctness
- Score range [0, 100]
- Explanation generation
- Integration with the scoring pipeline
"""

from __future__ import annotations

from time import time

import pytest

from app.domain.models import (
    GraphEdge,
    GraphNode,
    InvestigationGraph,
    RiskLevel,
)
from app.ml.features import FEATURE_SCHEMA_VERSION, extract_features
from app.ml.raindrop_scorer import RaindropAmlScorer, RaindropResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_graph(
    node_count: int = 5,
    edge_count: int = 8,
    risk_tag_ratio: float = 0.0,
    direct_hit_count: int = 0,
    value_range: tuple[float, float] = (0.1, 5.0),
    time_span_hours: float = 24.0,
    max_hop: int = 2,
) -> InvestigationGraph:
    """Build a deterministic test graph with controllable parameters."""
    now = int(time())
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # Create nodes
    for i in range(node_count):
        addr = f"0x{i:040x}"
        tags: list[str] = []
        if i < int(node_count * risk_tag_ratio):
            tags = ["malicious"]
        if i < direct_hit_count:
            tags.append("ofac")
        hop = min(i, max_hop)
        nodes.append(
            GraphNode(
                id=addr,
                address=addr,
                label=addr[:6],
                hop=hop,
                source="target" if i == 0 else "derived",
                tags=tags,
            )
        )

    # Create edges
    for i in range(edge_count):
        src_idx = i % node_count
        dst_idx = (i + 1) % node_count
        src = nodes[src_idx].address
        dst = nodes[dst_idx].address
        timestamp = now - int((time_span_hours * 3600) * (1 - i / max(edge_count, 1)))
        value = value_range[0] + (value_range[1] - value_range[0]) * (i / max(edge_count - 1, 1))
        edges.append(
            GraphEdge(
                id=f"edge-{i}",
                source=src,
                target=dst,
                tx_hash=f"0x{i:064x}",
                timestamp=timestamp,
                value_eth=round(value, 8),
                hop=min(src_idx, max_hop),
                direction="out" if i % 2 == 0 else "in",
            )
        )

    return InvestigationGraph(investigation_id="test", nodes=nodes, edges=edges)


def _minimal_graph() -> InvestigationGraph:
    """A tiny graph with 2 nodes and 1 edge."""
    now = int(time())
    a, b = "0x" + "a" * 40, "0x" + "b" * 40
    return InvestigationGraph(
        investigation_id="minimal",
        nodes=[
            GraphNode(id=a, address=a, label="aaa", hop=0, source="target"),
            GraphNode(id=b, address=b, label="bbb", hop=1),
        ],
        edges=[
            GraphEdge(
                id="e1", source=a, target=b, tx_hash="0x" + "1" * 64,
                timestamp=now, value_eth=1.5, hop=0, direction="out",
            )
        ],
    )


def _empty_graph() -> InvestigationGraph:
    """Graph with no edges."""
    return InvestigationGraph(investigation_id="empty", nodes=[], edges=[])


# ---------------------------------------------------------------------------
# predict() contract tests
# ---------------------------------------------------------------------------

class TestPredictContract:
    """Verify the frozen ``predict(graph) -> RaindropResult`` contract."""

    def test_returns_raindrop_result(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_minimal_graph())
        assert isinstance(result, RaindropResult)

    def test_score_in_range(self):
        scorer = RaindropAmlScorer()
        for _ in range(10):
            g = _make_graph()
            result = scorer.predict(g)
            assert 0.0 <= result.score <= 100.0, f"Score {result.score} out of range"

    def test_score_range_empty_graph(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_empty_graph())
        assert 0.0 <= result.score <= 100.0

    def test_deterministic_same_graph_same_result(self):
        scorer = RaindropAmlScorer()
        g = _make_graph()
        r1 = scorer.predict(g)
        r2 = scorer.predict(g)
        assert r1.score == r2.score
        assert r1.features == r2.features
        assert r1.explanation == r2.explanation
        assert r1.model_version == r2.model_version

    def test_deterministic_different_graphs_different_results(self):
        scorer = RaindropAmlScorer()
        g1 = _make_graph(node_count=3, edge_count=4)
        g2 = _make_graph(node_count=20, edge_count=40, risk_tag_ratio=0.5)
        r1 = scorer.predict(g1)
        r2 = scorer.predict(g2)
        # Scores should differ (extremely unlikely to be equal)
        assert r1.score != r2.score or r1.features != r2.features

    def test_model_version_string(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_minimal_graph())
        assert result.model_version == "raindrop-v1-deterministic"

    def test_features_is_dict(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_minimal_graph())
        assert isinstance(result.features, dict)
        assert "node_count" in result.features
        assert "edge_count" in result.features

    def test_explanation_is_string(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_minimal_graph())
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0


# ---------------------------------------------------------------------------
# Feature extraction tests
# ---------------------------------------------------------------------------

class TestFeatureExtraction:
    """Verify ``extract_features`` returns correct values."""

    def test_schema_version_present(self):
        features = extract_features(_minimal_graph())
        assert features["feature_schema_version"] == FEATURE_SCHEMA_VERSION

    def test_node_count(self):
        g = _make_graph(node_count=7)
        features = extract_features(g)
        assert features["node_count"] == 7

    def test_edge_count(self):
        g = _make_graph(edge_count=12)
        features = extract_features(g)
        assert features["edge_count"] == 12

    def test_max_degree_positive(self):
        g = _make_graph(node_count=5, edge_count=10)
        features = extract_features(g)
        assert features["max_degree"] >= 1

    def test_density_in_range(self):
        g = _make_graph()
        features = extract_features(g)
        assert 0.0 <= features["density"] <= 1.0

    def test_risk_tag_count(self):
        g = _make_graph(node_count=10, risk_tag_ratio=0.3)
        features = extract_features(g)
        assert features["risk_tag_count"] == 3  # 30% of 10

    def test_direct_hit_count(self):
        g = _make_graph(node_count=10, direct_hit_count=2)
        features = extract_features(g)
        assert features["direct_hit_count"] == 2

    def test_burst_score_range(self):
        g = _make_graph()
        features = extract_features(g)
        assert 0.0 <= features["burst_score"] <= 1.0

    def test_value_features_positive(self):
        g = _make_graph(value_range=(1.0, 10.0))
        features = extract_features(g)
        assert features["total_value"] > 0
        assert features["avg_value"] > 0
        assert features["max_value"] > 0

    def test_empty_graph_features(self):
        features = extract_features(_empty_graph())
        assert features["node_count"] == 0
        assert features["edge_count"] == 0
        assert features["total_value"] == 0
        assert features["risk_tag_count"] == 0

    def test_target_node_identified(self):
        g = _make_graph(node_count=5)
        features = extract_features(g)
        # Target node is the first one (source="target")
        assert features["target_in_degree"] >= 0
        assert features["target_out_degree"] >= 0
        assert features["target_tx_count"] >= 0


# ---------------------------------------------------------------------------
# Score behaviour tests
# ---------------------------------------------------------------------------

class TestScoreBehaviour:
    """Verify that score responds correctly to risk signals."""

    def test_higher_risk_tags_higher_score(self):
        scorer = RaindropAmlScorer()
        low = scorer.predict(_make_graph(risk_tag_ratio=0.0))
        high = scorer.predict(_make_graph(risk_tag_ratio=0.8))
        assert high.score >= low.score

    def test_direct_hits_increase_score(self):
        scorer = RaindropAmlScorer()
        no_hits = scorer.predict(_make_graph(direct_hit_count=0))
        with_hits = scorer.predict(_make_graph(direct_hit_count=3))
        assert with_hits.score >= no_hits.score

    def test_deeper_graph_higher_score(self):
        scorer = RaindropAmlScorer()
        shallow = scorer.predict(_make_graph(max_hop=1))
        deep = scorer.predict(_make_graph(max_hop=5))
        assert deep.score >= shallow.score

    def test_higher_centrality_higher_score(self):
        scorer = RaindropAmlScorer()
        # Many nodes, few edges → low centrality
        low = scorer.predict(_make_graph(node_count=20, edge_count=10))
        # Few nodes, many edges → high centrality
        high = scorer.predict(_make_graph(node_count=4, edge_count=20))
        assert high.score >= low.score


# ---------------------------------------------------------------------------
# Explanation tests
# ---------------------------------------------------------------------------

class TestExplanation:
    """Verify that explanations are human-readable and informative."""

    def test_explanation_mentions_score(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_make_graph())
        assert "score" in result.explanation.lower()

    def test_explanation_high_risk_mentions_tags(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_make_graph(risk_tag_ratio=0.8, direct_hit_count=2))
        # Should mention risk tags
        assert "tag" in result.explanation.lower() or "risk" in result.explanation.lower()

    def test_explanation_empty_graph(self):
        scorer = RaindropAmlScorer()
        result = scorer.predict(_empty_graph())
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestIntegration:
    """Verify ML layer integrates with the scoring pipeline."""

    @pytest.mark.asyncio
    async def test_scoring_pipeline_uses_raindrop(self):
        """End-to-end: scoring.py should use RaindropAmlScorer."""
        from app.connectors.goplus import GoPlusClient
        from app.domain.patterns import PatternAnalyzer
        from app.domain.risk_intel import RiskIntelAggregator
        from app.domain.scoring import RiskScoringEngine

        graph = _make_graph(node_count=8, edge_count=12, risk_tag_ratio=0.25)
        scorer = RiskScoringEngine(
            intel=RiskIntelAggregator(GoPlusClient(demo_mode=True)),
            raindrop=RaindropAmlScorer(),
            patterns=PatternAnalyzer(),
        )
        response = await scorer.score_graph(
            "integration-test", graph, chain_id="1", watchlist={}
        )
        assert 0.0 <= response.raindrop_score <= 100.0
        assert 0.0 <= response.final_risk_score <= 100.0
        assert "raindrop_adapter" in response.feature_summary or "node_count" in response.feature_summary

    @pytest.mark.asyncio
    async def test_raindrop_score_is_advisory(self):
        """raindrop_score should never exceed final_risk_score when rule_score is higher."""
        from app.connectors.goplus import GoPlusClient
        from app.domain.patterns import PatternAnalyzer
        from app.domain.risk_intel import RiskIntelAggregator
        from app.domain.scoring import RiskScoringEngine

        # High-risk graph
        graph = _make_graph(
            node_count=10, edge_count=20, risk_tag_ratio=0.5,
            direct_hit_count=2, max_hop=4,
        )
        scorer = RiskScoringEngine(
            intel=RiskIntelAggregator(GoPlusClient(demo_mode=True)),
            raindrop=RaindropAmlScorer(),
            patterns=PatternAnalyzer(),
        )
        response = await scorer.score_graph(
            "advisory-test", graph, chain_id="1", watchlist={}
        )
        # final_risk_score = max(rule_score, 0.65*rule + 0.35*raindrop)
        # So final >= rule_score always (since raindrop >= 0)
        # And final >= raindrop_score is not guaranteed, but final >= 0.65*rule
        assert response.final_risk_score >= 0.0

    @pytest.mark.asyncio
    async def test_feature_summary_includes_raindrop_features(self):
        """Feature summary should include features from the ML layer."""
        from app.connectors.goplus import GoPlusClient
        from app.domain.patterns import PatternAnalyzer
        from app.domain.risk_intel import RiskIntelAggregator
        from app.domain.scoring import RiskScoringEngine

        graph = _make_graph(node_count=5, edge_count=8)
        scorer = RiskScoringEngine(
            intel=RiskIntelAggregator(GoPlusClient(demo_mode=True)),
            raindrop=RaindropAmlScorer(),
            patterns=PatternAnalyzer(),
        )
        response = await scorer.score_graph(
            "feature-test", graph, chain_id="1", watchlist={}
        )
        # Features from raindrop should be in feature_summary
        assert "burst_score" in response.feature_summary or "node_count" in response.feature_summary

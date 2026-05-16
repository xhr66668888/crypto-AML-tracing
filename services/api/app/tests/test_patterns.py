"""Comprehensive tests for all 9 deterministic AML pattern detectors.

Each test builds a specific graph scenario that should trigger exactly one
(or a known set of) pattern(s).  Determinism is verified by running the
same analysis twice and comparing results.
"""
from __future__ import annotations

from time import time

import pytest

from app.domain.models import GraphEdge, GraphNode, InvestigationGraph, RiskLevel
from app.domain.patterns import PatternAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _addr(n: int) -> str:
    """Generate a deterministic test address."""
    return f"0x{n:040x}"


def _tx_hash(n: int) -> str:
    """Generate a deterministic test tx hash."""
    return f"0x{n:064x}"


def _make_edge(
    idx: int,
    source: str,
    target: str,
    value_eth: float,
    timestamp: int,
    hop: int = 1,
    direction: str = "out",
) -> GraphEdge:
    return GraphEdge(
        id=f"edge-{idx}",
        source=source,
        target=target,
        tx_hash=_tx_hash(idx),
        timestamp=timestamp,
        value_eth=value_eth,
        hop=hop,
        direction=direction,
    )


def _make_node(addr: str, hop: int = 0, risk_score: float = 0.0, source: str = "derived") -> GraphNode:
    return GraphNode(
        id=addr,
        address=addr,
        label=f"{addr[:6]}...{addr[-4:]}",
        hop=hop,
        risk_score=risk_score,
        source=source,
    )


# ---------------------------------------------------------------------------
# Fixtures: Layering
# ---------------------------------------------------------------------------

def make_layering_graph() -> InvestigationGraph:
    """Graph with 5 hops and 12 edges — should trigger layering.

    A -> B -> C -> D -> E -> F
    Each hop is within a short time window (30 minutes apart).
    """
    now = int(time())
    addresses = [_addr(i) for i in range(6)]  # A-F
    nodes = [_make_node(a, hop=i) for i, a in enumerate(addresses)]

    edges = []
    for i in range(5):
        edges.append(_make_edge(
            idx=i,
            source=addresses[i],
            target=addresses[i + 1],
            value_eth=10.0 - i * 0.5,
            timestamp=now - (5 - i) * 1800,  # 30 min apart
            hop=i + 1,
        ))

    # Add extra edges to meet the >= 8 edge requirement
    for i in range(5, 12):
        src_idx = i % 5
        tgt_idx = (i + 1) % 5
        edges.append(_make_edge(
            idx=i,
            source=addresses[src_idx],
            target=addresses[tgt_idx],
            value_eth=5.0,
            timestamp=now - (12 - i) * 900,
            hop=src_idx + 1,
        ))

    return InvestigationGraph(investigation_id="layering-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: Aggregation
# ---------------------------------------------------------------------------

def make_aggregation_graph() -> InvestigationGraph:
    """5 sources sending to 1 sink — should trigger aggregation."""
    now = int(time())
    sink = _addr(0)
    sources = [_addr(i) for i in range(1, 6)]

    nodes = [_make_node(sink, hop=0)]
    nodes.extend(_make_node(s, hop=1) for s in sources)

    edges = []
    for i, src in enumerate(sources):
        edges.append(_make_edge(
            idx=i,
            source=src,
            target=sink,
            value_eth=2.5 + i * 0.3,
            timestamp=now - i * 600,
            hop=1,
            direction="in",
        ))

    return InvestigationGraph(investigation_id="aggregation-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: Peel Chain
# ---------------------------------------------------------------------------

def make_peel_chain_graph() -> InvestigationGraph:
    """Classic peel chain: source peels decreasing amounts to 5 targets."""
    now = int(time())
    source = _addr(0)
    targets = [_addr(i) for i in range(1, 6)]

    nodes = [_make_node(source, hop=0)]
    nodes.extend(_make_node(t, hop=i + 1) for i, t in enumerate(targets))

    # Strictly descending values: 100 -> 50 -> 25 -> 12 -> 6
    values = [100.0, 50.0, 25.0, 12.0, 6.0]
    edges = []
    for i, (tgt, val) in enumerate(zip(targets, values)):
        edges.append(_make_edge(
            idx=i,
            source=source,
            target=tgt,
            value_eth=val,
            timestamp=now - (5 - i) * 3600,
            hop=i + 1,
        ))

    return InvestigationGraph(investigation_id="peel-chain-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: Threshold Structuring
# ---------------------------------------------------------------------------

def make_threshold_structuring_graph() -> InvestigationGraph:
    """Multiple transfers just below 10 ETH threshold — should trigger structuring."""
    now = int(time())
    source = _addr(0)
    targets = [_addr(i) for i in range(1, 6)]

    nodes = [_make_node(source, hop=0)]
    nodes.extend(_make_node(t, hop=1) for t in targets)

    # All values are 9.0-9.99 ETH (just below 10 ETH threshold)
    values = [9.1, 9.3, 9.5, 9.7, 9.9]
    edges = []
    for i, (tgt, val) in enumerate(zip(targets, values)):
        edges.append(_make_edge(
            idx=i,
            source=source,
            target=tgt,
            value_eth=val,
            timestamp=now - i * 300,
            hop=1,
        ))

    return InvestigationGraph(investigation_id="threshold-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: High-Frequency Small-Value
# ---------------------------------------------------------------------------

def make_high_frequency_graph() -> InvestigationGraph:
    """8 tiny transfers within 1 hour — should trigger high_frequency_micro."""
    now = int(time())
    source = _addr(0)
    targets = [_addr(i) for i in range(1, 9)]

    nodes = [_make_node(source, hop=0)]
    nodes.extend(_make_node(t, hop=1) for t in targets)

    edges = []
    for i, tgt in enumerate(targets):
        edges.append(_make_edge(
            idx=i,
            source=source,
            target=tgt,
            value_eth=0.005 + i * 0.001,
            timestamp=now - (8 - i) * 300,  # 5 min apart
            hop=1,
        ))

    return InvestigationGraph(investigation_id="high-freq-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: Dusting
# ---------------------------------------------------------------------------

def make_dusting_graph() -> InvestigationGraph:
    """7 dust transfers to 7 distinct recipients — should trigger dusting."""
    now = int(time())
    source = _addr(0)
    targets = [_addr(i) for i in range(1, 8)]

    nodes = [_make_node(source, hop=0)]
    nodes.extend(_make_node(t, hop=1) for t in targets)

    edges = []
    for i, tgt in enumerate(targets):
        edges.append(_make_edge(
            idx=i,
            source=source,
            target=tgt,
            value_eth=0.00005,
            timestamp=now - i * 60,
            hop=1,
        ))

    return InvestigationGraph(investigation_id="dusting-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: One-Shot Addresses
# ---------------------------------------------------------------------------

def make_one_shot_graph() -> InvestigationGraph:
    """10 non-target addresses with degree 1 — should trigger one_shot_addresses."""
    now = int(time())
    hub = _addr(0)
    spokes = [_addr(i) for i in range(1, 12)]  # 11 spokes, 10 with degree 1

    nodes = [_make_node(hub, hop=0)]
    nodes.extend(_make_node(s, hop=1) for s in spokes)

    edges = []
    # Hub sends to each spoke (degree 1 for each spoke)
    for i, spoke in enumerate(spokes[:10]):
        edges.append(_make_edge(
            idx=i,
            source=hub,
            target=spoke,
            value_eth=1.0,
            timestamp=now - i * 600,
            hop=1,
        ))

    # One spoke has degree 2 (doesn't count as one-shot)
    edges.append(_make_edge(
        idx=10,
        source=spokes[10],
        target=spokes[0],
        value_eth=0.5,
        timestamp=now - 6000,
        hop=2,
    ))

    return InvestigationGraph(investigation_id="one-shot-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: Centrality Hub
# ---------------------------------------------------------------------------

def make_centrality_hub_graph() -> InvestigationGraph:
    """Hub with degree 10 — should trigger centrality_hub."""
    now = int(time())
    hub = _addr(0)
    periphery = [_addr(i) for i in range(1, 11)]

    nodes = [_make_node(hub, hop=0)]
    nodes.extend(_make_node(p, hop=1) for p in periphery)

    edges = []
    # Hub transacts with all 10 periphery nodes
    for i, p in enumerate(periphery):
        edges.append(_make_edge(
            idx=i,
            source=hub,
            target=p,
            value_eth=2.0,
            timestamp=now - i * 120,
            hop=1,
        ))

    return InvestigationGraph(investigation_id="centrality-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Fixtures: Risk Propagation
# ---------------------------------------------------------------------------

def make_risk_propagation_graph() -> InvestigationGraph:
    """Hub with 2 high-risk neighbors at hop 1 — should trigger risk_propagation."""
    now = int(time())
    target_addr = _addr(0)
    risky1 = _addr(1)
    risky2 = _addr(2)
    normal = _addr(3)

    nodes = [
        _make_node(target_addr, hop=0, risk_score=20.0, source="target"),
        _make_node(risky1, hop=1, risk_score=80.0),
        _make_node(risky2, hop=1, risk_score=75.0),
        _make_node(normal, hop=1, risk_score=10.0),
    ]

    edges = [
        _make_edge(0, target_addr, risky1, 5.0, now - 1000, hop=1),
        _make_edge(1, target_addr, risky2, 3.0, now - 2000, hop=1),
        _make_edge(2, target_addr, normal, 1.0, now - 3000, hop=1),
    ]

    return InvestigationGraph(investigation_id="risk-prop-test", nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLayering:
    def test_layering_detected(self):
        graph = make_layering_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "layering" in names

    def test_layering_has_required_fields(self):
        graph = make_layering_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        layering = [s for s in signals if s.name == "layering"]
        assert len(layering) == 1
        s = layering[0]
        assert s.name == "layering"
        assert s.severity in {RiskLevel.medium, RiskLevel.high}
        assert 0 <= s.score <= 100
        assert s.subject
        assert s.evidence
        assert 0 <= s.confidence <= 1
        assert isinstance(s.metadata, dict)
        assert "max_hop" in s.metadata

    def test_layering_not_triggered_with_few_hops(self):
        """Graph with only 2 hops should not trigger layering."""
        now = int(time())
        nodes = [_make_node(_addr(i), hop=i) for i in range(3)]
        edges = [_make_edge(i, _addr(i), _addr(i + 1), 5.0, now - i * 600, hop=i + 1) for i in range(2)]
        graph = InvestigationGraph(investigation_id="no-layer", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "layering" not in names


class TestAggregation:
    def test_aggregation_detected(self):
        graph = make_aggregation_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "aggregation" in names

    def test_aggregation_subject_is_sink(self):
        graph = make_aggregation_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        agg = [s for s in signals if s.name == "aggregation"]
        assert len(agg) == 1
        assert agg[0].subject == _addr(0)

    def test_aggregation_not_triggered_below_threshold(self):
        """3 sources should not trigger aggregation (needs >= 4)."""
        now = int(time())
        sink = _addr(0)
        sources = [_addr(i) for i in range(1, 4)]
        nodes = [_make_node(sink, hop=0)] + [_make_node(s, hop=1) for s in sources]
        edges = [_make_edge(i, s, sink, 1.0, now - i * 100, hop=1) for i, s in enumerate(sources)]
        graph = InvestigationGraph(investigation_id="no-agg", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "aggregation" not in names


class TestPeelChain:
    def test_peel_chain_detected(self):
        graph = make_peel_chain_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "peel_chain" in names

    def test_peel_chain_evidence_mentions_values(self):
        graph = make_peel_chain_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        peel = [s for s in signals if s.name == "peel_chain"]
        assert len(peel) == 1
        assert "first value" in peel[0].evidence.lower() or "decrease" in peel[0].evidence.lower()

    def test_peel_chain_not_triggered_with_ascending_values(self):
        """Ascending values over time should not trigger peel chain.

        We create edges where the oldest transaction has the smallest value
        and the newest has the largest.  When sorted by timestamp (oldest
        first) the values ascend: [6, 12, 25, 50, 100].  No descending
        pairs means the detector should not fire.
        """
        now = int(time())
        source = _addr(0)
        targets = [_addr(i) for i in range(1, 6)]
        nodes = [_make_node(source, hop=0)] + [_make_node(t, hop=1) for t in targets]
        # Oldest first with ascending values
        values = [6.0, 12.0, 25.0, 50.0, 100.0]
        edges = [_make_edge(i, source, targets[i], v, now - (4 - i) * 3600, hop=1) for i, v in enumerate(values)]
        graph = InvestigationGraph(investigation_id="no-peel", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "peel_chain" not in names


class TestThresholdStructuring:
    def test_threshold_structuring_detected(self):
        graph = make_threshold_structuring_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "threshold_structuring" in names

    def test_threshold_structuring_metadata(self):
        graph = make_threshold_structuring_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        ts = [s for s in signals if s.name == "threshold_structuring"]
        assert len(ts) == 1
        assert ts[0].metadata["transfer_count"] >= 3
        assert "most_common_threshold" in ts[0].metadata

    def test_threshold_not_triggered_with_random_values(self):
        """Values far from thresholds should not trigger."""
        now = int(time())
        source = _addr(0)
        targets = [_addr(i) for i in range(1, 6)]
        nodes = [_make_node(source, hop=0)] + [_make_node(t, hop=1) for t in targets]
        edges = [_make_edge(i, source, targets[i], 0.001 * (i + 1), now - i * 300, hop=1) for i in range(5)]
        graph = InvestigationGraph(investigation_id="no-thresh", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "threshold_structuring" not in names


class TestHighFrequencyMicro:
    def test_high_frequency_detected(self):
        graph = make_high_frequency_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "high_frequency_micro" in names

    def test_high_frequency_metadata_has_span(self):
        graph = make_high_frequency_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        hf = [s for s in signals if s.name == "high_frequency_micro"]
        assert len(hf) == 1
        assert "time_span_seconds" in hf[0].metadata
        assert hf[0].metadata["time_span_seconds"] <= 24 * 60 * 60

    def test_high_frequency_not_triggered_with_large_values(self):
        """Values > 0.02 ETH should not count as micro."""
        now = int(time())
        source = _addr(0)
        targets = [_addr(i) for i in range(1, 9)]
        nodes = [_make_node(source, hop=0)] + [_make_node(t, hop=1) for t in targets]
        edges = [_make_edge(i, source, targets[i], 1.0, now - (8 - i) * 300, hop=1) for i in range(8)]
        graph = InvestigationGraph(investigation_id="no-hf", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "high_frequency_micro" not in names


class TestDusting:
    def test_dusting_detected(self):
        graph = make_dusting_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "dusting" in names

    def test_dusting_subject_is_source(self):
        graph = make_dusting_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        dust = [s for s in signals if s.name == "dusting"]
        assert len(dust) == 1
        assert dust[0].subject == _addr(0)

    def test_dusting_not_triggered_with_large_values(self):
        """Values > 0.0001 ETH should not count as dust."""
        now = int(time())
        source = _addr(0)
        targets = [_addr(i) for i in range(1, 8)]
        nodes = [_make_node(source, hop=0)] + [_make_node(t, hop=1) for t in targets]
        edges = [_make_edge(i, source, targets[i], 0.01, now - i * 60, hop=1) for i in range(7)]
        graph = InvestigationGraph(investigation_id="no-dust", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "dusting" not in names


class TestOneShotAddresses:
    def test_one_shot_detected(self):
        graph = make_one_shot_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "one_shot_addresses" in names

    def test_one_shot_ratio_in_metadata(self):
        graph = make_one_shot_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        osa = [s for s in signals if s.name == "one_shot_addresses"]
        assert len(osa) == 1
        assert osa[0].metadata["singleton_ratio"] >= 0.7

    def test_one_shot_not_triggered_with_small_graph(self):
        """Graph with < 8 nodes should not trigger."""
        now = int(time())
        nodes = [_make_node(_addr(i), hop=i) for i in range(5)]
        edges = [_make_edge(i, _addr(i), _addr(i + 1), 1.0, now - i * 600, hop=i + 1) for i in range(4)]
        graph = InvestigationGraph(investigation_id="no-os", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "one_shot_addresses" not in names


class TestCentralityHub:
    def test_centrality_hub_detected(self):
        graph = make_centrality_hub_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph)
        names = {s.name for s in signals}
        assert "centrality_hub" in names

    def test_centrality_hub_subject_is_hub(self):
        graph = make_centrality_hub_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        ch = [s for s in signals if s.name == "centrality_hub"]
        assert len(ch) == 1
        assert ch[0].subject == _addr(0)

    def test_centrality_hub_metadata(self):
        graph = make_centrality_hub_graph()
        signals = PatternAnalyzer().analyze_graph(graph)
        ch = [s for s in signals if s.name == "centrality_hub"]
        assert ch[0].metadata["degree"] >= 6
        assert "betweenness_centrality" in ch[0].metadata

    def test_centrality_not_triggered_with_low_degree(self):
        """Node with degree < 6 should not trigger."""
        now = int(time())
        nodes = [_make_node(_addr(i), hop=i % 2) for i in range(5)]
        edges = [_make_edge(i, _addr(i), _addr((i + 1) % 5), 1.0, now - i * 600, hop=1) for i in range(5)]
        graph = InvestigationGraph(investigation_id="no-ch", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph)
        names = {s.name for s in signals}
        assert "centrality_hub" not in names


class TestRiskPropagation:
    def test_risk_propagation_detected(self):
        graph = make_risk_propagation_graph()
        analyzer = PatternAnalyzer()
        signals = analyzer.analyze_graph(graph, target_address=_addr(0))
        names = {s.name for s in signals}
        assert "risk_propagation" in names

    def test_risk_propagation_metadata(self):
        graph = make_risk_propagation_graph()
        signals = PatternAnalyzer().analyze_graph(graph, target_address=_addr(0))
        rp = [s for s in signals if s.name == "risk_propagation"]
        assert len(rp) == 1
        assert rp[0].metadata["risky_node_count"] == 2
        assert rp[0].metadata["nearest_hop"] == 1

    def test_risk_propagation_not_triggered_without_risky_nodes(self):
        """No high-risk nodes should not trigger."""
        now = int(time())
        nodes = [
            _make_node(_addr(0), hop=0, risk_score=10.0, source="target"),
            _make_node(_addr(1), hop=1, risk_score=10.0),
        ]
        edges = [_make_edge(0, _addr(0), _addr(1), 1.0, now - 1000, hop=1)]
        graph = InvestigationGraph(investigation_id="no-rp", nodes=nodes, edges=edges)
        signals = PatternAnalyzer().analyze_graph(graph, target_address=_addr(0))
        names = {s.name for s in signals}
        assert "risk_propagation" not in names


class TestDeterminism:
    """All detectors must produce identical output for identical input."""

    def test_layering_deterministic(self):
        graph = make_layering_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_aggregation_deterministic(self):
        graph = make_aggregation_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_peel_chain_deterministic(self):
        graph = make_peel_chain_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_threshold_structuring_deterministic(self):
        graph = make_threshold_structuring_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_high_frequency_deterministic(self):
        graph = make_high_frequency_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_dusting_deterministic(self):
        graph = make_dusting_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_one_shot_deterministic(self):
        graph = make_one_shot_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_centrality_hub_deterministic(self):
        graph = make_centrality_hub_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph)]
        run2 = [s.model_dump() for s in a.analyze_graph(graph)]
        assert run1 == run2

    def test_risk_propagation_deterministic(self):
        graph = make_risk_propagation_graph()
        a = PatternAnalyzer()
        run1 = [s.model_dump() for s in a.analyze_graph(graph, target_address=_addr(0))]
        run2 = [s.model_dump() for s in a.analyze_graph(graph, target_address=_addr(0))]
        assert run1 == run2


class TestNetworkMetrics:
    """Test network metric computation."""

    def test_metrics_not_empty_for_nontrivial_graph(self):
        graph = make_centrality_hub_graph()
        metrics = PatternAnalyzer().network_metrics(graph)
        assert len(metrics) >= 5
        names = {m.name for m in metrics}
        assert "node_count" in names
        assert "edge_count" in names
        assert "graph_density" in names

    def test_metrics_include_betweenness(self):
        graph = make_centrality_hub_graph()
        metrics = PatternAnalyzer().network_metrics(graph)
        names = {m.name for m in metrics}
        assert "max_betweenness_centrality" in names

    def test_metrics_include_components(self):
        graph = make_centrality_hub_graph()
        metrics = PatternAnalyzer().network_metrics(graph)
        names = {m.name for m in metrics}
        assert "connected_component_count" in names
        assert "largest_component_size" in names

    def test_metrics_include_clustering(self):
        graph = make_centrality_hub_graph()
        metrics = PatternAnalyzer().network_metrics(graph)
        names = {m.name for m in metrics}
        assert "average_clustering_coefficient" in names

    def test_metrics_include_path_length(self):
        graph = make_centrality_hub_graph()
        metrics = PatternAnalyzer().network_metrics(graph)
        names = {m.name for m in metrics}
        assert "average_path_length" in names

    def test_metrics_empty_for_empty_graph(self):
        graph = InvestigationGraph(investigation_id="empty", nodes=[], edges=[])
        metrics = PatternAnalyzer().network_metrics(graph)
        assert metrics == []


class TestAllSignalFields:
    """Every PatternSignal must carry all required fields with valid values."""

    REQUIRED_FIELDS = {"name", "severity", "score", "subject", "evidence", "confidence", "metadata"}

    def _validate_signals(self, signals: list):
        for s in signals:
            data = s.model_dump()
            for field in self.REQUIRED_FIELDS:
                assert field in data, f"Missing field {field} in signal {s.name}"
            assert 0 <= s.score <= 100, f"Score out of range: {s.score}"
            assert 0 <= s.confidence <= 1, f"Confidence out of range: {s.confidence}"
            assert s.evidence, f"Empty evidence for {s.name}"
            assert s.subject, f"Empty subject for {s.name}"
            assert isinstance(s.metadata, dict), f"Metadata not dict for {s.name}"

    def test_layering_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_layering_graph()))

    def test_aggregation_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_aggregation_graph()))

    def test_peel_chain_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_peel_chain_graph()))

    def test_threshold_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_threshold_structuring_graph()))

    def test_high_frequency_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_high_frequency_graph()))

    def test_dusting_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_dusting_graph()))

    def test_one_shot_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_one_shot_graph()))

    def test_centrality_hub_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_centrality_hub_graph()))

    def test_risk_propagation_fields(self):
        self._validate_signals(PatternAnalyzer().analyze_graph(make_risk_propagation_graph(), target_address=_addr(0)))

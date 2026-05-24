"""AML feature extraction from transaction graphs.

Builds a deterministic feature dict from ``InvestigationGraph`` objects.
All features are scalar (float or int) so the dict can be serialised to JSON
and later converted to numpy/torch tensors without ambiguity.

Feature schema version: 1
"""

from __future__ import annotations

from collections import Counter
from statistics import pstdev

from app.domain.models import InvestigationGraph


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

FEATURE_SCHEMA_VERSION = 1


def extract_features(graph: InvestigationGraph) -> dict[str, float | int | str]:
    """Return a flat feature dict extracted from *graph*.

    Keys are grouped into five families:
    - ``graph_*``   – topology of the entire transaction graph
    - ``node_*``    – per-node aggregated (target node) metrics
    - ``temporal_*`` – timing characteristics
    - ``value_*``   – ETH/token value distribution
    - ``risk_*``    – risk-tag and direct-hit counts

    The returned dict always includes ``feature_schema_version`` so downstream
    consumers can detect when the schema changes.
    """
    nodes = graph.nodes
    edges = graph.edges

    # Build helpers --------------------------------------------------------
    degree: Counter[str] = Counter()
    in_degree: Counter[str] = Counter()
    out_degree: Counter[str] = Counter()
    for edge in edges:
        degree[edge.source] += 1
        degree[edge.target] += 1
        out_degree[edge.source] += 1
        in_degree[edge.target] += 1

    values = [_edge_amount(edge) for edge in edges]
    timestamps = sorted(edge.timestamp for edge in edges if edge.timestamp > 0)

    # Target node (root of investigation) ---------------------------------
    target_node = next((n for n in nodes if n.source.startswith("target")), None)
    target_addr = target_node.address if target_node else ""

    # Graph-level features ------------------------------------------------
    node_count = len(nodes)
    edge_count = len(edges)
    degrees = list(degree.values()) if degree else [0]
    avg_degree = sum(degrees) / len(degrees)
    max_degree = max(degrees)
    density = edge_count / max(node_count * max(node_count - 1, 1), 1)

    # Node-level features (target node) -----------------------------------
    target_in = in_degree.get(target_addr, 0)
    target_out = out_degree.get(target_addr, 0)
    # value in/out for target
    value_in = sum(_edge_amount(e) for e in edges if e.target == target_addr)
    value_out = sum(_edge_amount(e) for e in edges if e.source == target_addr)
    tx_count = target_in + target_out

    # Temporal features ---------------------------------------------------
    time_span = (timestamps[-1] - timestamps[0]) if len(timestamps) >= 2 else 0
    if len(timestamps) >= 2:
        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        avg_time_between = sum(gaps) / len(gaps) if gaps else 0
        burst_score = _burst_score(gaps)
    else:
        avg_time_between = 0
        burst_score = 0.0

    # Value features ------------------------------------------------------
    total_value = sum(values)
    avg_value = total_value / max(len(values), 1)
    max_value = max(values) if values else 0.0
    value_variance = pstdev(values) if len(values) > 1 else 0.0

    # Risk features -------------------------------------------------------
    risk_tag_count = sum(1 for n in nodes if n.tags and "trust_list" not in n.tags)
    direct_hit_count = sum(
        1 for n in nodes
        if n.tags and any(
            t.lower() in {"ofac", "sanctions", "pep", "circle_blacklist",
                          "tether_blacklist", "stablecoin_blacklist", "sanctioned"}
            for t in n.tags
        )
    )

    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        # Graph-level
        "node_count": node_count,
        "edge_count": edge_count,
        "avg_degree": round(avg_degree, 4),
        "max_degree": max_degree,
        "density": round(density, 6),
        # Node-level (target)
        "target_in_degree": target_in,
        "target_out_degree": target_out,
        "target_total_value_in": round(value_in, 8),
        "target_total_value_out": round(value_out, 8),
        "target_tx_count": tx_count,
        # Temporal
        "time_span": time_span,
        "avg_time_between_txs": round(avg_time_between, 4),
        "burst_score": round(burst_score, 4),
        # Value
        "total_value": round(total_value, 8),
        "avg_value": round(avg_value, 8),
        "max_value": round(max_value, 8),
        "value_variance": round(value_variance, 8),
        # Risk
        "risk_tag_count": risk_tag_count,
        "direct_hit_count": direct_hit_count,
        # Max hop
        "max_hop": max((n.hop for n in nodes), default=0),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _burst_score(gaps: list[int]) -> float:
    """Measure temporal burstiness using coefficient of variation.

    Returns a value in [0, 1].  A perfectly regular stream yields 0; a
    highly bursty stream (many zero/near-zero gaps mixed with large gaps)
    approaches 1.
    """
    if len(gaps) < 2:
        return 0.0
    mean_gap = sum(gaps) / len(gaps)
    if mean_gap <= 0:
        return 1.0
    cv = pstdev(gaps) / mean_gap
    return min(1.0, cv)


def _edge_amount(edge) -> float:
    return float(edge.amount if getattr(edge, "amount", None) is not None else edge.value_eth)

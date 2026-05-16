"""Raindrop AML Scorer – deterministic rule-based V1.

This module provides the **stable** ``RaindropAmlScorer`` adapter that is
imported by ``scoring.py``.  The ``predict(graph)`` signature is frozen until
``aml-architect`` approves a change (see docs/architecture.md).

Model version: ``raindrop-v1-deterministic``
Feature schema version: 1  (see ``features.py``)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.models import InvestigationGraph
from app.ml.features import FEATURE_SCHEMA_VERSION, extract_features


# ---------------------------------------------------------------------------
# Stable return type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RaindropResult:
    """Immutable result returned by ``RaindropAmlScorer.predict``.

    Attributes
    ----------
    score : float
        Risk score in [0, 100].  Advisory only – never overrides rule_score or
        direct-hit evidence.
    features : dict
        Feature vector used to derive *score*.  Serialisable to JSON.
    explanation : str
        Human-readable summary of the main score drivers.
    model_version : str
        Identifier that ties this result to a specific model/checkpoint.
    """

    score: float
    features: dict[str, Any]
    explanation: str
    model_version: str


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

_MODEL_VERSION = f"raindrop-v{FEATURE_SCHEMA_VERSION}-deterministic"


class RaindropAmlScorer:
    """Deterministic, CPU-only AML risk scorer.

    The MVP uses rule-based feature scoring.  A future PyTorch/PyG model will
    replace the internals of ``predict`` while keeping the same signature and
    return type.
    """

    def predict(self, graph: InvestigationGraph) -> RaindropResult:
        """Score a transaction graph.

        Parameters
        ----------
        graph : InvestigationGraph
            Bounded transaction graph built by ``GraphBuilder``.

        Returns
        -------
        RaindropResult
            score in [0, 100], feature dict, human explanation, model version.
        """
        features = extract_features(graph)

        # --- Component scores (each 0-100, weighted) ---
        centrality_score = self._centrality_component(features)
        risk_tag_score = self._risk_tag_component(features)
        temporal_score = self._temporal_component(features)
        value_score = self._value_component(features)
        depth_score = self._depth_component(features)

        # Weighted combination
        raw = (
            0.25 * centrality_score
            + 0.25 * risk_tag_score
            + 0.20 * temporal_score
            + 0.15 * value_score
            + 0.15 * depth_score
        )
        score = round(min(100.0, max(0.0, raw)), 2)

        explanation = self._build_explanation(
            score, centrality_score, risk_tag_score,
            temporal_score, value_score, depth_score, features,
        )

        return RaindropResult(
            score=score,
            features=features,
            explanation=explanation,
            model_version=_MODEL_VERSION,
        )

    # ------------------------------------------------------------------
    # Component scorers (each returns 0-100)
    # ------------------------------------------------------------------

    @staticmethod
    def _centrality_component(f: dict) -> float:
        """High centrality (max_degree) → higher risk."""
        max_deg = f["max_degree"]
        # Linear scale: degree 1 → 0, degree 15+ → 100
        return min(100.0, max(0.0, (max_deg - 1) / 14 * 100))

    @staticmethod
    def _risk_tag_component(f: dict) -> float:
        """Many risk tags → higher risk.  Direct hits dominate."""
        tag_count = f["risk_tag_count"]
        direct = f["direct_hit_count"]
        node_count = max(f["node_count"], 1)
        # Direct hits are extremely concerning
        direct_bonus = min(60.0, direct * 30.0)
        # Tag ratio contribution
        ratio_score = min(40.0, (tag_count / node_count) * 100)
        return min(100.0, direct_bonus + ratio_score)

    @staticmethod
    def _temporal_component(f: dict) -> float:
        """Rapid / bursty transactions → higher risk."""
        burst = f["burst_score"]  # 0-1
        time_span = f["time_span"]
        edge_count = max(f["edge_count"], 1)
        # High burst score is concerning
        burst_contrib = burst * 60
        # Many transactions in a short time span
        if time_span > 0 and edge_count >= 4:
            rate = edge_count / (time_span / 3600)  # tx/hour
            rate_contrib = min(40.0, rate * 2)
        else:
            rate_contrib = 0.0
        return min(100.0, burst_contrib + rate_contrib)

    @staticmethod
    def _value_component(f: dict) -> float:
        """Large value variance → higher risk (mixing patterns)."""
        total = f["total_value"]
        variance = f["value_variance"]
        avg = f["avg_value"]
        # High total value raises attention
        total_contrib = min(40.0, total * 0.4)
        # High variance relative to mean suggests mixing
        if avg > 0:
            cv = variance / avg
            variance_contrib = min(60.0, cv * 15)
        else:
            variance_contrib = 0.0
        return min(100.0, total_contrib + variance_contrib)

    @staticmethod
    def _depth_component(f: dict) -> float:
        """Deeper graph (more hops) → higher risk."""
        max_hop = f["max_hop"]
        # hop 0 → 0, hop 5+ → 100
        return min(100.0, max(0.0, max_hop / 5 * 100))

    # ------------------------------------------------------------------
    # Explanation builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanation(
        score: float,
        centrality: float,
        risk_tag: float,
        temporal: float,
        value: float,
        depth: float,
        f: dict,
    ) -> str:
        drivers: list[str] = []

        if risk_tag >= 40:
            drivers.append(
                f"High risk-tag exposure: {f['risk_tag_count']} tagged nodes "
                f"({f['direct_hit_count']} direct hits)"
            )
        if centrality >= 40:
            drivers.append(
                f"Central hub detected: max degree {f['max_degree']}"
            )
        if temporal >= 40:
            drivers.append(
                f"Bursty transaction pattern: burst score {f['burst_score']:.2f}"
            )
        if value >= 40:
            drivers.append(
                f"Value dispersion: total {f['total_value']:.4f} ETH, "
                f"variance {f['value_variance']:.4f}"
            )
        if depth >= 40:
            drivers.append(
                f"Deep graph traversal: {f['max_hop']} hops"
            )

        if not drivers:
            return (
                f"Raindrop score {score:.1f}/100 – no dominant risk signals. "
                f"Graph has {f['node_count']} nodes and {f['edge_count']} edges."
            )

        return (
            f"Raindrop score {score:.1f}/100 driven by: "
            + "; ".join(drivers) + "."
        )

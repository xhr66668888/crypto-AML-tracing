from __future__ import annotations

from statistics import pstdev

from app.domain.models import InvestigationGraph


class RaindropAmlScorer:
    """Raindrop-inspired AML scoring adapter.

    This is the production boundary for the Harvard Raindrop model idea. The
    MVP implementation computes deterministic temporal-graph features. The next
    ML task replaces `predict` internals with a PyTorch/PyG model ported from
    `Raindrop/code/models_rd.py` while preserving this method signature.
    """

    def predict(self, graph: InvestigationGraph) -> tuple[float, dict[str, float | int | str]]:
        timestamps = sorted(edge.timestamp for edge in graph.edges if edge.timestamp > 0)
        values = [edge.value_eth for edge in graph.edges]
        high_tag_nodes = [node for node in graph.nodes if node.tags and "trust_list" not in node.tags]

        temporal_irregularity = self._temporal_irregularity(timestamps)
        burst_score = min(35.0, temporal_irregularity * 35.0)
        value_dispersion = min(25.0, (pstdev(values) if len(values) > 1 else 0.0) * 2.5)
        tagged_exposure = min(40.0, (len(high_tag_nodes) / max(len(graph.nodes), 1)) * 100)
        depth_exposure = min(20.0, max((node.hop for node in graph.nodes), default=0) * 5)

        score = min(100.0, burst_score + value_dispersion + tagged_exposure + depth_exposure)
        features: dict[str, float | int | str] = {
            "raindrop_adapter": "deterministic-mvp",
            "temporal_irregularity": round(temporal_irregularity, 4),
            "value_dispersion": round(value_dispersion, 4),
            "tagged_exposure_nodes": len(high_tag_nodes),
            "max_hop": max((node.hop for node in graph.nodes), default=0),
        }
        return round(score, 2), features

    @staticmethod
    def _temporal_irregularity(timestamps: list[int]) -> float:
        if len(timestamps) < 3:
            return 0.0
        gaps = [right - left for left, right in zip(timestamps, timestamps[1:]) if right > left]
        if len(gaps) < 2:
            return 0.0
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap == 0:
            return 0.0
        return min(1.0, pstdev(gaps) / mean_gap)

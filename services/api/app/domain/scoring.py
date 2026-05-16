from __future__ import annotations

from app.domain.models import (
    GraphNode,
    InvestigationGraph,
    PatternSignal,
    RiskDisposition,
    RiskFinding,
    RiskLevel,
    RiskResponse,
    RiskSourceHit,
)
from app.domain.patterns import PatternAnalyzer
from app.domain.risk_intel import SEVERITY_WEIGHTS, RiskIntelAggregator
from app.ml.raindrop_scorer import RaindropAmlScorer


class RiskScoringEngine:
    def __init__(self, intel: RiskIntelAggregator, raindrop: RaindropAmlScorer, patterns: PatternAnalyzer | None = None) -> None:
        self.intel = intel
        self.raindrop = raindrop
        self.patterns = patterns or PatternAnalyzer()

    async def score_graph(self, investigation_id: str, graph: InvestigationGraph, chain_id: str, watchlist: dict) -> RiskResponse:
        findings: list[RiskFinding] = []
        source_hits: list[RiskSourceHit] = []
        node_by_address = {node.address: node for node in graph.nodes}

        for node in graph.nodes:
            tags, raw_findings, node_source_hits = await self.intel.enrich_address_detail(
                node.address,
                chain_id=chain_id,
                local_watchlist=watchlist,
            )
            node.tags = tags
            source_hits.extend(node_source_hits)
            node_score = 0.0
            for category, severity, evidence in raw_findings:
                decayed = max(0.35, 1 - node.hop * 0.12)
                score = SEVERITY_WEIGHTS[severity] * decayed
                node_score = max(node_score, score)
                findings.append(
                    RiskFinding(
                        category=category,
                        severity=severity,
                        score=round(score, 2),
                        subject=node.address,
                        evidence=evidence,
                        source=category,
                        hop=node.hop,
                    )
                )
            node.risk_score = round(node_score, 2)
            node.risk_level = risk_level(node.risk_score)

        exposure_score = self._edge_exposure_score(graph, node_by_address)
        target_address = next((node.address for node in graph.nodes if node.source.startswith("target")), None)
        pattern_signals = self.patterns.analyze_graph(graph, target_address=target_address)
        network_metrics = self.patterns.network_metrics(graph)
        findings.extend(self._pattern_findings(pattern_signals))
        pattern_score = max((signal.score for signal in pattern_signals), default=0.0)
        direct_hit_score = self._direct_hit_score(source_hits)
        base_rule_score = max([node.risk_score for node in graph.nodes] + [0]) + exposure_score
        rule_score = min(100.0, max(base_rule_score, pattern_score, direct_hit_score))
        raindrop_result = self.raindrop.predict(graph)
        if isinstance(raindrop_result, tuple):
            raindrop_score, raindrop_features = raindrop_result
        else:
            raindrop_score = raindrop_result.score
            raindrop_features = raindrop_result.features
        # final_risk_score = max(rule_score, raindrop_score)
        # raindrop_score is advisory — it can raise the floor but never
        # overrides source-backed evidence captured in rule_score.
        final_score = min(100.0, max(rule_score, raindrop_score))
        top_paths = self._top_risk_paths(graph)
        disposition = decide_disposition(final_score, source_hits, pattern_signals)
        actions = recommended_actions(disposition, source_hits, pattern_signals)

        feature_summary = {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "max_hop": max((node.hop for node in graph.nodes), default=0),
            "edge_exposure_score": round(exposure_score, 2),
            "pattern_signal_count": len(pattern_signals),
            "max_pattern_score": round(pattern_score, 2),
            **raindrop_features,
        }

        return RiskResponse(
            investigation_id=investigation_id,
            rule_score=round(rule_score, 2),
            raindrop_score=round(raindrop_score, 2),
            final_risk_score=round(final_score, 2),
            final_risk_level=risk_level(final_score),
            findings=sorted(findings, key=lambda item: item.score, reverse=True),
            top_risk_paths=top_paths,
            feature_summary=feature_summary,
            pattern_signals=pattern_signals,
            source_hits=source_hits,
            network_metrics=network_metrics,
            disposition_hint=disposition,
            recommended_actions=actions,
        )

    @staticmethod
    def _edge_exposure_score(graph: InvestigationGraph, nodes: dict[str, GraphNode]) -> float:
        exposure = 0.0
        for edge in graph.edges:
            source_risk = nodes.get(edge.source).risk_score if nodes.get(edge.source) else 0
            target_risk = nodes.get(edge.target).risk_score if nodes.get(edge.target) else 0
            if source_risk or target_risk:
                exposure += min(4.0, edge.value_eth / 3.0)
        return min(20.0, exposure)

    @staticmethod
    def _top_risk_paths(graph: InvestigationGraph) -> list[list[str]]:
        risky = sorted((node for node in graph.nodes if node.risk_score > 0), key=lambda node: node.risk_score, reverse=True)
        paths: list[list[str]] = []
        for node in risky[:5]:
            incoming = next((edge for edge in graph.edges if edge.target == node.address), None)
            if incoming:
                paths.append([incoming.source, incoming.target])
            else:
                paths.append([node.address])
        return paths

    @staticmethod
    def _pattern_findings(signals: list[PatternSignal]) -> list[RiskFinding]:
        return [
            RiskFinding(
                category="pattern",
                severity=signal.severity,
                score=round(signal.score, 2),
                subject=signal.subject,
                evidence=signal.evidence,
                source=f"pattern:{signal.name}",
                metadata={"confidence": signal.confidence, **signal.metadata},
            )
            for signal in signals
            if signal.score >= 35
        ]

    @staticmethod
    def _direct_hit_score(source_hits: list[RiskSourceHit]) -> float:
        direct_hits = [hit for hit in source_hits if hit.direct_hit]
        if not direct_hits:
            return 0.0
        return max(float(SEVERITY_WEIGHTS[hit.severity]) for hit in direct_hits)


def risk_level(score: float) -> RiskLevel:
    """Map a 0–100 numeric score to a risk level.

    Boundaries (spec):
    - low: 0–30
    - medium: 31–60
    - high: 61–85
    - critical: 86–100
    """
    if score >= 86:
        return RiskLevel.critical
    if score >= 61:
        return RiskLevel.high
    if score >= 31:
        return RiskLevel.medium
    return RiskLevel.low


def decide_disposition(
    score: float,
    source_hits: list[RiskSourceHit],
    pattern_signals: list[PatternSignal],
) -> RiskDisposition:
    direct_hits = [hit for hit in source_hits if hit.direct_hit]
    if any(hit.severity == RiskLevel.critical for hit in direct_hits):
        return RiskDisposition.hold_for_manual_review
    if direct_hits:
        return RiskDisposition.hold_for_manual_review
    if score >= 85:
        return RiskDisposition.hold_for_manual_review
    if score >= 65 or any(signal.severity == RiskLevel.high for signal in pattern_signals):
        return RiskDisposition.review
    if score >= 35:
        return RiskDisposition.review
    return RiskDisposition.allow


def recommended_actions(
    disposition: RiskDisposition,
    source_hits: list[RiskSourceHit],
    pattern_signals: list[PatternSignal],
) -> list[str]:
    actions: list[str] = []
    if any(hit.direct_hit for hit in source_hits):
        actions.append("Hold funds for manual compliance review and verify the authoritative source evidence.")
    if any(hit.category.lower() in {"pep", "ofac", "sanctions", "sanctioned"} for hit in source_hits):
        actions.append("Escalate to the sanctions/PEP review workflow before customer release.")
    if any(signal.name in {"dusting", "dusting_counterparty"} for signal in pattern_signals):
        actions.append("Warn the operator about recent dusting-like behavior before approving withdrawal.")
    if any(signal.name in {"layering", "aggregation", "peel_chain"} for signal in pattern_signals):
        actions.append("Open a deeper investigation case and preserve the graph evidence.")
    if disposition == RiskDisposition.review and not actions:
        actions.append("Queue for manual risk review with the attached evidence.")
    if disposition == RiskDisposition.allow:
        actions.append("Allow if no additional business-rule controls apply.")
    return actions

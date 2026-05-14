from __future__ import annotations

from app.domain.models import GraphNode, InvestigationGraph, RiskFinding, RiskLevel, RiskResponse
from app.domain.risk_intel import SEVERITY_WEIGHTS, RiskIntelAggregator
from app.ml.raindrop_aml import RaindropAmlScorer


class RiskScoringEngine:
    def __init__(self, intel: RiskIntelAggregator, raindrop: RaindropAmlScorer) -> None:
        self.intel = intel
        self.raindrop = raindrop

    async def score_graph(self, investigation_id: str, graph: InvestigationGraph, chain_id: str, watchlist: dict) -> RiskResponse:
        findings: list[RiskFinding] = []
        node_by_address = {node.address: node for node in graph.nodes}

        for node in graph.nodes:
            tags, raw_findings = await self.intel.enrich_address(node.address, chain_id=chain_id, local_watchlist=watchlist)
            node.tags = tags
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
        rule_score = min(100.0, max([node.risk_score for node in graph.nodes] + [0]) + exposure_score)
        raindrop_score, raindrop_features = self.raindrop.predict(graph)
        final_score = min(100.0, max(rule_score, 0.65 * rule_score + 0.35 * raindrop_score))
        top_paths = self._top_risk_paths(graph)

        feature_summary = {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "max_hop": max((node.hop for node in graph.nodes), default=0),
            "edge_exposure_score": round(exposure_score, 2),
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


def risk_level(score: float) -> RiskLevel:
    if score >= 85:
        return RiskLevel.critical
    if score >= 65:
        return RiskLevel.high
    if score >= 35:
        return RiskLevel.medium
    return RiskLevel.low

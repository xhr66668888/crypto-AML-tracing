from __future__ import annotations

from time import time
from uuid import uuid4

from app.domain.graph_builder import GraphBuilder, short_address
from app.domain.models import (
    GraphEdge,
    GraphNode,
    InvestigationGraph,
    InvestigationMode,
    PatternSignal,
    RiskFinding,
    ScreeningResponse,
    ScreeningTransactionCreate,
)
from app.domain.patterns import PatternAnalyzer
from app.domain.scoring import decide_disposition, recommended_actions, risk_level
from app.domain.scoring import RiskScoringEngine
from app.domain.validators import normalize_address, normalize_hash
from app.storage.memory import InMemoryStore


class ScreeningService:
    def __init__(
        self,
        store: InMemoryStore,
        graph_builder: GraphBuilder,
        scoring: RiskScoringEngine,
        patterns: PatternAnalyzer,
    ) -> None:
        self.store = store
        self.graph_builder = graph_builder
        self.scoring = scoring
        self.patterns = patterns

    async def screen_transaction(self, payload: ScreeningTransactionCreate) -> ScreeningResponse:
        screening_id = str(uuid4())
        from_address = normalize_address(payload.from_address)
        to_address = normalize_address(payload.to_address)
        tx_hash = normalize_hash(payload.tx_hash) if payload.tx_hash else f"screening:{screening_id}"
        target = to_address if payload.direction.value == "outbound" else from_address

        graph = await self._context_graph(
            screening_id=screening_id,
            target=target,
            chain_id=payload.chain_id,
            from_address=from_address,
            to_address=to_address,
            tx_hash=tx_hash,
            amount=payload.amount,
            timestamp=payload.timestamp or int(time()),
        )
        risk = await self.scoring.score_graph(
            screening_id,
            graph,
            chain_id=payload.chain_id,
            watchlist=self.store.get_watchlist_map(),
        )
        transaction_signals = self.patterns.analyze_transaction(
            from_address=from_address,
            to_address=to_address,
            amount=payload.amount,
            asset=payload.asset.value,
            direction=payload.direction.value,
            graph=graph,
        )
        all_signals = self._dedupe_signals([*transaction_signals, *risk.pattern_signals])
        findings = [*self._pattern_findings(transaction_signals), *risk.findings]
        score = round(min(100.0, max(risk.final_risk_score, *(signal.score for signal in all_signals), 0)), 2)
        disposition = decide_disposition(score, risk.source_hits, all_signals)
        actions = recommended_actions(disposition, risk.source_hits, all_signals)

        response = ScreeningResponse(
            id=screening_id,
            chain_id=payload.chain_id,
            asset=payload.asset,
            direction=payload.direction,
            from_address=from_address,
            to_address=to_address,
            amount=payload.amount,
            risk_score=score,
            risk_level=risk_level(score),
            disposition=disposition,
            findings=sorted(findings, key=lambda item: item.score, reverse=True),
            pattern_signals=all_signals,
            source_hits=risk.source_hits,
            evidence_summary=self._evidence_summary(risk.source_hits, all_signals, findings),
            recommended_actions=actions,
            data_freshness=self._data_freshness(risk.source_hits),
            graph_investigation_id=screening_id,
        )
        return self.store.add_screening_event(response)

    async def _context_graph(
        self,
        screening_id: str,
        target: str,
        chain_id: str,
        from_address: str,
        to_address: str,
        tx_hash: str,
        amount: float,
        timestamp: int,
    ) -> InvestigationGraph:
        result = await self.graph_builder.build_from_address(
            screening_id,
            target,
            chain_id=chain_id,
            depth=2,
            mode=InvestigationMode.stable,
        )
        graph = result.graph
        node_by_address = {node.address: node for node in graph.nodes}
        for address, source in ((from_address, "screening_party"), (to_address, "screening_party")):
            if address not in node_by_address:
                graph.nodes.append(GraphNode(id=address, address=address, label=short_address(address), hop=0, source=source))
        edge_id = f"{tx_hash}:{from_address}:{to_address}"
        if all(edge.id != edge_id for edge in graph.edges):
            graph.edges.insert(
                0,
                GraphEdge(
                    id=edge_id,
                    source=from_address,
                    target=to_address,
                    tx_hash=tx_hash,
                    timestamp=timestamp,
                    value_eth=amount,
                    hop=0,
                    direction="screening",
                    metadata={"source": "screening_request"},
                ),
            )
        return graph

    @staticmethod
    def _pattern_findings(signals: list[PatternSignal]) -> list[RiskFinding]:
        return [
            RiskFinding(
                category="pattern",
                severity=signal.severity,
                score=signal.score,
                subject=signal.subject,
                evidence=signal.evidence,
                source=f"screening_pattern:{signal.name}",
                metadata={"confidence": signal.confidence, **signal.metadata},
            )
            for signal in signals
        ]

    @staticmethod
    def _dedupe_signals(signals: list[PatternSignal]) -> list[PatternSignal]:
        deduped: dict[tuple[str, str], PatternSignal] = {}
        for signal in signals:
            key = (signal.name, signal.subject)
            current = deduped.get(key)
            if current is None or signal.score > current.score:
                deduped[key] = signal
        return sorted(deduped.values(), key=lambda item: item.score, reverse=True)

    @staticmethod
    def _evidence_summary(source_hits, signals: list[PatternSignal], findings: list[RiskFinding]) -> list[str]:
        summary: list[str] = []
        summary.extend(hit.evidence for hit in source_hits[:3])
        summary.extend(signal.evidence for signal in signals[:3])
        summary.extend(finding.evidence for finding in findings[:3])
        deduped = list(dict.fromkeys(item for item in summary if item))
        return deduped[:8]

    @staticmethod
    def _data_freshness(source_hits) -> dict[str, str]:
        freshness = {"transaction_context": "current_request", "graph_context": "provider_recent_transactions"}
        for hit in source_hits:
            if hit.source_updated_at:
                freshness[hit.source] = hit.source_updated_at.isoformat()
            else:
                freshness.setdefault(hit.source, "provider_response")
        return freshness

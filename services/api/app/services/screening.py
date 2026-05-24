from __future__ import annotations

from collections import defaultdict, deque
from time import time
from uuid import uuid4

from app.connectors.base import ConnectorError
from app.connectors.goplus import GoPlusClient
from app.connectors.stablecoin_blacklist import StablecoinBlacklistCheck, StablecoinBlacklistClient
from app.domain.assets import AssetMetadata, resolve_screening_asset
from app.domain.graph_builder import GraphBuilder, short_address
from app.domain.models import (
    GraphEdge,
    GraphNode,
    InvestigationGraph,
    InvestigationMode,
    PatternSignal,
    PreTransactionScreeningCreate,
    RiskFinding,
    RiskLevel,
    RiskResponse,
    RiskSourceHit,
    ScreeningResponse,
    TransferDirection,
)
from app.domain.patterns import PatternAnalyzer
from app.domain.scoring import decide_disposition, recommended_actions, risk_level
from app.domain.scoring import RiskScoringEngine
from app.domain.validators import normalize_address
from app.storage.base import StorageAdapter


TOKEN_CONTRACT_RISK_FLAGS: tuple[tuple[str, RiskLevel, str], ...] = (
    ("is_honeypot", RiskLevel.critical, "honeypot behavior"),
    ("hidden_owner", RiskLevel.high, "hidden owner"),
    ("selfdestruct", RiskLevel.high, "selfdestruct capability"),
    ("cannot_sell_all", RiskLevel.high, "cannot sell all tokens"),
    ("owner_change_balance", RiskLevel.medium, "owner can change balances"),
    ("owner_can_pause", RiskLevel.medium, "owner can pause transfers"),
    ("external_call", RiskLevel.medium, "external call behavior"),
)
SCREENING_CONTEXT_DEPTH = 2
SCREENING_REPEATED_TRANSFER_WINDOW_SECONDS = 24 * 60 * 60
INTERNAL_CREGIS_ADDRESS = "0x0000000000000000000000000000000000000000"


class ScreeningService:
    def __init__(
        self,
        store: StorageAdapter,
        graph_builder: GraphBuilder,
        scoring: RiskScoringEngine,
        patterns: PatternAnalyzer,
        stablecoin_blacklist: StablecoinBlacklistClient | None = None,
        token_security: GoPlusClient | None = None,
    ) -> None:
        self.store = store
        self.graph_builder = graph_builder
        self.scoring = scoring
        self.patterns = patterns
        self.stablecoin_blacklist = stablecoin_blacklist
        self.token_security = token_security

    async def screen_transaction(self, payload: PreTransactionScreeningCreate) -> ScreeningResponse:
        screening_id = str(uuid4())
        counterparty_address = normalize_address(payload.counterparty_address)
        from_address, to_address = _screening_parties(payload.direction, counterparty_address)
        asset = resolve_screening_asset(
            payload.asset,
            chain_id=payload.chain_id,
            asset_type=payload.asset_type,
            token_address=payload.token_address,
        )

        graph = await self._context_graph(
            screening_id=screening_id,
            chain_id=payload.chain_id,
            counterparty_address=counterparty_address,
            asset=asset,
        )
        risk = await self.scoring.score_graph(
            screening_id,
            graph,
            chain_id=payload.chain_id,
            watchlist=self.store.get_watchlist_map(),
        )
        party_addresses = {counterparty_address}
        party_source_hits = self._party_source_hits(risk.source_hits, party_addresses)
        context_signals = [
            *self._context_exposure_signals(graph, counterparty_address, payload.direction, risk.source_hits),
            *self._repeated_transfer_signals(graph, counterparty_address, asset),
        ]
        transaction_signals = self.patterns.analyze_transaction(
            from_address=from_address,
            to_address=to_address,
            amount=payload.amount,
            asset=asset.symbol,
            asset_type=asset.asset_type,
            direction=payload.direction.value,
            graph=graph,
        )
        stablecoin_hits, stablecoin_findings, stablecoin_signals = await self._stablecoin_blacklist_evidence(
            asset=asset,
            chain_id=payload.chain_id,
            addresses=[counterparty_address],
        )
        token_hits, token_findings, token_signals = await self._token_contract_evidence(asset, payload.chain_id)
        provider_findings = [*stablecoin_findings, *token_findings]
        source_hits = [*party_source_hits, *stablecoin_hits, *token_hits]
        all_signals = self._dedupe_signals(
            [*context_signals, *transaction_signals, *risk.pattern_signals, *stablecoin_signals, *token_signals]
        )
        findings = [
            *self._pattern_findings(transaction_signals),
            *provider_findings,
            *self._screening_findings(risk.findings, party_addresses),
        ]
        direct_hit_score = 95.0 if any(hit.direct_hit for hit in source_hits) else 0.0
        provider_score = max((finding.score for finding in provider_findings), default=0.0)
        screening_base_score = self._screening_base_score(risk, party_addresses)
        score = round(min(100.0, max(screening_base_score, direct_hit_score, provider_score, *(signal.score for signal in all_signals), 0)), 2)
        disposition = decide_disposition(score, source_hits, all_signals)
        actions = recommended_actions(disposition, source_hits, all_signals)

        response = ScreeningResponse(
            id=screening_id,
            chain_id=payload.chain_id,
            asset=asset.symbol,
            direction=payload.direction,
            counterparty_address=counterparty_address,
            from_address=counterparty_address if payload.direction == TransferDirection.inbound else None,
            to_address=counterparty_address if payload.direction == TransferDirection.outbound else None,
            amount=payload.amount,
            risk_score=score,
            risk_level=risk_level(score),
            disposition=disposition,
            findings=sorted(findings, key=lambda item: item.score, reverse=True),
            pattern_signals=all_signals,
            source_hits=source_hits,
            evidence_summary=self._evidence_summary(source_hits, all_signals, findings),
            recommended_actions=actions,
            data_freshness=self._data_freshness(source_hits),
            graph_investigation_id=None,
        )
        return self.store.add_screening_event(response)

    async def _context_graph(
        self,
        screening_id: str,
        chain_id: str,
        counterparty_address: str,
        asset: AssetMetadata,
    ) -> InvestigationGraph:
        token_address = asset.token_address if asset.is_erc20 else None
        result = await self.graph_builder.build_from_address(
            screening_id,
            counterparty_address,
            chain_id=chain_id,
            depth=SCREENING_CONTEXT_DEPTH,
            mode=InvestigationMode.stable,
            token_address=token_address,
            asset_symbol=asset.symbol,
            root_source="screening_counterparty",
        )
        graph = result.graph
        node_by_address = {node.address: node for node in graph.nodes}
        node = node_by_address.get(counterparty_address)
        if node:
            node.hop = 0
            node.source = "screening_counterparty"
        else:
            graph.nodes.append(
                GraphNode(
                    id=counterparty_address,
                    address=counterparty_address,
                    label=short_address(counterparty_address),
                    hop=0,
                    source="screening_counterparty",
                )
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
    def _party_source_hits(source_hits: list[RiskSourceHit], party_addresses: set[str]) -> list[RiskSourceHit]:
        return [hit for hit in source_hits if hit.address.lower() in party_addresses]

    @staticmethod
    def _screening_findings(findings: list[RiskFinding], party_addresses: set[str]) -> list[RiskFinding]:
        return [
            finding
            for finding in findings
            if finding.subject in party_addresses or finding.source.startswith("pattern:")
        ]

    @staticmethod
    def _screening_base_score(risk: RiskResponse, party_addresses: set[str]) -> float:
        party_finding_score = max(
            (finding.score for finding in risk.findings if finding.subject in party_addresses),
            default=0.0,
        )
        graph_pattern_score = max((signal.score for signal in risk.pattern_signals), default=0.0)
        return max(party_finding_score, graph_pattern_score, risk.raindrop_score)

    @staticmethod
    def _context_exposure_signals(
        graph: InvestigationGraph,
        counterparty_address: str,
        direction: TransferDirection,
        source_hits: list[RiskSourceHit],
    ) -> list[PatternSignal]:
        hit_by_address = {hit.address.lower(): hit for hit in source_hits}
        node_by_address = {node.address: node for node in graph.nodes}
        role = "inbound_source" if direction == TransferDirection.inbound else "outbound_recipient"
        signals: list[PatternSignal] = []
        seen: set[str] = set()

        for risky in sorted(node_by_address.values(), key=lambda item: (-item.risk_score, item.address)):
            if risky.address == counterparty_address or risky.risk_score < 65:
                continue
            distance, path = _shortest_path_within_two_hops(graph, counterparty_address, risky.address)
            if distance not in {1, 2} or risky.address in seen:
                continue
            seen.add(risky.address)
            hit = hit_by_address.get(risky.address)
            label = hit.label if hit else ",".join(risky.tags[:2]) or "high-risk node"
            category = hit.category if hit else "node_risk"
            name = "one_hop_risky_exposure" if distance == 1 else "two_hop_risky_exposure"
            severity = RiskLevel.high if distance == 1 else RiskLevel.medium
            score = 72.0 if distance == 1 else 58.0
            evidence = (
                f"{role} {short_address(counterparty_address)} has {distance}-hop exposure to "
                f"{short_address(risky.address)} ({category}: {label}) in the bounded screening context graph."
            )
            signals.append(
                PatternSignal(
                    name=name,
                    severity=severity,
                    score=score,
                    subject=counterparty_address,
                    evidence=evidence,
                    confidence=0.78 if distance == 1 else 0.68,
                    metadata={
                        "party_role": role,
                        "party_address": counterparty_address,
                        "risky_address": risky.address,
                        "risky_score": risky.risk_score,
                        "hop_distance": distance,
                        "path": path,
                        "source_hit_source": hit.source if hit else "",
                        "source_hit_category": category,
                        "source_hit_evidence": hit.evidence if hit else "",
                    },
                )
            )
        return signals[:6]

    @staticmethod
    def _repeated_transfer_signals(
        graph: InvestigationGraph,
        counterparty_address: str,
        asset: AssetMetadata,
    ) -> list[PatternSignal]:
        groups: dict[tuple[str, str], list[GraphEdge]] = defaultdict(list)
        for edge in graph.edges:
            if edge.metadata.get("source") == "screening_request" or edge.timestamp <= 0:
                continue
            if edge.source == counterparty_address:
                groups[(counterparty_address, edge.target)].append(edge)
            elif edge.target == counterparty_address:
                groups[(counterparty_address, edge.source)].append(edge)

        signals: list[PatternSignal] = []
        for (party, counterparty), edges in sorted(groups.items()):
            if len(edges) < 3:
                continue
            timestamps = sorted(edge.timestamp for edge in edges)
            span = timestamps[-1] - timestamps[0]
            if span > SCREENING_REPEATED_TRANSFER_WINDOW_SECONDS:
                continue
            hours = max(round(span / 3600, 2), 0.01)
            evidence = (
                f"{asset.symbol} screening context shows {len(edges)} transfers between "
                f"{short_address(party)} and {short_address(counterparty)} within {hours:g}h."
            )
            signals.append(
                PatternSignal(
                    name="short_time_repeated_transfers",
                    severity=RiskLevel.medium,
                    score=min(62.0, 36 + len(edges) * 4),
                    subject=party,
                    evidence=evidence,
                    confidence=0.66,
                    metadata={
                        "party_address": party,
                        "counterparty": counterparty,
                        "transfer_count": len(edges),
                        "time_span_seconds": span,
                        "asset": asset.symbol,
                    },
                )
            )
        return signals[:4]

    async def _stablecoin_blacklist_evidence(
        self,
        asset: AssetMetadata,
        chain_id: str,
        addresses: list[str],
    ) -> tuple[list[RiskSourceHit], list[RiskFinding], list[PatternSignal]]:
        if self.stablecoin_blacklist is None:
            return [], [], []

        hits: list[RiskSourceHit] = []
        findings: list[RiskFinding] = []
        signals: list[PatternSignal] = []
        for address in dict.fromkeys(addresses):
            try:
                check = await self.stablecoin_blacklist.check_address(
                    asset.symbol,
                    address,
                    chain_id=chain_id,
                    token_address=asset.token_address,
                )
            except ConnectorError as exc:
                signals.append(self._stablecoin_degraded_signal(asset.symbol, address, exc))
                continue
            if check is None or not check.blacklisted:
                continue
            hits.append(self._stablecoin_source_hit(check))
            findings.append(
                RiskFinding(
                    category=check.category,
                    severity=RiskLevel.critical,
                    score=95.0,
                    subject=check.address,
                    evidence=check.evidence,
                    source=check.provider,
                    metadata={"token_symbol": check.token_symbol, "token_address": check.token_address},
                )
            )
        return hits, findings, signals

    async def _token_contract_evidence(
        self,
        asset: AssetMetadata,
        chain_id: str,
    ) -> tuple[list[RiskSourceHit], list[RiskFinding], list[PatternSignal]]:
        if not asset.is_erc20 or not asset.token_address or self.token_security is None:
            return [], [], []

        try:
            payload = await self.token_security.get_token_security(asset.token_address, chain_id=chain_id)
        except ConnectorError as exc:
            return [], [], [self._token_security_degraded_signal(asset, exc)]

        hits: list[RiskSourceHit] = []
        findings: list[RiskFinding] = []
        checked_at = int(time())
        for field, severity, label in TOKEN_CONTRACT_RISK_FLAGS:
            if not _is_enabled(payload.get(field)):
                continue
            evidence = f"GoPlus token security flags {asset.symbol} contract {asset.token_address}: {label}."
            hits.append(
                RiskSourceHit(
                    source="goplus_token_security",
                    category="token_contract_risk",
                    severity=severity,
                    address=asset.token_address,
                    label=label,
                    evidence=evidence,
                    confidence=0.85 if severity in {RiskLevel.high, RiskLevel.critical} else 0.65,
                    source_updated_at=None,
                    raw_payload={
                        "asset_symbol": asset.symbol,
                        "asset_decimals": asset.decimals,
                        "checked_at_unix": checked_at,
                        **payload,
                    },
                )
            )
            findings.append(
                RiskFinding(
                    category="token_contract_risk",
                    severity=severity,
                    score=95.0 if severity == RiskLevel.critical else 70.0 if severity == RiskLevel.high else 45.0,
                    subject=asset.token_address,
                    evidence=evidence,
                    source="goplus_token_security",
                    metadata={"asset_symbol": asset.symbol, "token_address": asset.token_address, "flag": field},
                )
            )
        return hits, findings, []

    @staticmethod
    def _stablecoin_source_hit(check: StablecoinBlacklistCheck) -> RiskSourceHit:
        return RiskSourceHit(
            source=check.provider,
            category=check.category,
            severity=RiskLevel.critical,
            address=check.address,
            label=f"{check.token_symbol} issuer blacklist",
            evidence=check.evidence,
            confidence=1.0,
            source_updated_at=check.checked_at,
            direct_hit=True,
            raw_payload={
                "token_symbol": check.token_symbol,
                "token_address": check.token_address,
                **check.raw_payload,
            },
        )

    @staticmethod
    def _stablecoin_degraded_signal(asset: str, address: str, exc: ConnectorError) -> PatternSignal:
        return PatternSignal(
            name="stablecoin_blacklist_unavailable",
            severity=RiskLevel.medium,
            score=35.0,
            subject=address,
            evidence=f"{asset} stablecoin blacklist check unavailable for {address}: {exc.message}",
            confidence=0.50,
            metadata={"provider": exc.provider, "retryable": exc.retryable},
        )

    @staticmethod
    def _token_security_degraded_signal(asset: AssetMetadata, exc: ConnectorError) -> PatternSignal:
        return PatternSignal(
            name="token_contract_risk_unavailable",
            severity=RiskLevel.medium,
            score=35.0,
            subject=asset.token_address or asset.symbol,
            evidence=f"GoPlus token contract risk check unavailable for {asset.symbol}: {exc.message}",
            confidence=0.50,
            metadata={"provider": exc.provider, "retryable": exc.retryable, "token_address": asset.token_address},
        )

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
        freshness = {"screening_context": "current_request", "address_context": "provider_recent_transactions"}
        for hit in source_hits:
            if hit.source_updated_at:
                freshness[hit.source] = hit.source_updated_at.isoformat()
            else:
                freshness.setdefault(hit.source, "provider_response")
        return freshness


def _is_enabled(value) -> bool:
    return value is True or str(value).strip() == "1"


def _screening_parties(direction: TransferDirection, counterparty_address: str) -> tuple[str, str]:
    if direction == TransferDirection.inbound:
        return counterparty_address, INTERNAL_CREGIS_ADDRESS
    return INTERNAL_CREGIS_ADDRESS, counterparty_address


def _shortest_path_within_two_hops(graph: InvestigationGraph, start: str, end: str) -> tuple[int, list[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in graph.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)

    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    visited = {start}
    while queue:
        address, path = queue.popleft()
        if len(path) > 3:
            continue
        if address == end:
            return len(path) - 1, path
        for neighbor in sorted(adjacency.get(address, set())):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, [*path, neighbor]))
    return 0, []

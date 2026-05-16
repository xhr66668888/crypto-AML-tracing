from __future__ import annotations

from collections import Counter, defaultdict
from time import time

from app.domain.models import GraphEdge, InvestigationGraph, NetworkMetric, PatternSignal, RiskLevel


class PatternAnalyzer:
    """Deterministic AML pattern detectors used before any ML prioritization."""

    ETH_THRESHOLDS = (1.0, 5.0, 10.0, 50.0)
    TOKEN_THRESHOLDS = (1000.0, 5000.0, 10000.0, 50000.0)

    def analyze_graph(self, graph: InvestigationGraph, target_address: str | None = None) -> list[PatternSignal]:
        signals: list[PatternSignal] = []
        edges = graph.edges
        if not edges:
            return signals

        signals.extend(self._layering(graph))
        signals.extend(self._aggregation(edges))
        signals.extend(self._peel_chain(edges))
        signals.extend(self._threshold_structuring(edges))
        signals.extend(self._high_frequency_micro(edges))
        signals.extend(self._dusting(edges))
        signals.extend(self._one_time_address_pattern(graph))
        signals.extend(self._risk_propagation(graph, target_address))
        signals.extend(self._centrality_signal(graph))
        return sorted(signals, key=lambda item: item.score, reverse=True)

    def analyze_transaction(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        asset: str,
        direction: str,
        graph: InvestigationGraph,
    ) -> list[PatternSignal]:
        signals: list[PatternSignal] = []
        thresholds = self.TOKEN_THRESHOLDS if asset.upper() in {"USDT", "USDC"} else self.ETH_THRESHOLDS
        near = next((threshold for threshold in thresholds if threshold * 0.9 <= amount < threshold), None)
        if near:
            signals.append(
                PatternSignal(
                    name="threshold_structuring",
                    severity=RiskLevel.medium,
                    score=42,
                    subject=to_address,
                    evidence=f"{asset.upper()} amount {amount:.6g} is just below the {near:.6g} review threshold.",
                    confidence=0.78,
                    metadata={"amount": amount, "threshold": near, "asset": asset.upper()},
                )
            )

        dust_edges = self._dust_edges(graph.edges)
        dust_touch = [
            edge
            for edge in dust_edges
            if edge.source in {from_address, to_address} or edge.target in {from_address, to_address}
        ]
        if direction == "outbound" and dust_touch:
            signals.append(
                PatternSignal(
                    name="dusting_counterparty",
                    severity=RiskLevel.high,
                    score=68,
                    subject=to_address,
                    evidence="Withdrawal counterparty has recent tiny-value transaction activity consistent with dusting probes.",
                    confidence=0.72,
                    metadata={"dust_edge_count": len(dust_touch)},
                )
            )

        degree = self._degree(graph.edges)
        if amount >= thresholds[min(2, len(thresholds) - 1)] and degree.get(to_address, 0) <= 1:
            signals.append(
                PatternSignal(
                    name="large_transfer_to_sparse_address",
                    severity=RiskLevel.medium,
                    score=48,
                    subject=to_address,
                    evidence="Large transfer is directed to an address with little observed graph activity.",
                    confidence=0.7,
                    metadata={"amount": amount, "asset": asset.upper(), "observed_degree": degree.get(to_address, 0)},
                )
            )

        return sorted(signals, key=lambda item: item.score, reverse=True)

    def network_metrics(self, graph: InvestigationGraph) -> list[NetworkMetric]:
        degree = self._degree(graph.edges)
        if not graph.nodes:
            return []
        max_degree_address, max_degree = max(degree.items(), key=lambda item: item[1], default=("", 0))
        singletons = sum(1 for node in graph.nodes if degree.get(node.address, 0) <= 1)
        density = len(graph.edges) / max(len(graph.nodes) * max(len(graph.nodes) - 1, 1), 1)
        return [
            NetworkMetric(name="node_count", value=float(len(graph.nodes))),
            NetworkMetric(name="edge_count", value=float(len(graph.edges))),
            NetworkMetric(name="graph_density", value=round(density, 4)),
            NetworkMetric(name="singleton_ratio", value=round(singletons / len(graph.nodes), 4)),
            NetworkMetric(name="max_degree", value=float(max_degree), subject=max_degree_address or None),
        ]

    @staticmethod
    def _layering(graph: InvestigationGraph) -> list[PatternSignal]:
        max_hop = max((node.hop for node in graph.nodes), default=0)
        if max_hop < 3 or len(graph.edges) < 8:
            return []
        score = min(75.0, 45 + max_hop * 6 + len(graph.edges) * 0.6)
        return [
            PatternSignal(
                name="layering",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=graph.investigation_id,
                evidence=f"Funds traverse {max_hop} hops across {len(graph.edges)} observed transfers.",
                confidence=0.68,
                metadata={"max_hop": max_hop, "edge_count": len(graph.edges)},
            )
        ]

    @staticmethod
    def _aggregation(edges: list[GraphEdge]) -> list[PatternSignal]:
        inbound: dict[str, set[str]] = defaultdict(set)
        totals: Counter[str] = Counter()
        for edge in edges:
            inbound[edge.target].add(edge.source)
            totals[edge.target] += edge.value_eth
        signals: list[PatternSignal] = []
        for target, sources in inbound.items():
            if len(sources) >= 4:
                score = min(82.0, 42 + len(sources) * 7 + min(totals[target], 20))
                signals.append(
                    PatternSignal(
                        name="aggregation",
                        severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                        score=round(score, 2),
                        subject=target,
                        evidence=f"{len(sources)} source addresses aggregate {totals[target]:.4g} ETH into one address.",
                        confidence=0.76,
                        metadata={"source_count": len(sources), "total_value_eth": round(totals[target], 8)},
                    )
                )
        return signals

    @staticmethod
    def _peel_chain(edges: list[GraphEdge]) -> list[PatternSignal]:
        outgoing: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in edges:
            outgoing[edge.source].append(edge)
        signals: list[PatternSignal] = []
        for source, source_edges in outgoing.items():
            ordered = sorted(source_edges, key=lambda item: item.timestamp)
            values = [edge.value_eth for edge in ordered if edge.value_eth > 0]
            if len(values) < 4:
                continue
            descending_pairs = sum(1 for left, right in zip(values, values[1:]) if right <= left)
            if descending_pairs >= 3 and len({edge.target for edge in ordered}) >= 3:
                score = min(74.0, 44 + descending_pairs * 8)
                signals.append(
                    PatternSignal(
                        name="peel_chain",
                        severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                        score=round(score, 2),
                        subject=source,
                        evidence="Sequential outgoing transfers decrease across multiple counterparties.",
                        confidence=0.69,
                        metadata={"transfer_count": len(values), "descending_pairs": descending_pairs},
                    )
                )
        return signals

    def _threshold_structuring(self, edges: list[GraphEdge]) -> list[PatternSignal]:
        near_threshold = [
            edge
            for edge in edges
            if any(threshold * 0.9 <= edge.value_eth < threshold for threshold in self.ETH_THRESHOLDS)
        ]
        if len(near_threshold) < 3:
            return []
        addresses = Counter(edge.source for edge in near_threshold) + Counter(edge.target for edge in near_threshold)
        subject = addresses.most_common(1)[0][0]
        score = min(68.0, 36 + len(near_threshold) * 7)
        return [
            PatternSignal(
                name="threshold_structuring",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=subject,
                evidence=f"{len(near_threshold)} transfers sit just below configured ETH review thresholds.",
                confidence=0.74,
                metadata={"transfer_count": len(near_threshold)},
            )
        ]

    @staticmethod
    def _high_frequency_micro(edges: list[GraphEdge]) -> list[PatternSignal]:
        tiny = [edge for edge in edges if 0 < edge.value_eth <= 0.02 and edge.timestamp > 0]
        if len(tiny) < 5:
            return []
        span = max(edge.timestamp for edge in tiny) - min(edge.timestamp for edge in tiny)
        if span > 24 * 60 * 60:
            return []
        return [
            PatternSignal(
                name="high_frequency_micro",
                severity=RiskLevel.medium,
                score=min(60.0, 34 + len(tiny) * 4),
                subject="transaction_graph",
                evidence=f"{len(tiny)} tiny transfers occur within a 24 hour window.",
                confidence=0.73,
                metadata={"transfer_count": len(tiny), "time_span_seconds": span},
            )
        ]

    def _dusting(self, edges: list[GraphEdge]) -> list[PatternSignal]:
        dust = self._dust_edges(edges)
        if len(dust) < 5:
            return []
        recipients = {edge.target for edge in dust}
        severity = RiskLevel.high if len(recipients) >= 8 else RiskLevel.medium
        return [
            PatternSignal(
                name="dusting",
                severity=severity,
                score=min(72.0, 38 + len(dust) * 4 + len(recipients)),
                subject="transaction_graph",
                evidence=f"{len(dust)} dust-sized transfers touch {len(recipients)} recipient addresses.",
                confidence=0.77,
                metadata={"dust_edge_count": len(dust), "recipient_count": len(recipients)},
            )
        ]

    @staticmethod
    def _one_time_address_pattern(graph: InvestigationGraph) -> list[PatternSignal]:
        if len(graph.nodes) < 8:
            return []
        degree = PatternAnalyzer._degree(graph.edges)
        singletons = [node.address for node in graph.nodes if node.hop > 0 and degree.get(node.address, 0) <= 1]
        ratio = len(singletons) / max(len(graph.nodes) - 1, 1)
        if ratio < 0.7:
            return []
        return [
            PatternSignal(
                name="one_time_address_pattern",
                severity=RiskLevel.medium,
                score=round(min(62.0, 30 + ratio * 40), 2),
                subject="transaction_graph",
                evidence=f"{ratio:.0%} of non-target addresses appear only once in the observed graph.",
                confidence=0.66,
                metadata={"singleton_ratio": round(ratio, 4), "singleton_count": len(singletons)},
            )
        ]

    @staticmethod
    def _risk_propagation(graph: InvestigationGraph, target_address: str | None) -> list[PatternSignal]:
        risky_nodes = [node for node in graph.nodes if node.risk_score >= 65 and (target_address is None or node.address != target_address)]
        if not risky_nodes:
            return []
        nearest_hop = min(node.hop for node in risky_nodes)
        score = max(58.0, 78 - nearest_hop * 8)
        return [
            PatternSignal(
                name="risk_propagation",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=target_address or graph.investigation_id,
                evidence=f"{len(risky_nodes)} high-risk labeled addresses are present within {nearest_hop} hops.",
                confidence=0.82,
                metadata={"risky_node_count": len(risky_nodes), "nearest_hop": nearest_hop},
            )
        ]

    @staticmethod
    def _centrality_signal(graph: InvestigationGraph) -> list[PatternSignal]:
        degree = PatternAnalyzer._degree(graph.edges)
        if not degree:
            return []
        address, max_degree = max(degree.items(), key=lambda item: item[1])
        if max_degree < 6:
            return []
        score = min(70.0, 36 + max_degree * 5)
        return [
            PatternSignal(
                name="centrality_hub",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=address,
                evidence=f"Address has degree {max_degree}, acting as a central routing node.",
                confidence=0.7,
                metadata={"degree": max_degree},
            )
        ]

    @staticmethod
    def _dust_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
        now = int(time())
        recent_floor = now - 45 * 24 * 60 * 60
        return [
            edge
            for edge in edges
            if 0 < edge.value_eth <= 0.0001 and (edge.timestamp == 0 or edge.timestamp >= recent_floor)
        ]

    @staticmethod
    def _degree(edges: list[GraphEdge]) -> Counter[str]:
        degree: Counter[str] = Counter()
        for edge in edges:
            degree[edge.source] += 1
            degree[edge.target] += 1
        return degree

from __future__ import annotations

import math
from collections import Counter, defaultdict
from time import time

from app.domain.models import GraphEdge, InvestigationGraph, NetworkMetric, PatternSignal, RiskLevel


class PatternAnalyzer:
    """Deterministic AML pattern detectors used before any ML prioritization.

    All detectors are pure functions of the graph structure.  Same input always
    produces the same ordered list of PatternSignal objects.  No external state
    or randomness is used.
    """

    ETH_THRESHOLDS = (1.0, 5.0, 10.0, 50.0)
    TOKEN_THRESHOLDS = (1000.0, 5000.0, 10000.0, 50000.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_graph(self, graph: InvestigationGraph, target_address: str | None = None) -> list[PatternSignal]:
        """Run all nine deterministic pattern detectors on *graph*.

        Returns signals sorted by score descending.
        """
        signals: list[PatternSignal] = []
        edges = graph.edges
        if not edges:
            return signals

        # Build adjacency for metrics used by multiple detectors
        adj = self._build_adjacency(graph)

        signals.extend(self._layering(graph))
        signals.extend(self._aggregation(edges))
        signals.extend(self._peel_chain(edges))
        signals.extend(self._threshold_structuring(edges))
        signals.extend(self._high_frequency_micro(edges))
        signals.extend(self._dusting(edges))
        signals.extend(self._one_shot_addresses(graph))
        signals.extend(self._centrality_hubs(graph, adj))
        signals.extend(self._risk_propagation(graph, target_address))
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
        """Single-transaction screening signals."""
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

    # ------------------------------------------------------------------
    # Network Metrics  (exposed for RaindropAmlScorer feature builder)
    # ------------------------------------------------------------------

    def network_metrics(self, graph: InvestigationGraph) -> list[NetworkMetric]:
        """Compute graph-level metrics suitable for downstream ML features."""
        degree = self._degree(graph.edges)
        in_degree, out_degree = self._in_out_degree(graph.edges)
        if not graph.nodes:
            return []

        max_degree_address, max_degree = max(degree.items(), key=lambda item: item[1], default=("", 0))
        singletons = sum(1 for node in graph.nodes if degree.get(node.address, 0) <= 1)
        n = len(graph.nodes)
        density = len(graph.edges) / max(n * max(n - 1, 1), 1)

        # Betweenness centrality (sampled for large graphs)
        bc = self._betweenness_centrality(graph)
        max_bc_address, max_bc = ("", 0.0)
        if bc:
            max_bc_address, max_bc = max(bc.items(), key=lambda item: item[1])

        # Connected components
        components = self._connected_components(graph)
        component_sizes = sorted([len(c) for c in components], reverse=True)

        # Average path length (from BFS on largest component)
        avg_path = self._avg_path_length_largest_component(graph, components)

        # Clustering coefficient
        cc = self._clustering_coefficient(graph)
        avg_cc = sum(cc.values()) / len(cc) if cc else 0.0

        metrics = [
            NetworkMetric(name="node_count", value=float(n)),
            NetworkMetric(name="edge_count", value=float(len(graph.edges))),
            NetworkMetric(name="graph_density", value=round(density, 4)),
            NetworkMetric(name="singleton_ratio", value=round(singletons / max(n, 1), 4)),
            NetworkMetric(name="max_degree", value=float(max_degree), subject=max_degree_address or None),
            NetworkMetric(name="max_betweenness_centrality", value=round(max_bc, 4), subject=max_bc_address or None),
            NetworkMetric(name="connected_component_count", value=float(len(components))),
            NetworkMetric(name="largest_component_size", value=float(component_sizes[0]) if component_sizes else 0.0),
            NetworkMetric(name="average_path_length", value=round(avg_path, 4)),
            NetworkMetric(name="average_clustering_coefficient", value=round(avg_cc, 4)),
        ]

        # In/out degree distribution summary
        if in_degree:
            top_in_addr, top_in_val = max(in_degree.items(), key=lambda item: item[1])
            metrics.append(NetworkMetric(name="max_in_degree", value=float(top_in_val), subject=top_in_addr))
        if out_degree:
            top_out_addr, top_out_val = max(out_degree.items(), key=lambda item: item[1])
            metrics.append(NetworkMetric(name="max_out_degree", value=float(top_out_val), subject=top_out_addr))

        return metrics

    # ------------------------------------------------------------------
    # Detector 1: Layering
    # ------------------------------------------------------------------

    @staticmethod
    def _layering(graph: InvestigationGraph) -> list[PatternSignal]:
        """Detect rapid sequential transfers through multiple addresses.

        Triggered when:
        - max observed hop >= 3 AND
        - at least 8 edges AND
        - time span of transfers is short relative to hop count (rapid movement)
        """
        max_hop = max((node.hop for node in graph.nodes), default=0)
        if max_hop < 3 or len(graph.edges) < 8:
            return []

        # Check for rapid movement: narrow time windows per hop
        hop_timestamps: dict[int, list[int]] = defaultdict(list)
        for edge in graph.edges:
            if edge.timestamp > 0:
                hop_timestamps[edge.hop].append(edge.timestamp)

        # Compute average time between consecutive hops
        hop_spans = []
        for hop in sorted(hop_timestamps):
            ts = sorted(hop_timestamps[hop])
            if len(ts) >= 2:
                hop_spans.append(ts[-1] - ts[0])
            elif ts:
                hop_spans.append(0)

        avg_span = sum(hop_spans) / len(hop_spans) if hop_spans else float("inf")
        rapid = avg_span < 3600 * 6  # 6 hours average per hop is suspicious

        score = min(78.0, 45 + max_hop * 6 + len(graph.edges) * 0.5)
        if rapid:
            score = min(85.0, score + 10)

        return [
            PatternSignal(
                name="layering",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=graph.investigation_id,
                evidence=f"Funds traverse {max_hop} hops across {len(graph.edges)} observed transfers with rapid per-hop time windows.",
                confidence=0.71 if rapid else 0.62,
                metadata={
                    "max_hop": max_hop,
                    "edge_count": len(graph.edges),
                    "rapid_movement": rapid,
                    "avg_hop_span_seconds": round(avg_span),
                },
            )
        ]

    # ------------------------------------------------------------------
    # Detector 2: Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregation(edges: list[GraphEdge]) -> list[PatternSignal]:
        """Detect fan-in: many small inputs consolidating into one address.

        Triggered when an address receives from >= 4 distinct sources.
        """
        inbound: dict[str, set[str]] = defaultdict(set)
        totals: Counter[str] = Counter()
        for edge in edges:
            inbound[edge.target].add(edge.source)
            totals[edge.target] += edge.value_eth

        signals: list[PatternSignal] = []
        for target, sources in sorted(inbound.items()):
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

    # ------------------------------------------------------------------
    # Detector 3: Peel Chain
    # ------------------------------------------------------------------

    @staticmethod
    def _peel_chain(edges: list[GraphEdge]) -> list[PatternSignal]:
        """Detect sequential transfers peeling off small amounts from a large source.

        Classic peel chain: a source sends most of its balance to a first
        recipient, then sends most of the remainder to a second recipient,
        and so on.  Each successive value is smaller than the previous one.
        """
        outgoing: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in edges:
            outgoing[edge.source].append(edge)

        signals: list[PatternSignal] = []
        for source in sorted(outgoing):
            source_edges = outgoing[source]
            ordered = sorted(source_edges, key=lambda item: item.timestamp)
            values = [edge.value_eth for edge in ordered if edge.value_eth > 0]
            if len(values) < 4:
                continue

            # Count strictly or weakly descending consecutive pairs
            descending_pairs = sum(1 for left, right in zip(values, values[1:]) if right <= left)
            unique_targets = len({edge.target for edge in ordered})

            if descending_pairs >= 3 and unique_targets >= 3:
                # Additional check: first value is significantly larger than last
                ratio = values[-1] / values[0] if values[0] > 0 else 0
                strong = descending_pairs >= 4 and ratio < 0.3

                score = min(78.0, 44 + descending_pairs * 8)
                if strong:
                    score = min(85.0, score + 8)

                signals.append(
                    PatternSignal(
                        name="peel_chain",
                        severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                        score=round(score, 2),
                        subject=source,
                        evidence=(
                            f"Sequential outgoing transfers decrease across {unique_targets} counterparties; "
                            f"first value {values[0]:.4g} ETH, last {values[-1]:.4g} ETH."
                        ),
                        confidence=0.72 if strong else 0.65,
                        metadata={
                            "transfer_count": len(values),
                            "descending_pairs": descending_pairs,
                            "unique_targets": unique_targets,
                            "first_value": values[0],
                            "last_value": values[-1],
                        },
                    )
                )
        return signals

    # ------------------------------------------------------------------
    # Detector 4: Threshold Structuring (just-under)
    # ------------------------------------------------------------------

    def _threshold_structuring(self, edges: list[GraphEdge]) -> list[PatternSignal]:
        """Detect multiple transactions just below reporting thresholds.

        Looks for repeated transfers at 90-100% of configured ETH thresholds.
        """
        near_threshold: list[GraphEdge] = []
        threshold_hit: dict[str, float] = {}  # edge_id -> threshold

        for edge in edges:
            for threshold in self.ETH_THRESHOLDS:
                if threshold * 0.9 <= edge.value_eth < threshold:
                    near_threshold.append(edge)
                    threshold_hit[edge.id] = threshold
                    break

        if len(near_threshold) < 3:
            return []

        # Find the most involved address
        addresses: Counter[str] = Counter()
        for edge in near_threshold:
            addresses[edge.source] += 1
            addresses[edge.target] += 1
        subject = addresses.most_common(1)[0][0]

        # Determine which threshold is most commonly approached
        threshold_counts: Counter[float] = Counter()
        for edge in near_threshold:
            if edge.id in threshold_hit:
                threshold_counts[threshold_hit[edge.id]] += 1
        most_common_threshold = threshold_counts.most_common(1)[0][0]

        score = min(72.0, 36 + len(near_threshold) * 7)
        return [
            PatternSignal(
                name="threshold_structuring",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=subject,
                evidence=f"{len(near_threshold)} transfers sit just below the {most_common_threshold:.4g} ETH review threshold.",
                confidence=0.76,
                metadata={
                    "transfer_count": len(near_threshold),
                    "most_common_threshold": most_common_threshold,
                    "threshold_counts": {str(k): v for k, v in sorted(threshold_counts.items())},
                },
            )
        ]

    # ------------------------------------------------------------------
    # Detector 5: High-Frequency Small-Value
    # ------------------------------------------------------------------

    @staticmethod
    def _high_frequency_micro(edges: list[GraphEdge]) -> list[PatternSignal]:
        """Detect many small transactions in a short time period.

        Triggered when >= 5 transfers with value <= 0.02 ETH occur within
        a 24-hour window.
        """
        tiny = [edge for edge in edges if 0 < edge.value_eth <= 0.02 and edge.timestamp > 0]
        if len(tiny) < 5:
            return []

        timestamps = sorted(edge.timestamp for edge in tiny)
        span = timestamps[-1] - timestamps[0]
        if span > 24 * 60 * 60:
            return []

        # Compute frequency (tx per hour)
        hours = max(span / 3600, 0.01)
        frequency = len(tiny) / hours

        score = min(64.0, 34 + len(tiny) * 3.5 + min(frequency, 10))
        return [
            PatternSignal(
                name="high_frequency_micro",
                severity=RiskLevel.medium,
                score=round(score, 2),
                subject="transaction_graph",
                evidence=f"{len(tiny)} tiny transfers occur within a {span // 3600}h window ({frequency:.1f} tx/hour).",
                confidence=0.74,
                metadata={
                    "transfer_count": len(tiny),
                    "time_span_seconds": span,
                    "frequency_per_hour": round(frequency, 2),
                    "total_value": round(sum(e.value_eth for e in tiny), 8),
                },
            )
        ]

    # ------------------------------------------------------------------
    # Detector 6: Dusting
    # ------------------------------------------------------------------

    def _dusting(self, edges: list[GraphEdge]) -> list[PatternSignal]:
        """Detect dust-sized transfers to many addresses.

        Dusting: sending tiny amounts (<= 0.0001 ETH) to many addresses,
        often used for tracking or mixing.  Triggered when >= 5 dust
        transfers touch >= 3 distinct recipients.
        """
        dust = self._dust_edges(edges)
        if len(dust) < 5:
            return []

        # Require touching multiple recipients to avoid false positive on
        # a single high-frequency dust source
        recipients = {edge.target for edge in dust}
        if len(recipients) < 3:
            return []

        # Find the most common dust source
        sources: Counter[str] = Counter(edge.source for edge in dust)
        primary_source = sources.most_common(1)[0][0]

        severity = RiskLevel.high if len(recipients) >= 8 else RiskLevel.medium
        score = min(76.0, 38 + len(dust) * 3 + len(recipients) * 2)
        return [
            PatternSignal(
                name="dusting",
                severity=severity,
                score=round(score, 2),
                subject=primary_source,
                evidence=f"{len(dust)} dust-sized transfers from {primary_source[:10]}… touch {len(recipients)} recipient addresses.",
                confidence=0.78,
                metadata={
                    "dust_edge_count": len(dust),
                    "recipient_count": len(recipients),
                    "primary_source": primary_source,
                },
            )
        ]

    # ------------------------------------------------------------------
    # Detector 7: One-Shot Addresses
    # ------------------------------------------------------------------

    @staticmethod
    def _one_shot_addresses(graph: InvestigationGraph) -> list[PatternSignal]:
        """Detect addresses that receive funds once and immediately forward.

        Triggered when >= 70% of non-target addresses have degree <= 1
        (appear in only one transaction).  This is consistent with
        one-time-use or throwaway addresses used to obscure fund flow.
        """
        if len(graph.nodes) < 8:
            return []

        degree = PatternAnalyzer._degree(graph.edges)
        singletons = [
            node.address for node in graph.nodes
            if node.hop > 0 and degree.get(node.address, 0) <= 1
        ]
        ratio = len(singletons) / max(len(graph.nodes) - 1, 1)
        if ratio < 0.7:
            return []

        return [
            PatternSignal(
                name="one_shot_addresses",
                severity=RiskLevel.medium,
                score=round(min(66.0, 30 + ratio * 40), 2),
                subject="transaction_graph",
                evidence=f"{ratio:.0%} of non-target addresses ({len(singletons)}/{len(graph.nodes) - 1}) appear only once in the observed graph.",
                confidence=0.67,
                metadata={"singleton_ratio": round(ratio, 4), "singleton_count": len(singletons)},
            )
        ]

    # ------------------------------------------------------------------
    # Detector 8: Centrality Hubs
    # ------------------------------------------------------------------

    @staticmethod
    def _centrality_hubs(graph: InvestigationGraph, adj: dict[str, set[str]]) -> list[PatternSignal]:
        """Detect addresses with unusually high betweenness centrality.

        A centrality hub is an address that sits on many shortest paths
        between other addresses, suggesting it acts as a routing or mixing
        node.  We use degree as a fast proxy and supplement with a sampled
        betweenness centrality for the top-degree node.
        """
        degree = PatternAnalyzer._degree(graph.edges)
        if not degree:
            return []

        # Sort deterministically by (degree desc, address asc)
        sorted_nodes = sorted(degree.items(), key=lambda item: (-item[1], item[0]))
        address, max_degree = sorted_nodes[0]

        if max_degree < 6:
            return []

        # Compute betweenness for the hub
        bc = PatternAnalyzer._betweenness_centrality(graph)
        hub_bc = bc.get(address, 0.0)

        score = min(74.0, 36 + max_degree * 4 + hub_bc * 50)
        return [
            PatternSignal(
                name="centrality_hub",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=address,
                evidence=(
                    f"Address has degree {max_degree} (betweenness centrality {hub_bc:.3f}), "
                    f"acting as a central routing node in the transaction graph."
                ),
                confidence=0.72,
                metadata={
                    "degree": max_degree,
                    "betweenness_centrality": round(hub_bc, 4),
                    "in_degree": sum(1 for e in graph.edges if e.target == address),
                    "out_degree": sum(1 for e in graph.edges if e.source == address),
                },
            )
        ]

    # ------------------------------------------------------------------
    # Detector 9: Risk Propagation
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_propagation(graph: InvestigationGraph, target_address: str | None) -> list[PatternSignal]:
        """Detect high-risk labeled addresses within close graph proximity.

        Risk propagation models contagion: if a directly-connected address
        carries a high risk score, that risk "propagates" to the target.
        Score decays with hop distance.
        """
        risky_nodes = [
            node for node in graph.nodes
            if node.risk_score >= 65 and (target_address is None or node.address != target_address)
        ]
        if not risky_nodes:
            return []

        nearest_hop = min(node.hop for node in risky_nodes)
        total_risk = sum(node.risk_score for node in risky_nodes)
        score = max(58.0, 78 - nearest_hop * 8 + min(total_risk / 10, 10))
        return [
            PatternSignal(
                name="risk_propagation",
                severity=RiskLevel.high if score >= 65 else RiskLevel.medium,
                score=round(score, 2),
                subject=target_address or graph.investigation_id,
                evidence=(
                    f"{len(risky_nodes)} high-risk labeled addresses are present within {nearest_hop} hops "
                    f"(aggregate risk score {total_risk:.0f})."
                ),
                confidence=0.82,
                metadata={
                    "risky_node_count": len(risky_nodes),
                    "nearest_hop": nearest_hop,
                    "aggregate_risk_score": round(total_risk, 2),
                    "risky_addresses": [n.address for n in risky_nodes[:5]],
                },
            )
        ]

    # ------------------------------------------------------------------
    # Helper: Build adjacency
    # ------------------------------------------------------------------

    @staticmethod
    def _build_adjacency(graph: InvestigationGraph) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = defaultdict(set)
        for edge in graph.edges:
            adj[edge.source].add(edge.target)
            adj[edge.target].add(edge.source)
        return adj

    # ------------------------------------------------------------------
    # Helper: Degree
    # ------------------------------------------------------------------

    @staticmethod
    def _degree(edges: list[GraphEdge]) -> Counter[str]:
        degree: Counter[str] = Counter()
        for edge in edges:
            degree[edge.source] += 1
            degree[edge.target] += 1
        return degree

    @staticmethod
    def _in_out_degree(edges: list[GraphEdge]) -> tuple[Counter[str], Counter[str]]:
        in_degree: Counter[str] = Counter()
        out_degree: Counter[str] = Counter()
        for edge in edges:
            out_degree[edge.source] += 1
            in_degree[edge.target] += 1
        return in_degree, out_degree

    # ------------------------------------------------------------------
    # Helper: Dust edges
    # ------------------------------------------------------------------

    @staticmethod
    def _dust_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
        now = int(time())
        recent_floor = now - 45 * 24 * 60 * 60
        return [
            edge
            for edge in edges
            if 0 < edge.value_eth <= 0.0001 and (edge.timestamp == 0 or edge.timestamp >= recent_floor)
        ]

    # ------------------------------------------------------------------
    # Network metric: Betweenness centrality (BFS-based, O(VE))
    # ------------------------------------------------------------------

    @staticmethod
    def _betweenness_centrality(graph: InvestigationGraph) -> dict[str, float]:
        """Compute approximate betweenness centrality using BFS shortest paths.

        For graphs larger than 200 nodes we sample at most 50 source nodes
        to keep computation bounded.
        """
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            adj[edge.source].append(edge.target)
            adj[edge.target].append(edge.source)

        nodes = [node.address for node in graph.nodes]
        n = len(nodes)
        if n < 3:
            return {}

        bc: dict[str, float] = {addr: 0.0 for addr in nodes}

        # Sample sources for large graphs
        sources = nodes if n <= 200 else nodes[:50]

        for s in sources:
            # BFS from s
            stack: list[str] = []
            predecessors: dict[str, list[str]] = defaultdict(list)
            sigma: dict[str, float] = defaultdict(float)
            sigma[s] = 1.0
            dist: dict[str, int] = defaultdict(lambda: -1)
            dist[s] = 0
            queue = [s]

            while queue:
                next_queue = []
                for v in queue:
                    stack.append(v)
                    for w in adj[v]:
                        if dist[w] < 0:
                            dist[w] = dist[v] + 1
                            next_queue.append(w)
                        if dist[w] == dist[v] + 1:
                            sigma[w] += sigma[v]
                            predecessors[w].append(v)
                queue = next_queue

            # Back-propagation
            delta: dict[str, float] = defaultdict(float)
            while stack:
                w = stack.pop()
                for v in predecessors[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != s and w in bc:
                    bc[w] += delta[w]

        # Normalize
        norm = 1.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
        for addr in bc:
            bc[addr] *= norm

        return bc

    # ------------------------------------------------------------------
    # Network metric: Connected components
    # ------------------------------------------------------------------

    @staticmethod
    def _connected_components(graph: InvestigationGraph) -> list[set[str]]:
        """Find connected components using BFS."""
        adj: dict[str, set[str]] = defaultdict(set)
        for edge in graph.edges:
            adj[edge.source].add(edge.target)
            adj[edge.target].add(edge.source)

        visited: set[str] = set()
        components: list[set[str]] = []

        for node in graph.nodes:
            if node.address in visited:
                continue
            component: set[str] = set()
            queue = [node.address]
            while queue:
                addr = queue.pop()
                if addr in visited:
                    continue
                visited.add(addr)
                component.add(addr)
                for neighbor in adj[addr]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            components.append(component)

        return components

    # ------------------------------------------------------------------
    # Network metric: Average path length (largest component)
    # ------------------------------------------------------------------

    @staticmethod
    def _avg_path_length_largest_component(
        graph: InvestigationGraph, components: list[set[str]]
    ) -> float:
        """Compute average shortest path length in the largest component."""
        if not components:
            return 0.0

        largest = max(components, key=len)
        if len(largest) < 2:
            return 0.0

        adj: dict[str, list[str]] = defaultdict(list)
        for edge in graph.edges:
            if edge.source in largest and edge.target in largest:
                adj[edge.source].append(edge.target)
                adj[edge.target].append(edge.source)

        # BFS from each node in the component (capped at 50 sources)
        nodes_in = sorted(largest)
        sources = nodes_in[:50]
        total_dist = 0
        total_pairs = 0

        for s in sources:
            dist: dict[str, int] = {s: 0}
            queue = [s]
            while queue:
                next_queue = []
                for v in queue:
                    for w in adj[v]:
                        if w not in dist:
                            dist[w] = dist[v] + 1
                            next_queue.append(w)
                queue = next_queue

            for t in nodes_in:
                if t != s and t in dist:
                    total_dist += dist[t]
                    total_pairs += 1

        return total_dist / max(total_pairs, 1)

    # ------------------------------------------------------------------
    # Network metric: Clustering coefficient
    # ------------------------------------------------------------------

    @staticmethod
    def _clustering_coefficient(graph: InvestigationGraph) -> dict[str, float]:
        """Compute local clustering coefficient for each node.

        CC(v) = 2 * |edges among neighbors| / (deg(v) * (deg(v) - 1))
        """
        adj: dict[str, set[str]] = defaultdict(set)
        for edge in graph.edges:
            adj[edge.source].add(edge.target)
            adj[edge.target].add(edge.source)

        cc: dict[str, float] = {}
        for node in graph.nodes:
            neighbors = adj[node.address]
            k = len(neighbors)
            if k < 2:
                cc[node.address] = 0.0
                continue
            # Count triangles
            triangles = 0
            neighbor_list = sorted(neighbors)
            for i, u in enumerate(neighbor_list):
                for v in neighbor_list[i + 1:]:
                    if v in adj[u]:
                        triangles += 1
            cc[node.address] = (2.0 * triangles) / (k * (k - 1))

        return cc

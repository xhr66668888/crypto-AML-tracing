from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass

from app.connectors.etherscan import EtherscanClient
from app.domain.models import GraphEdge, GraphNode, InvestigationGraph, InvestigationMode
from app.domain.validators import normalize_address


@dataclass
class GraphData:
    """Bounded graph representation with nodes, edges, and aggregated metadata."""

    nodes: list[dict]
    edges: list[dict]
    metadata: dict


@dataclass
class GraphBuildResult:
    graph: InvestigationGraph
    raw_transactions: list[dict]
    graph_data: GraphData | None = None


class GraphBuilder:
    """Bounded BFS graph builder for AML investigations.

    Stable mode: 3 hops, MAX_STABLE_NODES (default 75).
    Experimental mode: 5 hops, MAX_EXPERIMENTAL_NODES (default 160).
    """

    def __init__(self, etherscan: EtherscanClient, max_stable_nodes: int, max_experimental_nodes: int) -> None:
        self.etherscan = etherscan
        self.max_stable_nodes = max_stable_nodes
        self.max_experimental_nodes = max_experimental_nodes

    async def build_from_address(
        self,
        investigation_id: str,
        root_address: str,
        chain_id: str,
        depth: int,
        mode: InvestigationMode,
        token_address: str | None = None,
        asset_symbol: str | None = None,
        root_source: str = "target",
    ) -> GraphBuildResult:
        max_nodes = self.max_experimental_nodes if mode == InvestigationMode.experimental else self.max_stable_nodes
        max_txs_per_address = 10 if mode == InvestigationMode.experimental else 6
        max_hops = 5 if mode == InvestigationMode.experimental else 3
        effective_depth = min(depth, max_hops)

        root = normalize_address(root_address)
        node_map: dict[str, GraphNode] = {
            root: GraphNode(id=root, address=root, label=short_address(root), hop=0, source=root_source)
        }
        edge_map: dict[str, GraphEdge] = {}
        raw_transactions: list[dict] = []

        # Aggregation tracking for GraphData metadata
        first_seen: dict[str, int] = {root: 0}
        last_seen: dict[str, int] = {root: 0}
        total_in: dict[str, float] = defaultdict(float)
        total_out: dict[str, float] = defaultdict(float)
        tx_count: dict[str, int] = Counter()
        risk_tags: dict[str, list[str]] = defaultdict(list)

        queue: deque[tuple[str, int]] = deque([(root, 0)])
        visited: set[str] = set()

        while queue and len(node_map) < max_nodes:
            address, hop = queue.popleft()
            if address in visited or hop >= effective_depth:
                continue
            visited.add(address)

            if token_address:
                txs = await self.etherscan.get_token_transfers(
                    address,
                    token_address=token_address,
                    offset=max_txs_per_address,
                    chain_id=chain_id,
                )
            else:
                txs = await self.etherscan.get_transactions(address, offset=max_txs_per_address, chain_id=chain_id)
            raw_transactions.extend(txs)

            for tx in txs:
                sender = (tx.get("from") or "").lower()
                recipient = (tx.get("to") or "").lower()
                if not sender or not recipient:
                    continue

                timestamp = int(tx.get("timestamp") or 0)
                raw_value = tx.get("value_token") if token_address else tx.get("value_eth")
                value = float(raw_value or 0)
                tx_asset_symbol = str(tx.get("token_symbol") or asset_symbol or "ETH").upper()

                # Update aggregation counters
                total_out[sender] += value
                total_in[recipient] += value
                tx_count[sender] += 1
                tx_count[recipient] += 1

                if timestamp > 0:
                    if sender not in first_seen or timestamp < first_seen[sender]:
                        first_seen[sender] = timestamp
                    if sender not in last_seen or timestamp > last_seen[sender]:
                        last_seen[sender] = timestamp
                    if recipient not in first_seen or timestamp < first_seen[recipient]:
                        first_seen[recipient] = timestamp
                    if recipient not in last_seen or timestamp > last_seen[recipient]:
                        last_seen[recipient] = timestamp

                peer = recipient if sender == address else sender
                if peer not in node_map and len(node_map) < max_nodes:
                    node_map[peer] = GraphNode(id=peer, address=peer, label=short_address(peer), hop=hop + 1)
                    queue.append((peer, hop + 1))

                edge_token = (tx.get("contract_address") or token_address or "").lower()
                edge_id = f"{tx.get('hash', '')}:{sender}:{recipient}:{edge_token}"
                if edge_id not in edge_map:
                    metadata = {
                        "block_number": tx.get("block_number", ""),
                        "is_error": tx.get("is_error", "0"),
                        "source": tx.get("source", "etherscan"),
                        "asset_symbol": tx_asset_symbol,
                        "asset_type": "erc20" if token_address else "native",
                    }
                    if token_address:
                        metadata.update(
                            {
                                "token_address": edge_token,
                                "token_name": tx.get("token_name", ""),
                                "token_decimal": tx.get("token_decimal"),
                                "value_token": value,
                            }
                        )
                    edge_map[edge_id] = GraphEdge(
                        id=edge_id,
                        source=sender,
                        target=recipient,
                        tx_hash=tx.get("hash", ""),
                        timestamp=timestamp,
                        value_eth=value,
                        hop=hop + 1,
                        direction="out" if sender == address else "in",
                        metadata=metadata,
                    )

        graph = InvestigationGraph(
            investigation_id=investigation_id,
            nodes=list(node_map.values()),
            edges=list(edge_map.values()),
        )

        graph_data = self._build_graph_data(node_map, edge_map, first_seen, last_seen, total_in, total_out, tx_count, risk_tags)

        return GraphBuildResult(
            graph=graph,
            raw_transactions=raw_transactions,
            graph_data=graph_data,
        )

    async def build_from_transaction_hash(
        self,
        investigation_id: str,
        tx_hash: str,
        chain_id: str,
        depth: int,
        mode: InvestigationMode,
    ) -> GraphBuildResult:
        tx = await self.etherscan.get_transaction_details(tx_hash)
        root = tx.get("from") or tx.get("to")
        if not root:
            raise ValueError("Transaction did not return a usable sender or recipient.")
        result = await self.build_from_address(investigation_id, root, chain_id=chain_id, depth=depth, mode=mode)
        source = tx.get("from", "").lower()
        target = tx.get("to", "").lower()
        if source and target:
            addresses = {node.address for node in result.graph.nodes}
            if source not in addresses:
                result.graph.nodes.append(GraphNode(id=source, address=source, label=short_address(source), hop=0, source="target_tx"))
            if target not in addresses:
                result.graph.nodes.append(GraphNode(id=target, address=target, label=short_address(target), hop=1, source="target_tx"))
            edge_id = f"{tx_hash}:{source}:{target}"
            if all(edge.id != edge_id for edge in result.graph.edges):
                result.graph.edges.insert(
                    0,
                    GraphEdge(
                        id=edge_id,
                        source=source,
                        target=target,
                        tx_hash=tx_hash,
                        timestamp=int(tx.get("timestamp") or 0),
                        value_eth=float(tx.get("value_eth") or 0),
                        hop=0,
                        direction="target",
                        metadata={"source": "target_tx"},
                    ),
                )
        return result

    @staticmethod
    def _build_graph_data(
        node_map: dict[str, GraphNode],
        edge_map: dict[str, GraphEdge],
        first_seen: dict[str, int],
        last_seen: dict[str, int],
        total_in: dict[str, float],
        total_out: dict[str, float],
        tx_count: dict[str, int],
        risk_tags: dict[str, list[str]],
    ) -> GraphData:
        """Build GraphData with enriched node and edge dicts plus metadata."""
        nodes = []
        for address, node in node_map.items():
            nodes.append({
                "address": address,
                "first_seen": first_seen.get(address, 0),
                "last_seen": last_seen.get(address, 0),
                "total_in": round(total_in.get(address, 0), 8),
                "total_out": round(total_out.get(address, 0), 8),
                "tx_count": tx_count.get(address, 0),
                "risk_tags": risk_tags.get(address, []),
                "hop": node.hop,
                "source": node.source,
                "label": node.label,
            })

        edges = []
        for _edge_id, edge in edge_map.items():
            edges.append({
                "tx_hash": edge.tx_hash,
                "from": edge.source,
                "to": edge.target,
                "value": edge.value_eth,
                "timestamp": edge.timestamp,
                "block_number": edge.metadata.get("block_number", ""),
            })

        max_hop = max((n.hop for n in node_map.values()), default=0)
        metadata = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "max_hop": max_hop,
            "total_value_eth": round(sum(e.value_eth for e in edge_map.values()), 8),
        }

        return GraphData(nodes=nodes, edges=edges, metadata=metadata)


def short_address(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}"

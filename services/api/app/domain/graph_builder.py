from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.connectors.etherscan import EtherscanClient
from app.domain.models import GraphEdge, GraphNode, InvestigationGraph, InvestigationMode
from app.domain.validators import normalize_address


@dataclass
class GraphBuildResult:
    graph: InvestigationGraph
    raw_transactions: list[dict]


class GraphBuilder:
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
    ) -> GraphBuildResult:
        max_nodes = self.max_experimental_nodes if mode == InvestigationMode.experimental else self.max_stable_nodes
        max_txs_per_address = 10 if mode == InvestigationMode.experimental else 6
        root = normalize_address(root_address)
        nodes: dict[str, GraphNode] = {
            root: GraphNode(id=root, address=root, label=short_address(root), hop=0, source="target")
        }
        edges: dict[str, GraphEdge] = {}
        raw_transactions: list[dict] = []
        queue: deque[tuple[str, int]] = deque([(root, 0)])
        visited: set[str] = set()

        while queue and len(nodes) < max_nodes:
            address, hop = queue.popleft()
            if address in visited or hop >= depth:
                continue
            visited.add(address)
            txs = await self.etherscan.get_transactions_for_address(address, offset=max_txs_per_address)
            raw_transactions.extend(txs)
            for tx in txs:
                sender = (tx.get("from") or "").lower()
                recipient = (tx.get("to") or "").lower()
                if not sender or not recipient:
                    continue
                peer = recipient if sender == address else sender
                if peer not in nodes and len(nodes) < max_nodes:
                    nodes[peer] = GraphNode(id=peer, address=peer, label=short_address(peer), hop=hop + 1)
                    queue.append((peer, hop + 1))
                edge_id = f"{tx.get('hash', '')}:{sender}:{recipient}"
                if edge_id not in edges:
                    edges[edge_id] = GraphEdge(
                        id=edge_id,
                        source=sender,
                        target=recipient,
                        tx_hash=tx.get("hash", ""),
                        timestamp=int(tx.get("timestamp") or 0),
                        value_eth=float(tx.get("value_eth") or 0),
                        hop=hop + 1,
                        direction="out" if sender == address else "in",
                        metadata={
                            "block_number": tx.get("block_number", ""),
                            "is_error": tx.get("is_error", "0"),
                            "source": tx.get("source", "etherscan"),
                        },
                    )

        return GraphBuildResult(
            graph=InvestigationGraph(investigation_id=investigation_id, nodes=list(nodes.values()), edges=list(edges.values())),
            raw_transactions=raw_transactions,
        )

    async def build_from_transaction_hash(
        self,
        investigation_id: str,
        tx_hash: str,
        chain_id: str,
        depth: int,
        mode: InvestigationMode,
    ) -> GraphBuildResult:
        tx = await self.etherscan.get_transaction_by_hash(tx_hash)
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


def short_address(address: str) -> str:
    return f"{address[:6]}...{address[-4:]}"

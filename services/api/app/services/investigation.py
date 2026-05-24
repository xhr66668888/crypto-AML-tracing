from __future__ import annotations

from app.domain.graph_builder import GraphBuilder
from app.domain.models import InvestigationCreate, TargetType
from app.domain.scoring import RiskScoringEngine
from app.domain.validators import detect_target_type, normalize_address, normalize_hash
from app.storage.base import StorageAdapter


class InvestigationService:
    def __init__(self, store: StorageAdapter, graph_builder: GraphBuilder, scoring: RiskScoringEngine) -> None:
        self.store = store
        self.graph_builder = graph_builder
        self.scoring = scoring

    async def create_and_run(self, payload: InvestigationCreate):
        target_type_value = detect_target_type(payload.target)
        target_type = TargetType(target_type_value)
        normalized_target = normalize_address(payload.target) if target_type == TargetType.address else normalize_hash(payload.target)
        payload = payload.model_copy(update={"target": normalized_target})
        record = self.store.create_investigation(payload, target_type)

        try:
            if target_type == TargetType.address:
                result = await self.graph_builder.build_from_address(
                    record.status.id,
                    normalized_target,
                    chain_id=payload.chain_id,
                    depth=payload.depth,
                    mode=payload.mode,
                    asset=payload.asset.value,
                    token_contract_address=payload.token_contract_address,
                )
            else:
                result = await self.graph_builder.build_from_transaction_hash(
                    record.status.id,
                    normalized_target,
                    chain_id=payload.chain_id,
                    depth=payload.depth,
                    mode=payload.mode,
                    asset=payload.asset.value,
                    token_contract_address=payload.token_contract_address,
                )
            risk = await self.scoring.score_graph(
                record.status.id,
                result.graph,
                chain_id=payload.chain_id,
                watchlist=self.store.get_watchlist_map(),
            )
            self.store.complete_investigation(record.status.id, result.graph, risk)
        except Exception as exc:  # noqa: BLE001 - keep MVP jobs observable.
            self.store.fail_investigation(record.status.id, str(exc))
        return self.store.get_investigation(record.status.id)

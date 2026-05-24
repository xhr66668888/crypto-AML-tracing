from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domain.models import GraphNode, InvestigationGraph, PreTransactionScreeningCreate, RiskLevel, RiskResponse
from app.domain.patterns import PatternAnalyzer
from app.services.screening import ScreeningService
from app.storage.memory import InMemoryStore


TX_HASH = "0x" + "9" * 64
COUNTERPARTY_ADDRESS = "0x" + "22" * 20
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


def test_pre_transaction_request_rejects_tx_hash_input():
    with pytest.raises(ValidationError):
        PreTransactionScreeningCreate(tx_hash=TX_HASH, amount=123)


@pytest.mark.asyncio
async def test_pre_transaction_screening_uses_counterparty_address_only():
    graph_builder = _CounterpartyGraphBuilder()
    service = ScreeningService(
        InMemoryStore(),
        graph_builder,  # type: ignore[arg-type]
        _LowRiskScoring(),
        PatternAnalyzer(),
    )

    response = await service.screen_transaction(
        PreTransactionScreeningCreate(
            asset="USDC",
            direction="outbound",
            counterparty_address=COUNTERPARTY_ADDRESS,
            amount=123.45,
        )
    )

    assert response.counterparty_address == COUNTERPARTY_ADDRESS
    assert response.from_address is None
    assert response.to_address == COUNTERPARTY_ADDRESS
    assert response.asset == "USDC"
    assert response.amount == 123.45
    assert response.graph_investigation_id is None
    assert graph_builder.calls == [
        (COUNTERPARTY_ADDRESS, USDC_CONTRACT, "USDC", "screening_counterparty"),
    ]


def test_screening_endpoint_rejects_tx_hash_only_payload():
    import app.main as main

    response = TestClient(main.app).post(
        "/api/v1/screening/pre-transactions",
        json={"tx_hash": TX_HASH},
    )

    assert response.status_code == 422


def test_address_analysis_endpoint_accepts_transaction_hash():
    import app.main as main

    previous_etherscan_demo_mode = main.etherscan.demo_mode
    previous_goplus_demo_mode = main.goplus.demo_mode
    try:
        main.etherscan.demo_mode = True
        main.goplus.demo_mode = True
        response = TestClient(main.app).post(
            "/api/v1/investigations",
            json={"target": TX_HASH, "chain_id": "1", "depth": 2, "mode": "stable"},
        )
    finally:
        main.etherscan.demo_mode = previous_etherscan_demo_mode
        main.goplus.demo_mode = previous_goplus_demo_mode

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["target_type"] == "transaction_hash"
    assert payload["graph"]["nodes"]
    assert payload["risk"]["final_risk_score"] >= 0


class _CounterpartyGraphBuilder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, str | None, str]] = []

    async def build_from_address(
        self,
        investigation_id: str,
        root_address: str,
        chain_id: str,
        depth: int,
        mode,
        token_address: str | None = None,
        asset_symbol: str | None = None,
        root_source: str = "target",
    ):
        self.calls.append((root_address, token_address, asset_symbol, root_source))
        graph = InvestigationGraph(
            investigation_id=investigation_id,
            nodes=[GraphNode(id=root_address, address=root_address, label="root", hop=0, source=root_source)],
            edges=[],
        )
        return SimpleNamespace(graph=graph)


class _LowRiskScoring:
    async def score_graph(self, investigation_id: str, graph: InvestigationGraph, chain_id: str, watchlist: dict):
        return RiskResponse(
            investigation_id=investigation_id,
            rule_score=0,
            raindrop_score=0,
            final_risk_score=0,
            final_risk_level=RiskLevel.low,
            findings=[],
            top_risk_paths=[],
            feature_summary={},
            pattern_signals=[],
            source_hits=[],
        )

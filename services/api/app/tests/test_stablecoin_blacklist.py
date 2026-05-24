from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.connectors.base import ConnectorError
from app.connectors.stablecoin_blacklist import (
    CIRCLE_USDC_ETH_CONTRACT,
    TETHER_USDT_ETH_CONTRACT,
    StablecoinBlacklistCheck,
    StablecoinBlacklistClient,
)
from app.domain.models import (
    GraphNode,
    InvestigationGraph,
    RiskDisposition,
    RiskLevel,
    RiskResponse,
    ScreeningTransactionCreate,
)
from app.domain.patterns import PatternAnalyzer
from app.services.screening import ScreeningService
from app.storage.memory import InMemoryStore


BLACKLISTED_ADDRESS = "0x" + "12" * 20
CLEAN_ADDRESS = "0x" + "34" * 20
USDC_BLACKLISTED_ADDRESS = "0xaa05f7c7eb9af63d6cc03c36c4f4ef6c37431ee0"


@pytest.mark.asyncio
async def test_usdc_blacklist_rpc_call_returns_true():
    seen: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.update(body)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": "0x" + "0" * 63 + "1"},
        )

    client = StablecoinBlacklistClient(
        rpc_url="https://eth-mainnet.g.alchemy.com/public",
        demo_mode=False,
        _transport=httpx.MockTransport(handler),
    )

    result = await client.check_address("USDC", BLACKLISTED_ADDRESS, chain_id="1")

    assert result is not None
    assert result.blacklisted is True
    assert result.provider == "circle_blacklist"
    assert result.token_address == CIRCLE_USDC_ETH_CONTRACT
    assert seen["method"] == "eth_call"
    call = seen["params"][0]
    assert call["to"] == CIRCLE_USDC_ETH_CONTRACT
    assert call["data"].startswith("0xfe575a87")
    assert call["data"].endswith(BLACKLISTED_ADDRESS.removeprefix("0x"))


@pytest.mark.asyncio
async def test_usdt_blacklist_rpc_call_returns_false():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": "0x" + "0" * 64},
        )

    client = StablecoinBlacklistClient(
        rpc_url="https://eth-mainnet.g.alchemy.com/public",
        demo_mode=False,
        _transport=httpx.MockTransport(handler),
    )

    result = await client.check_address("USDT", CLEAN_ADDRESS, chain_id="1")

    assert result is not None
    assert result.blacklisted is False
    assert result.provider == "tether_blacklist"
    assert result.token_address == TETHER_USDT_ETH_CONTRACT
    assert result.raw_payload["method"] == "isBlackListed(address)"


@pytest.mark.asyncio
async def test_usdc_blacklist_can_resolve_by_token_address():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": "0x" + "0" * 63 + "1"},
        )

    client = StablecoinBlacklistClient(
        rpc_url="https://eth-mainnet.g.alchemy.com/public",
        demo_mode=False,
        _transport=httpx.MockTransport(handler),
    )

    result = await client.check_address(
        "USD COIN",
        BLACKLISTED_ADDRESS,
        chain_id="1",
        token_address=CIRCLE_USDC_ETH_CONTRACT.lower(),
    )

    assert result is not None
    assert result.provider == "circle_blacklist"
    assert result.blacklisted is True


@pytest.mark.asyncio
async def test_rpc_timeout_raises_retryable_connector_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("boom")

    client = StablecoinBlacklistClient(
        rpc_url="https://eth-mainnet.g.alchemy.com/public",
        demo_mode=False,
        max_retries=1,
        _transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ConnectorError) as exc_info:
        await client.check_address("USDC", CLEAN_ADDRESS, chain_id="1")

    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_screening_circle_blacklist_hit_forces_manual_hold():
    service = ScreeningService(
        InMemoryStore(),
        _GraphBuilder(),
        _LowRiskScoring(),
        PatternAnalyzer(),
        _FakeStablecoinClient(blacklisted_address=BLACKLISTED_ADDRESS),
    )

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="USDC",
            direction="outbound",
            counterparty_address=BLACKLISTED_ADDRESS,
            amount=10,
        )
    )

    assert response.disposition == RiskDisposition.hold_for_manual_review
    assert response.risk_level == RiskLevel.critical
    assert any(hit.category == "circle_blacklist" and hit.direct_hit for hit in response.source_hits)
    assert any("USDC issuer blacklist check" in item for item in response.evidence_summary)


@pytest.mark.asyncio
async def test_screening_rpc_failure_returns_degraded_review_signal():
    service = ScreeningService(
        InMemoryStore(),
        _GraphBuilder(),
        _LowRiskScoring(),
        PatternAnalyzer(),
        _FailingStablecoinClient(),
    )

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="USDC",
            direction="outbound",
            counterparty_address=BLACKLISTED_ADDRESS,
            amount=10,
        )
    )

    assert response.disposition == RiskDisposition.review
    assert any(signal.name == "stablecoin_blacklist_unavailable" for signal in response.pattern_signals)
    assert any("stablecoin blacklist check unavailable" in item for item in response.evidence_summary)


def test_screening_endpoint_usdc_blacklist_hit_forces_manual_hold():
    import app.main as main

    previous_demo_mode = main.stablecoin_blacklist.demo_mode
    previous_transport = main.stablecoin_blacklist._transport
    previous_etherscan_demo_mode = main.etherscan.demo_mode
    previous_goplus_demo_mode = main.goplus.demo_mode

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        data = body["params"][0]["data"].lower()
        blacklisted = data.endswith(USDC_BLACKLISTED_ADDRESS.removeprefix("0x"))
        result = "0x" + "0" * 63 + ("1" if blacklisted else "0")
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    try:
        main.stablecoin_blacklist.demo_mode = False
        main.stablecoin_blacklist._transport = httpx.MockTransport(handler)
        main.etherscan.demo_mode = True
        main.goplus.demo_mode = True
        client = TestClient(main.app)
        response = client.post(
            "/api/v1/screening/pre-transactions",
            json={
                "asset": "USDC",
                "direction": "outbound",
                "counterparty_address": USDC_BLACKLISTED_ADDRESS,
                "amount": 100,
            },
        )
    finally:
        main.stablecoin_blacklist.demo_mode = previous_demo_mode
        main.stablecoin_blacklist._transport = previous_transport
        main.etherscan.demo_mode = previous_etherscan_demo_mode
        main.goplus.demo_mode = previous_goplus_demo_mode

    assert response.status_code == 200
    payload = response.json()
    assert payload["disposition"] == "hold_for_manual_review"
    assert payload["risk_level"] == "critical"
    assert any(hit["category"] == "circle_blacklist" and hit["direct_hit"] for hit in payload["source_hits"])
    assert any("USDC issuer blacklist check" in item for item in payload["evidence_summary"])


def test_screening_endpoint_usdt_blacklist_hit_forces_manual_hold():
    import app.main as main

    previous_demo_mode = main.stablecoin_blacklist.demo_mode
    previous_transport = main.stablecoin_blacklist._transport
    previous_etherscan_demo_mode = main.etherscan.demo_mode
    previous_goplus_demo_mode = main.goplus.demo_mode

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        data = body["params"][0]["data"].lower()
        blacklisted = data.endswith(BLACKLISTED_ADDRESS.removeprefix("0x"))
        result = "0x" + "0" * 63 + ("1" if blacklisted else "0")
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    try:
        main.stablecoin_blacklist.demo_mode = False
        main.stablecoin_blacklist._transport = httpx.MockTransport(handler)
        main.etherscan.demo_mode = True
        main.goplus.demo_mode = True
        client = TestClient(main.app)
        response = client.post(
            "/api/v1/screening/pre-transactions",
            json={
                "asset": "USDT",
                "direction": "inbound",
                "counterparty_address": BLACKLISTED_ADDRESS,
                "amount": 100,
            },
        )
    finally:
        main.stablecoin_blacklist.demo_mode = previous_demo_mode
        main.stablecoin_blacklist._transport = previous_transport
        main.etherscan.demo_mode = previous_etherscan_demo_mode
        main.goplus.demo_mode = previous_goplus_demo_mode

    assert response.status_code == 200
    payload = response.json()
    assert payload["disposition"] == "hold_for_manual_review"
    assert payload["risk_level"] == "critical"
    assert any(hit["category"] == "tether_blacklist" and hit["direct_hit"] for hit in payload["source_hits"])
    assert any("USDT issuer blacklist check" in item for item in payload["evidence_summary"])


class _GraphBuilder:
    async def build_from_address(
        self,
        investigation_id: str,
        target: str,
        chain_id: str,
        depth: int,
        mode,
        token_address: str | None = None,
        asset_symbol: str | None = None,
        root_source: str = "target",
    ):
        graph = InvestigationGraph(
            investigation_id=investigation_id,
            nodes=[
                GraphNode(
                    id=target,
                    address=target,
                    label="target",
                    hop=0,
                    source=root_source,
                    metadata={"token_address": token_address, "asset_symbol": asset_symbol},
                )
            ],
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


class _FakeStablecoinClient:
    def __init__(self, blacklisted_address: str) -> None:
        self.blacklisted_address = blacklisted_address.lower()

    async def check_address(
        self,
        token_symbol: str,
        address: str,
        chain_id: str = "1",
        token_address: str | None = None,
    ):
        blacklisted = address.lower() == self.blacklisted_address
        return StablecoinBlacklistCheck(
            provider="circle_blacklist",
            category="circle_blacklist",
            token_symbol=token_symbol,
            token_address=CIRCLE_USDC_ETH_CONTRACT,
            address=address.lower(),
            blacklisted=blacklisted,
            checked_at=datetime.now(UTC),
            evidence=f"{token_symbol} issuer blacklist check: {address.lower()} is blacklisted by circle_blacklist.",
            raw_payload={"method": "isBlacklisted(address)", "token_address": token_address},
        )


class _FailingStablecoinClient:
    async def check_address(
        self,
        token_symbol: str,
        address: str,
        chain_id: str = "1",
        token_address: str | None = None,
    ):
        raise ConnectorError(provider="circle_blacklist", message=f"Alchemy RPC timeout for {token_address}", retryable=True)

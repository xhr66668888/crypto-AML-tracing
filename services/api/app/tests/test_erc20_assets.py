from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.domain.assets import ETH_MAINNET_TOKENS, resolve_screening_asset
from app.domain.graph_builder import GraphBuilder
from app.domain.models import (
    GraphNode,
    InvestigationGraph,
    InvestigationMode,
    RiskDisposition,
    RiskLevel,
    RiskResponse,
    ScreeningTransactionCreate,
)
from app.domain.patterns import PatternAnalyzer
from app.services.screening import ScreeningService
from app.storage.memory import InMemoryStore


ROOT = "0x" + "a" * 40
PEER = "0x" + "b" * 40
CUSTOM_TOKEN = "0x" + "c" * 40


def test_known_mainnet_erc20_assets_resolve_without_enum_limit():
    for symbol in ("USDT", "USDC", "DAI", "WETH", "WBTC"):
        asset = resolve_screening_asset(symbol, chain_id="1")
        assert asset.symbol == symbol
        assert asset.asset_type == "erc20"
        assert asset.token_address == ETH_MAINNET_TOKENS[symbol].token_address


def test_custom_erc20_requires_chain_id_and_token_address():
    payload = ScreeningTransactionCreate(
        asset="pepe",
        asset_type="erc20",
        token_address=CUSTOM_TOKEN.upper(),
        counterparty_address=PEER,
        amount=10,
    )
    asset = resolve_screening_asset(
        payload.asset,
        chain_id=payload.chain_id,
        asset_type=payload.asset_type,
        token_address=payload.token_address,
    )

    assert payload.asset == "PEPE"
    assert asset.symbol == "PEPE"
    assert asset.token_address == CUSTOM_TOKEN


def test_unknown_symbol_without_token_address_is_rejected():
    with pytest.raises(ValueError, match="provide token_address"):
        resolve_screening_asset("PEPE", chain_id="1")


def test_screening_endpoint_accepts_builtin_dai_asset():
    import app.main as main

    previous_etherscan_demo_mode = main.etherscan.demo_mode
    previous_goplus_demo_mode = main.goplus.demo_mode
    previous_stablecoin_demo_mode = main.stablecoin_blacklist.demo_mode
    try:
        main.etherscan.demo_mode = True
        main.goplus.demo_mode = True
        main.stablecoin_blacklist.demo_mode = True
        response = TestClient(main.app).post(
            "/api/v1/screening/pre-transactions",
            json={
                "asset": "DAI",
                "direction": "outbound",
                "counterparty_address": PEER,
                "amount": 100,
            },
        )
    finally:
        main.etherscan.demo_mode = previous_etherscan_demo_mode
        main.goplus.demo_mode = previous_goplus_demo_mode
        main.stablecoin_blacklist.demo_mode = previous_stablecoin_demo_mode

    assert response.status_code == 200
    payload = response.json()
    assert payload["asset"] == "DAI"
    assert payload["counterparty_address"] == PEER
    assert payload["graph_investigation_id"] is None


@pytest.mark.asyncio
async def test_graph_builder_uses_erc20_token_transfers_for_token_screening():
    etherscan = _TokenTransferEtherscan()
    builder = GraphBuilder(etherscan, max_stable_nodes=10, max_experimental_nodes=20)  # type: ignore[arg-type]

    result = await builder.build_from_address(
        "erc20-graph",
        ROOT,
        chain_id="1",
        depth=1,
        mode=InvestigationMode.stable,
        token_address=CUSTOM_TOKEN,
        asset_symbol="PEPE",
    )

    assert etherscan.token_calls == [(ROOT, CUSTOM_TOKEN, "1")]
    assert len(result.graph.edges) == 1
    edge = result.graph.edges[0]
    assert edge.value_eth == 25.5
    assert edge.metadata["asset_type"] == "erc20"
    assert edge.metadata["asset_symbol"] == "PEPE"
    assert edge.metadata["token_address"] == CUSTOM_TOKEN


@pytest.mark.asyncio
async def test_screening_custom_token_risk_is_normalized_into_source_hits():
    graph_builder = _ScreeningGraphBuilder()
    service = ScreeningService(
        InMemoryStore(),
        graph_builder,  # type: ignore[arg-type]
        _LowRiskScoring(),
        PatternAnalyzer(),
        token_security=_FlaggedTokenSecurity(),  # type: ignore[arg-type]
    )

    response = await service.screen_transaction(
        ScreeningTransactionCreate(
            asset="pepe",
            asset_type="erc20",
            token_address=CUSTOM_TOKEN,
            direction="outbound",
            counterparty_address=PEER,
            amount=10,
        )
    )

    assert response.asset == "PEPE"
    assert response.risk_level == RiskLevel.critical
    assert response.disposition == RiskDisposition.hold_for_manual_review
    assert graph_builder.token_address == CUSTOM_TOKEN
    hit = next(hit for hit in response.source_hits if hit.source == "goplus_token_security")
    assert hit.category == "token_contract_risk"
    assert hit.direct_hit is False
    assert "honeypot behavior" in hit.evidence


class _TokenTransferEtherscan:
    def __init__(self) -> None:
        self.token_calls: list[tuple[str, str | None, str | None]] = []

    async def get_token_transfers(self, address, token_address=None, page=1, offset=25, chain_id=None):
        self.page = page
        self.offset = offset
        self.token_calls.append((address, token_address, chain_id))
        return [
            {
                "hash": "0x" + "1" * 64,
                "from": address,
                "to": PEER,
                "value_token": 25.5,
                "timestamp": 1700000000,
                "block_number": "19000000",
                "is_error": "0",
                "contract_address": token_address,
                "token_name": "Pepe",
                "token_symbol": "PEPE",
                "token_decimal": 18,
                "source": "etherscan_tokentx",
            }
        ]

    async def get_transactions(self, address, page=1, offset=25, chain_id=None):
        raise AssertionError(f"ERC-20 graph should use token transfers, not txlist for {address}:{page}:{offset}:{chain_id}.")


class _ScreeningGraphBuilder:
    def __init__(self) -> None:
        self.token_address: str | None = None

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
        self.token_address = token_address
        graph = InvestigationGraph(
            investigation_id=investigation_id,
            nodes=[
                GraphNode(
                    id=target,
                    address=target,
                    label="target",
                    hop=0,
                    source=root_source,
                    metadata={"depth": depth, "chain_id": chain_id, "asset_symbol": asset_symbol, "mode": str(mode)},
                ),
                GraphNode(id=ROOT, address=ROOT, label="from", hop=0, source="screening_party"),
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
            feature_summary={"chain_id": chain_id, "watchlist_size": len(watchlist), "node_count": len(graph.nodes)},
            pattern_signals=[],
            source_hits=[],
        )


class _FlaggedTokenSecurity:
    async def get_token_security(self, token_address: str, chain_id: str = "1"):
        return {
            "token_address": token_address,
            "chain_id": chain_id,
            "is_honeypot": "1",
            "source": "fixture-goplus",
        }

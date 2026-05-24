"""Tests for connector-engineer owned connectors: Etherscan, GoPlus, DeepSeek.

Covers:
- Demo-mode deterministic fixtures
- ConnectorError structure
- Timeout handling
- Retry logic (bounded back-off)
- Cache behaviour (Etherscan)
- Real-mode graceful failure when keys are missing
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.connectors.base import ConnectorError, new_request_id
from app.connectors.deepseek import DeepSeekClient
from app.connectors.etherscan import EtherscanClient, _Cache
from app.connectors.goplus import GoPlusClient


# ═══════════════════════════════════════════════════════════════════════════════
# ConnectorError
# ═══════════════════════════════════════════════════════════════════════════════


class TestConnectorError:
    def test_basic_fields(self):
        err = ConnectorError(provider="etherscan", message="boom")
        assert err.provider == "etherscan"
        assert err.message == "boom"
        assert err.status_code is None
        assert err.request_id is None
        assert err.retryable is False

    def test_str_with_status_code(self):
        err = ConnectorError(provider="goplus", status_code=503, message="Service unavailable", request_id="abc123")
        s = str(err)
        assert "[goplus]" in s
        assert "HTTP 503" in s
        assert "Service unavailable" in s
        assert "abc123" in s

    def test_str_without_status_code(self):
        err = ConnectorError(provider="deepseek", message="Timeout")
        s = str(err)
        assert "[deepseek]" in s
        assert "Timeout" in s
        assert "HTTP" not in s

    def test_is_exception(self):
        err = ConnectorError(provider="test", message="fail")
        assert isinstance(err, Exception)
        with pytest.raises(ConnectorError):
            raise err

    def test_raw_payload(self):
        raw = {"status": "0", "message": "NOTOK"}
        err = ConnectorError(provider="etherscan", message="API error", raw=raw)
        assert err.raw == raw

    def test_retryable_flag(self):
        err = ConnectorError(provider="test", message="retry me", retryable=True)
        assert err.retryable is True


class TestNewRequestId:
    def test_returns_hex_string(self):
        rid = new_request_id()
        assert isinstance(rid, str)
        assert len(rid) == 12
        int(rid, 16)  # should not raise

    def test_unique(self):
        ids = {new_request_id() for _ in range(100)}
        assert len(ids) == 100  # probabilistically guaranteed


# ═══════════════════════════════════════════════════════════════════════════════
# EtherscanClient
# ═══════════════════════════════════════════════════════════════════════════════


class TestEtherscanDemoMode:
    """Demo mode must work without API keys and return deterministic data."""

    @pytest.fixture
    def client(self):
        return EtherscanClient(api_key="", base_url="", demo_mode=True)

    @pytest.mark.asyncio
    async def test_get_transactions_deterministic(self, client: EtherscanClient):
        addr = "0x" + "a" * 40
        txs1 = await client.get_transactions(addr)
        txs2 = await client.get_transactions(addr)
        assert txs1 == txs2
        assert len(txs1) == 8  # default offset capped at 8
        for tx in txs1:
            assert "hash" in tx
            assert "from" in tx
            assert "to" in tx
            assert "value_eth" in tx
            assert tx["source"] == "demo"

    @pytest.mark.asyncio
    async def test_get_transaction_details_deterministic(self, client: EtherscanClient):
        tx_hash = "0x" + "b" * 64
        detail1 = await client.get_transaction_details(tx_hash)
        detail2 = await client.get_transaction_details(tx_hash)
        assert detail1 == detail2
        assert detail1["hash"] == tx_hash
        assert detail1["value_eth"] == 4.2
        assert detail1["source"] == "demo"

    @pytest.mark.asyncio
    async def test_different_addresses_yield_different_data(self, client: EtherscanClient):
        addr1 = "0x" + "a" * 40
        addr2 = "0x" + "b" * 40
        txs1 = await client.get_transactions(addr1)
        txs2 = await client.get_transactions(addr2)
        assert txs1 != txs2

    @pytest.mark.asyncio
    async def test_get_token_transfers_deterministic(self, client: EtherscanClient):
        addr = "0x" + "a" * 40
        token = "0x" + "d" * 40
        txs1 = await client.get_token_transfers(addr, token_address=token)
        txs2 = await client.get_token_transfers(addr, token_address=token)
        assert txs1 == txs2
        assert len(txs1) == 8
        assert txs1[0]["contract_address"] == token
        assert txs1[0]["source"] == "demo_tokentx"

    @pytest.mark.asyncio
    async def test_get_screening_transaction_demo_eth(self, client: EtherscanClient):
        tx_hash = "0x" + "f" * 64
        result = await client.get_screening_transaction(tx_hash)

        assert result["tx_hash"] == tx_hash
        assert result["asset"] == "ETH"
        assert result["asset_type"] == "native"
        assert result["from_address"].startswith("0x")
        assert result["to_address"].startswith("0x")


class TestEtherscanRealModeErrors:
    """Real mode must produce structured ConnectorError on failures."""

    @pytest.mark.asyncio
    async def test_timeout_produces_connector_error(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=0.01,
            max_retries=1,
        )
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("simulated timeout")):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_transactions("0x" + "a" * 40)
        err = exc_info.value
        assert err.provider == "etherscan"
        assert err.retryable is True
        assert "Timeout" in err.message

    @pytest.mark.asyncio
    async def test_429_produces_retryable_connector_error(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_transactions("0x" + "a" * 40)
        err = exc_info.value
        assert err.status_code == 429
        assert err.retryable is True

    @pytest.mark.asyncio
    async def test_500_produces_retryable_connector_error(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_transactions("0x" + "a" * 40)
        err = exc_info.value
        assert err.status_code == 500
        assert err.retryable is True

    @pytest.mark.asyncio
    async def test_empty_payload_produces_structured_error(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "0", "message": "NOTOK", "result": "No transactions found"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_transactions("0x" + "a" * 40)
        err = exc_info.value
        assert err.status_code == 200
        assert "Etherscan API error" in err.message

    @pytest.mark.asyncio
    async def test_real_mode_without_key_falls_back_to_demo(self):
        """When api_key is empty and demo_mode is False, should still use demo."""
        client = EtherscanClient(api_key="", base_url="", demo_mode=False)
        # The code checks `if self.demo_mode or not self.api_key`, so empty key => demo
        txs = await client.get_transactions("0x" + "a" * 40)
        assert len(txs) > 0
        assert txs[0]["source"] == "demo"

    @pytest.mark.asyncio
    async def test_get_token_transfers_calls_tokentx_with_contract(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        token = "0x" + "d" * 40
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "0xabc",
                    "from": "0x1111111111111111111111111111111111111111",
                    "to": "0x2222222222222222222222222222222222222222",
                    "value": "123450000",
                    "timeStamp": "1700000000",
                    "blockNumber": "19000000",
                    "isError": "0",
                    "contractAddress": token,
                    "tokenName": "USD Coin",
                    "tokenSymbol": "USDC",
                    "tokenDecimal": "6",
                }
            ],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            result = await client.get_token_transfers("0x" + "a" * 40, token_address=token, chain_id="1")

        params = mock_get.call_args.kwargs["params"]
        assert params["action"] == "tokentx"
        assert params["contractaddress"] == token
        assert result[0]["value_token"] == 123.45
        assert result[0]["token_symbol"] == "USDC"

    @pytest.mark.asyncio
    async def test_get_screening_transaction_decodes_erc20_transfer_log(self):
        client = EtherscanClient(api_key="test-key", demo_mode=False, max_retries=1)
        tx_hash = "0x" + "9" * 64
        token = "0x" + "a0" * 20
        sender = "0x" + "11" * 20
        recipient = "0x" + "22" * 20
        client._get = AsyncMock(
            side_effect=[
                {
                    "result": {
                        "from": sender,
                        "to": token,
                        "value": "0x0",
                    }
                },
                {
                    "result": {
                        "logs": [
                            {
                                "address": token,
                                "topics": [
                                    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                                    _topic_for_address(sender),
                                    _topic_for_address(recipient),
                                ],
                                "data": hex(123_450_000),
                            }
                        ]
                    }
                },
                {"result": hex(6)},
                {"result": _abi_string("USDC")},
                {"result": _abi_string("USD Coin")},
            ]
        )

        result = await client.get_screening_transaction(tx_hash, chain_id="1")

        assert result["asset"] == "USDC"
        assert result["asset_type"] == "erc20"
        assert result["token_address"] == token
        assert result["from_address"] == sender
        assert result["to_address"] == recipient
        assert result["amount"] == 123.45

    @pytest.mark.asyncio
    async def test_get_transaction_details_uses_block_timestamp(self):
        client = EtherscanClient(api_key="test-key", demo_mode=False, max_retries=1)
        tx_hash = "0x" + "8" * 64
        sender = "0x" + "11" * 20
        recipient = "0x" + "22" * 20
        client._get = AsyncMock(
            side_effect=[
                {
                    "result": {
                        "from": sender,
                        "to": recipient,
                        "value": "0xde0b6b3a7640000",
                        "blockNumber": "0x1234",
                    }
                },
                {"result": {"timestamp": hex(1_700_000_000)}},
            ]
        )

        result = await client.get_transaction_details(tx_hash, chain_id="1")

        assert result["from"] == sender
        assert result["to"] == recipient
        assert result["value_eth"] == 1
        assert result["timestamp"] == 1_700_000_000
        assert result["block_number"] == "0x1234"


class TestEtherscanRetries:
    """Retry logic with exponential back-off."""

    @pytest.mark.asyncio
    async def test_retries_on_timeout_then_success(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=3,
        )
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "0xabc",
                    "from": "0x1111111111111111111111111111111111111111",
                    "to": "0x2222222222222222222222222222222222222222",
                    "value": "1000000000000000000",
                    "timeStamp": "1700000000",
                    "blockNumber": "19000000",
                    "isError": "0",
                }
            ],
        }

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("simulated timeout")
            return success_response

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await client.get_transactions("0x" + "a" * 40)

        assert call_count == 3
        assert len(result) == 1
        assert result[0]["source"] == "etherscan"

    @pytest.mark.asyncio
    async def test_retries_rate_limit_payload_then_success(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=2,
        )
        rate_limited = MagicMock(spec=httpx.Response)
        rate_limited.status_code = 200
        rate_limited.json.return_value = {
            "status": "0",
            "message": "NOTOK",
            "result": "Max calls per sec rate limit reached (3/sec)",
        }
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "0xabc",
                    "from": "0x1111111111111111111111111111111111111111",
                    "to": "0x2222222222222222222222222222222222222222",
                    "value": "1000000000000000000",
                    "timeStamp": "1700000000",
                    "blockNumber": "19000000",
                    "isError": "0",
                }
            ],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[rate_limited, success_response]) as mock_get:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.get_transactions("0x" + "a" * 40)

        assert mock_get.call_count == 2
        assert len(result) == 1
        assert result[0]["source"] == "etherscan"

    @pytest.mark.asyncio
    async def test_retries_bounded(self):
        """All retries exhausted raises ConnectorError."""
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=0.01,
            max_retries=2,
        )
        with pytest.raises(ConnectorError) as exc_info:
            await client.get_transactions("0x" + "a" * 40)
        assert "attempt 2/2" in exc_info.value.message


class TestEtherscanCache:
    """Cache returns cached data on second call."""

    @pytest.mark.asyncio
    async def test_cache_returns_same_data(self):
        client = EtherscanClient(
            api_key="test-key",
            base_url="https://api.etherscan.io/v2/api",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "1",
            "message": "OK",
            "result": [
                {
                    "hash": "0xabc",
                    "from": "0x1111111111111111111111111111111111111111",
                    "to": "0x2222222222222222222222222222222222222222",
                    "value": "1000000000000000000",
                    "timeStamp": "1700000000",
                    "blockNumber": "19000000",
                    "isError": "0",
                }
            ],
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            result1 = await client.get_transactions("0x" + "a" * 40)
            result2 = await client.get_transactions("0x" + "a" * 40)

        assert result1 == result2
        assert mock_get.call_count == 1  # second call used cache


class TestCacheEntry:
    def test_get_returns_none_when_expired(self):
        cache = _Cache(ttl=0.0)
        cache.set("k", "v")
        time.sleep(0.01)
        assert cache.get("k") is None

    def test_get_returns_data_when_fresh(self):
        cache = _Cache(ttl=60.0)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_clear(self):
        cache = _Cache(ttl=60.0)
        cache.set("k", "v")
        cache.clear()
        assert cache.get("k") is None


# ═══════════════════════════════════════════════════════════════════════════════
# GoPlusClient
# ═══════════════════════════════════════════════════════════════════════════════


class TestGoPlusDemoMode:
    """Demo mode must work without tokens and return deterministic data."""

    @pytest.fixture
    def client(self):
        return GoPlusClient(token="", demo_mode=True)

    @pytest.mark.asyncio
    async def test_get_address_security_deterministic(self, client: GoPlusClient):
        addr = "0x" + "a" * 40
        result1 = await client.get_address_security(addr)
        result2 = await client.get_address_security(addr)
        assert result1 == result2
        assert result1["address"] == addr.lower()
        assert result1["source"] == "demo-goplus"
        assert "doubt_list" in result1
        assert "trust_list" in result1
        assert "malicious_behavior" in result1

    @pytest.mark.asyncio
    async def test_get_token_security_deterministic(self, client: GoPlusClient):
        token = "0x" + "d" * 40
        result1 = await client.get_token_security(token)
        result2 = await client.get_token_security(token)
        assert result1 == result2
        assert result1["token_address"] == token.lower()
        assert result1["source"] == "demo-goplus"
        assert "is_honeypot" in result1
        assert "is_open_source" in result1

    @pytest.mark.asyncio
    async def test_different_addresses_different_results(self, client: GoPlusClient):
        addr1 = "0x" + "a" * 40
        addr2 = "0x" + "b" * 40
        r1 = await client.get_address_security(addr1)
        r2 = await client.get_address_security(addr2)
        # They hash to different buckets, so results should differ
        assert r1["address"] != r2["address"]


class TestGoPlusRealModeErrors:
    """Real mode must produce structured ConnectorError on failures."""

    @pytest.mark.asyncio
    async def test_timeout_produces_connector_error(self):
        client = GoPlusClient(
            token="test-token",
            demo_mode=False,
            timeout_seconds=0.01,
            max_retries=1,
        )
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("simulated timeout")):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_address_security("0x" + "a" * 40)
        err = exc_info.value
        assert err.provider == "goplus"
        assert err.retryable is True
        assert "Timeout" in err.message

    @pytest.mark.asyncio
    async def test_429_produces_retryable_connector_error(self):
        client = GoPlusClient(
            token="test-token",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_address_security("0x" + "a" * 40)
        assert exc_info.value.status_code == 429
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_500_produces_retryable_connector_error(self):
        client = GoPlusClient(
            token="test-token",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_address_security("0x" + "a" * 40)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_api_error_code_produces_structured_error(self):
        client = GoPlusClient(
            token="test-token",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "Invalid address"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.get_address_security("0x" + "a" * 40)
        assert "GoPlus API error" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_4029_rate_limit_retries_then_success(self):
        client = GoPlusClient(
            token="",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=2,
        )
        rate_limited = MagicMock(spec=httpx.Response)
        rate_limited.status_code = 200
        rate_limited.json.return_value = {"code": 4029, "message": "too many requests"}
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "code": 1,
            "message": "ok",
            "result": {"address": "0xaaaa", "blacklist_doubt": "0"},
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[rate_limited, success_response]) as mock_get:
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client.get_address_security("0x" + "a" * 40)

        assert mock_get.call_count == 2
        assert result["address"] == "0xaaaa"

    @pytest.mark.asyncio
    async def test_real_mode_without_token_calls_free_endpoint(self):
        client = GoPlusClient(token="", demo_mode=False)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 1,
            "message": "ok",
            "result": {"address": "0xaaaa", "blacklist_doubt": "0"},
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            result = await client.get_address_security("0x" + "a" * 40)

        assert result["address"] == "0xaaaa"
        assert mock_get.call_args.kwargs["headers"] is None

    @pytest.mark.asyncio
    async def test_app_key_like_token_omits_auth_header(self):
        client = GoPlusClient(token="a" * 32, demo_mode=False)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 1,
            "message": "ok",
            "result": {"address": "0xaaaa", "blacklist_doubt": "0"},
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await client.get_address_security("0x" + "a" * 40)

        assert mock_get.call_args.kwargs["headers"] is None


class TestGoPlusRetries:
    @pytest.mark.asyncio
    async def test_retries_on_timeout_then_success(self):
        client = GoPlusClient(
            token="test-token",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=3,
        )
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "code": 1,
            "result": {"address": "0xaaaa", "doubt_list": "0"},
        }

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("simulated timeout")
            return success_response

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            result = await client.get_address_security("0x" + "a" * 40)

        assert call_count == 3
        assert result["address"] == "0xaaaa"


# ═══════════════════════════════════════════════════════════════════════════════
# DeepSeekClient
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeepSeekDemoMode:
    """Demo mode must return deterministic reports without API keys."""

    @pytest.fixture
    def client(self):
        return DeepSeekClient(api_key="", demo_mode=True)

    @pytest.mark.asyncio
    async def test_generate_report_deterministic(self, client: DeepSeekClient):
        context = {
            "investigation_id": "inv-test",
            "target": "0x" + "a" * 40,
            "risk": {
                "final_risk_level": "high",
                "final_risk_score": 75.0,
                "rule_score": 70.0,
                "raindrop_score": 80.0,
                "disposition_hint": "review",
                "findings": [
                    {
                        "severity": "high",
                        "subject": "0xaaaa",
                        "evidence": "OFAC sanctioned address",
                    }
                ],
                "pattern_signals": [
                    {
                        "severity": "medium",
                        "name": "layering",
                        "evidence": "Multiple rapid transfers detected",
                    }
                ],
                "recommended_actions": ["Manual review required"],
            },
        }
        report1 = await client.generate_report(context)
        report2 = await client.generate_report(context)
        assert report1 == report2
        assert "AML Investigation Report" in report1
        assert "inv-test" in report1
        assert "demo mode" in report1.lower() or "demo" in report1.lower()

    @pytest.mark.asyncio
    async def test_generate_report_minimal_context(self, client: DeepSeekClient):
        context = {"investigation_id": "inv-min", "target": "0x" + "b" * 40}
        report = await client.generate_report(context)
        assert "inv-min" in report
        assert "low" in report.lower()  # default risk level

    @pytest.mark.asyncio
    async def test_generate_report_includes_findings(self, client: DeepSeekClient):
        context = {
            "investigation_id": "inv-f",
            "target": "0x" + "c" * 40,
            "risk": {
                "final_risk_level": "critical",
                "final_risk_score": 95.0,
                "findings": [
                    {"severity": "critical", "subject": "sanctioned", "evidence": "Direct OFAC hit"},
                    {"severity": "high", "subject": "mixer", "evidence": "Tornado Cash interaction"},
                ],
            },
        }
        report = await client.generate_report(context)
        assert "OFAC" in report
        assert "Tornado Cash" in report


class TestDeepSeekRealModeErrors:
    """Real mode must produce structured ConnectorError on failures."""

    @pytest.mark.asyncio
    async def test_timeout_produces_connector_error(self):
        client = DeepSeekClient(
            api_key="test-key",
            demo_mode=False,
            timeout_seconds=0.01,
            max_retries=1,
        )
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("simulated timeout")):
            with pytest.raises(ConnectorError) as exc_info:
                await client.generate_report({"investigation_id": "inv-t", "target": "0x" + "a" * 40})
        err = exc_info.value
        assert err.provider == "deepseek"
        assert err.retryable is True
        assert "Timeout" in err.message

    @pytest.mark.asyncio
    async def test_429_produces_retryable_connector_error(self):
        client = DeepSeekClient(
            api_key="test-key",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.generate_report({"investigation_id": "inv-t", "target": "0x" + "a" * 40})
        assert exc_info.value.status_code == 429
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_500_produces_retryable_connector_error(self):
        client = DeepSeekClient(
            api_key="test-key",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.generate_report({"investigation_id": "inv-t", "target": "0x" + "a" * 40})
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_missing_choices_produces_structured_error(self):
        client = DeepSeekClient(
            api_key="test-key",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=1,
        )
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "shape"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ConnectorError) as exc_info:
                await client.generate_report({"investigation_id": "inv-t", "target": "0x" + "a" * 40})
        assert "missing 'choices' key" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_real_mode_without_key_falls_back_to_demo(self):
        client = DeepSeekClient(api_key="", demo_mode=False)
        report = await client.generate_report({"inv": "inv-x", "target": "0x" + "a" * 40})
        assert "AML Investigation Report" in report


class TestDeepSeekRetries:
    @pytest.mark.asyncio
    async def test_retries_on_timeout_then_success(self):
        client = DeepSeekClient(
            api_key="test-key",
            demo_mode=False,
            timeout_seconds=5.0,
            max_retries=3,
        )
        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "Report content"}}],
        }

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("simulated timeout")
            return success_response

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await client.generate_report({"investigation_id": "inv-r", "target": "0x" + "a" * 40})

        assert call_count == 3
        assert result == "Report content"


def _topic_for_address(address: str) -> str:
    return "0x" + address.removeprefix("0x").rjust(64, "0")


def _abi_string(value: str) -> str:
    encoded = value.encode().hex()
    length = len(value.encode())
    padded_length = ((len(encoded) + 63) // 64) * 64
    return "0x" + f"{32:064x}" + f"{length:064x}" + encoded.ljust(padded_length, "0")

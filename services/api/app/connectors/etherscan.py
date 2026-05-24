"""Etherscan API v2 client with retries, structured errors, and demo fixtures."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.connectors.base import ConnectorError, new_request_id

PROVIDER = "etherscan"
ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _demo_address(seed: str, index: int) -> str:
    digest = hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()
    return "0x" + digest[:40]


def _demo_hash(seed: str, index: int) -> str:
    digest = hashlib.sha256(f"tx:{seed}:{index}".encode()).hexdigest()
    return "0x" + digest


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    data: Any
    expires_at: float


@dataclass
class _Cache:
    """Simple in-memory TTL cache. Not thread-safe (single-event-loop assumed)."""

    ttl: float = 300.0  # 5 minutes default
    _store: dict[str, _CacheEntry] = field(default_factory=dict)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: Any) -> None:
        self._store[key] = _CacheEntry(data=data, expires_at=time.monotonic() + self.ttl)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

@dataclass
class EtherscanClient:
    """Etherscan API v2 connector.

    In demo mode, returns deterministic transaction data derived from the
    address hash so that investigations and screenings are reproducible
    without network access.
    """

    api_key: str = ""
    base_url: str = "https://api.etherscan.io/v2/api"
    chain_id: str = "1"
    demo_mode: bool = True
    timeout_seconds: float = 10.0
    max_retries: int = 2
    _cache: _Cache = field(default_factory=_Cache, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_transactions(
        self,
        address: str,
        page: int = 1,
        offset: int = 25,
        chain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch normal transactions for *address* (paginated)."""
        if self.demo_mode or not self.api_key:
            return self._demo_transactions(address, page=page, offset=min(offset, 8))

        effective_chain_id = chain_id or self.chain_id
        cache_key = f"txlist:{effective_chain_id}:{address}:{page}:{offset}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "chainid": effective_chain_id,
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": self.api_key,
        }
        payload = await self._get(params)
        result = payload.get("result", [])
        if isinstance(result, list):
            normalised = [self._normalize_tx(tx) for tx in result]
        else:
            normalised = []
        self._cache.set(cache_key, normalised)
        return normalised

    async def get_token_transfers(
        self,
        address: str,
        token_address: str | None = None,
        page: int = 1,
        offset: int = 25,
        chain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch ERC-20 token transfers for *address*."""
        if self.demo_mode or not self.api_key:
            return self._demo_token_transfers(address, token_address=token_address, page=page, offset=min(offset, 8))

        effective_chain_id = chain_id or self.chain_id
        normalized_token = token_address.lower() if token_address else ""
        cache_key = f"tokentx:{effective_chain_id}:{address}:{normalized_token}:{page}:{offset}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "chainid": effective_chain_id,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": page,
            "offset": offset,
            "sort": "desc",
            "apikey": self.api_key,
        }
        if normalized_token:
            params["contractaddress"] = normalized_token
        payload = await self._get(params)
        result = payload.get("result", [])
        if isinstance(result, list):
            normalised = [self._normalize_token_tx(tx) for tx in result]
        else:
            normalised = []
        self._cache.set(cache_key, normalised)
        return normalised

    async def get_transaction_details(self, tx_hash: str, chain_id: str | None = None) -> dict[str, Any]:
        """Fetch details for a single transaction by hash."""
        if self.demo_mode or not self.api_key:
            return self._demo_hash_transaction(tx_hash)

        effective_chain_id = chain_id or self.chain_id
        cache_key = f"txdetail:{effective_chain_id}:{tx_hash}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "chainid": effective_chain_id,
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
            "apikey": self.api_key,
        }
        payload = await self._get(params)
        result = payload.get("result") or {}
        block_number = result.get("blockNumber") or ""
        timestamp = None
        if block_number:
            try:
                timestamp = await self.get_block_timestamp(block_number, chain_id=effective_chain_id)
            except ConnectorError:
                timestamp = None
        detail = {
            "hash": tx_hash,
            "from": (result.get("from") or "").lower(),
            "to": (result.get("to") or "").lower(),
            "value_eth": int(result.get("value") or "0x0", 16) / 1e18,
            "timestamp": timestamp or int(time.time()),
            "block_number": block_number,
        }
        self._cache.set(cache_key, detail)
        return detail

    async def get_block_timestamp(self, block_number: str, chain_id: str | None = None) -> int | None:
        """Fetch a block timestamp for a hex block number."""
        if self.demo_mode or not self.api_key:
            return int(time.time())

        effective_chain_id = chain_id or self.chain_id
        cache_key = f"blockts:{effective_chain_id}:{block_number}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._get(
            {
                "chainid": effective_chain_id,
                "module": "proxy",
                "action": "eth_getBlockByNumber",
                "tag": block_number,
                "boolean": "false",
                "apikey": self.api_key,
            }
        )
        result = payload.get("result") or {}
        raw_timestamp = result.get("timestamp")
        if not isinstance(raw_timestamp, str) or not raw_timestamp.startswith("0x"):
            return None
        try:
            timestamp = int(raw_timestamp, 16)
        except ValueError:
            return None
        self._cache.set(cache_key, timestamp)
        return timestamp

    async def get_transaction_receipt(self, tx_hash: str, chain_id: str | None = None) -> dict[str, Any]:
        """Fetch transaction receipt for log-based token transfer decoding."""
        if self.demo_mode or not self.api_key:
            return {"transactionHash": tx_hash, "logs": [], "source": "demo"}

        effective_chain_id = chain_id or self.chain_id
        cache_key = f"txreceipt:{effective_chain_id}:{tx_hash}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._get(
            {
                "chainid": effective_chain_id,
                "module": "proxy",
                "action": "eth_getTransactionReceipt",
                "txhash": tx_hash,
                "apikey": self.api_key,
            }
        )
        receipt = payload.get("result") or {}
        self._cache.set(cache_key, receipt)
        return receipt

    async def get_token_metadata(self, token_address: str, chain_id: str | None = None) -> dict[str, Any]:
        """Read basic ERC-20 metadata through Etherscan proxy eth_call."""
        if self.demo_mode or not self.api_key:
            return {"symbol": "DEMO", "name": "Demo ERC20", "decimals": 18, "source": "demo"}

        effective_chain_id = chain_id or self.chain_id
        normalized = token_address.lower()
        cache_key = f"tokenmeta:{effective_chain_id}:{normalized}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        decimals = None
        symbol = ""
        name = ""
        try:
            decimals = await self._eth_call_uint(normalized, "0x313ce567", effective_chain_id)
        except ConnectorError:
            decimals = None
        try:
            symbol = await self._eth_call_string(normalized, "0x95d89b41", effective_chain_id)
        except ConnectorError:
            symbol = ""
        try:
            name = await self._eth_call_string(normalized, "0x06fdde03", effective_chain_id)
        except ConnectorError:
            name = ""
        metadata = {
            "symbol": symbol or "ERC20",
            "name": name or symbol or "ERC20 Token",
            "decimals": decimals if decimals is not None else 18,
            "source": "etherscan_eth_call",
        }
        self._cache.set(cache_key, metadata)
        return metadata

    async def get_screening_transaction(self, tx_hash: str, chain_id: str | None = None) -> dict[str, Any]:
        """Resolve a transaction hash into a screening-ready transfer payload."""
        detail = await self.get_transaction_details(tx_hash, chain_id=chain_id)
        receipt = await self.get_transaction_receipt(tx_hash, chain_id=chain_id)
        token_log = _first_erc20_transfer_log(
            receipt,
            {
                str(detail.get("from") or "").lower(),
                str(detail.get("to") or "").lower(),
            },
        )
        if token_log:
            token_address = str(token_log.get("address") or "").lower()
            metadata = await self.get_token_metadata(token_address, chain_id=chain_id)
            decimals = int(metadata.get("decimals") or 18)
            amount = token_log["raw_value"] / (10 ** decimals)
            return {
                "tx_hash": tx_hash,
                "from_address": token_log["from_address"],
                "to_address": token_log["to_address"],
                "amount": amount,
                "asset": str(metadata.get("symbol") or "ERC20").upper(),
                "asset_type": "erc20",
                "token_address": token_address,
                "timestamp": detail.get("timestamp") or int(time.time()),
                "raw_payload": {"transaction": detail, "receipt": receipt, "token_metadata": metadata},
            }

        return {
            "tx_hash": tx_hash,
            "from_address": detail.get("from", ""),
            "to_address": detail.get("to", ""),
            "amount": float(detail.get("value_eth") or 0),
            "asset": "ETH",
            "asset_type": "native",
            "token_address": None,
            "timestamp": detail.get("timestamp") or int(time.time()),
            "raw_payload": {"transaction": detail, "receipt": receipt},
        }

    # ------------------------------------------------------------------
    # HTTP with retries
    # ------------------------------------------------------------------

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET with bounded retry on 429/5xx/timeouts."""
        rid = new_request_id()
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.get(self.base_url, params=params)

                if response.status_code == 429:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=429,
                        message="Rate limited by Etherscan",
                        request_id=rid,
                        retryable=True,
                    )
                if response.status_code >= 500:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"Etherscan server error: {response.text[:200]}",
                        request_id=rid,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"Etherscan client error: {response.text[:200]}",
                        request_id=rid,
                        retryable=False,
                    )

                payload = response.json()
                status_field = payload.get("status", "")
                message_field = payload.get("message", "")
                # Etherscan returns status="0" for errors like "NOTOK"
                if status_field == "0" and message_field.upper() == "NOTOK":
                    error_msg = payload.get("result", "Unknown Etherscan error")
                    retryable = "rate limit" in str(error_msg).lower()
                    err = ConnectorError(
                        provider=PROVIDER,
                        status_code=200,
                        message=f"Etherscan API error: {error_msg}",
                        request_id=rid,
                        retryable=retryable,
                        raw=payload,
                    )
                    if retryable and attempt < self.max_retries:
                        last_exc = err
                    else:
                        raise err
                    await asyncio.sleep(1.1)
                    continue
                return payload

            except httpx.TimeoutException:
                last_exc = ConnectorError(
                    provider=PROVIDER,
                    status_code=None,
                    message=f"Timeout after {self.timeout_seconds}s (attempt {attempt}/{self.max_retries})",
                    request_id=rid,
                    retryable=True,
                )
            except httpx.HTTPError as exc:
                last_exc = ConnectorError(
                    provider=PROVIDER,
                    status_code=None,
                    message=f"HTTP error: {exc} (attempt {attempt}/{self.max_retries})",
                    request_id=rid,
                    retryable=True,
                )
            except ConnectorError as exc:
                if exc.retryable and attempt < self.max_retries:
                    last_exc = exc
                else:
                    raise

            # Exponential back-off before retry
            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        # All retries exhausted
        raise last_exc  # type: ignore[misc]

    async def _eth_call_uint(self, token_address: str, data: str, chain_id: str) -> int | None:
        payload = await self._eth_call(token_address, data, chain_id)
        result = payload.get("result")
        if not isinstance(result, str) or not result.startswith("0x"):
            return None
        try:
            return int(result, 16)
        except ValueError:
            return None

    async def _eth_call_string(self, token_address: str, data: str, chain_id: str) -> str:
        payload = await self._eth_call(token_address, data, chain_id)
        result = payload.get("result")
        if not isinstance(result, str) or not result.startswith("0x"):
            return ""
        return _decode_abi_string(result)

    async def _eth_call(self, token_address: str, data: str, chain_id: str) -> dict[str, Any]:
        return await self._get(
            {
                "chainid": chain_id,
                "module": "proxy",
                "action": "eth_call",
                "to": token_address,
                "data": data,
                "tag": "latest",
                "apikey": self.api_key,
            }
        )

    # ------------------------------------------------------------------
    # Demo fixtures
    # ------------------------------------------------------------------

    def _demo_transactions(self, address: str, page: int, offset: int) -> list[dict[str, Any]]:
        base = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
        transactions: list[dict[str, Any]] = []
        for idx in range(offset):
            peer = _demo_address(address, page * 100 + idx)
            outgoing = (base + idx) % 2 == 0
            timestamp = int(time.time()) - ((page - 1) * offset + idx + 1) * 7200
            value = round(((base % 19) + idx + 1) / 3.7, 5)
            transactions.append(
                {
                    "hash": _demo_hash(address, page * 100 + idx),
                    "from": address.lower() if outgoing else peer,
                    "to": peer if outgoing else address.lower(),
                    "value_eth": value,
                    "timestamp": timestamp,
                    "block_number": str(19000000 + idx),
                    "is_error": "0",
                    "source": "demo",
                }
            )
        return transactions

    def _demo_token_transfers(
        self,
        address: str,
        token_address: str | None,
        page: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        token = (token_address or "0x" + "d" * 40).lower()
        base = int(hashlib.sha256(f"{address}:{token}".encode()).hexdigest()[:8], 16)
        transactions: list[dict[str, Any]] = []
        for idx in range(offset):
            peer = _demo_address(f"{address}:{token}", page * 100 + idx)
            outgoing = (base + idx) % 2 == 0
            timestamp = int(time.time()) - ((page - 1) * offset + idx + 1) * 7200
            value_token = round(((base % 29) + idx + 1) * 137.5, 6)
            transactions.append(
                {
                    "hash": _demo_hash(f"{address}:{token}", page * 100 + idx),
                    "from": address.lower() if outgoing else peer,
                    "to": peer if outgoing else address.lower(),
                    "value_eth": value_token,
                    "value_token": value_token,
                    "timestamp": timestamp,
                    "block_number": str(19000000 + idx),
                    "is_error": "0",
                    "contract_address": token,
                    "token_name": "Demo ERC20",
                    "token_symbol": "DERC20",
                    "token_decimal": 18,
                    "source": "demo_tokentx",
                }
            )
        return transactions

    def _demo_hash_transaction(self, tx_hash: str) -> dict[str, Any]:
        return {
            "hash": tx_hash,
            "from": _demo_address(tx_hash, 1),
            "to": _demo_address(tx_hash, 2),
            "value_eth": 4.2,
            "timestamp": int(time.time()) - 3600,
            "source": "demo",
        }

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_tx(tx: dict[str, Any]) -> dict[str, Any]:
        value_raw = tx.get("value") or "0"
        try:
            value_eth = int(value_raw) / 1e18
        except (TypeError, ValueError):
            value_eth = 0.0
        return {
            "hash": tx.get("hash", ""),
            "from": (tx.get("from") or "").lower(),
            "to": (tx.get("to") or "").lower(),
            "value_eth": value_eth,
            "timestamp": int(tx.get("timeStamp") or 0),
            "block_number": tx.get("blockNumber", ""),
            "is_error": tx.get("isError", "0"),
            "source": "etherscan",
        }

    @staticmethod
    def _normalize_token_tx(tx: dict[str, Any]) -> dict[str, Any]:
        decimals_raw = tx.get("tokenDecimal") or tx.get("token_decimal") or "0"
        try:
            decimals = int(decimals_raw)
        except (TypeError, ValueError):
            decimals = 0
        value_raw = tx.get("value") or "0"
        try:
            value_token = int(value_raw) / (10 ** decimals if decimals >= 0 else 1)
        except (TypeError, ValueError):
            value_token = 0.0
        return {
            "hash": tx.get("hash", ""),
            "from": (tx.get("from") or "").lower(),
            "to": (tx.get("to") or "").lower(),
            "value_eth": value_token,
            "value_token": value_token,
            "timestamp": int(tx.get("timeStamp") or 0),
            "block_number": tx.get("blockNumber", ""),
            "is_error": tx.get("isError", "0"),
            "contract_address": (tx.get("contractAddress") or "").lower(),
            "token_name": tx.get("tokenName", ""),
            "token_symbol": tx.get("tokenSymbol", ""),
            "token_decimal": decimals,
            "source": "etherscan_tokentx",
        }


def _first_erc20_transfer_log(receipt: dict[str, Any], preferred_addresses: set[str] | None = None) -> dict[str, Any] | None:
    decoded: list[dict[str, Any]] = []
    for log in receipt.get("logs") or []:
        topics = [str(topic).lower() for topic in log.get("topics") or []]
        if len(topics) < 3 or topics[0] != ERC20_TRANSFER_TOPIC:
            continue
        data = str(log.get("data") or "0x0")
        try:
            raw_value = int(data, 16)
        except ValueError:
            continue
        token_address = str(log.get("address") or "").lower()
        if not token_address.startswith("0x") or len(token_address) != 42:
            continue
        decoded.append(
            {
                "address": token_address,
                "from_address": _topic_address(topics[1]),
                "to_address": _topic_address(topics[2]),
                "raw_value": raw_value,
                "raw_log": log,
            }
        )
    if not decoded:
        return None
    preferred = {address for address in (preferred_addresses or set()) if address}
    for item in decoded:
        if item["from_address"] in preferred or item["to_address"] in preferred:
            return item
    return decoded[0]


def _topic_address(topic: str) -> str:
    return "0x" + topic.removeprefix("0x")[-40:]


def _decode_abi_string(result: str) -> str:
    payload = result.removeprefix("0x")
    if not payload or set(payload) <= {"0"}:
        return ""
    # bytes32 symbols/names are common in older ERC-20 contracts.
    if len(payload) == 64:
        return bytes.fromhex(payload).rstrip(b"\x00").decode("utf-8", errors="ignore").strip()
    try:
        offset = int(payload[:64], 16) * 2
        length = int(payload[offset : offset + 64], 16) * 2
        data = payload[offset + 64 : offset + 64 + length]
        return bytes.fromhex(data).decode("utf-8", errors="ignore").strip()
    except (ValueError, IndexError):
        return ""

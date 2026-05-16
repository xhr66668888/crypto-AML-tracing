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

    async def get_transactions(self, address: str, page: int = 1, offset: int = 25) -> list[dict[str, Any]]:
        """Fetch normal transactions for *address* (paginated)."""
        if self.demo_mode or not self.api_key:
            return self._demo_transactions(address, page=page, offset=min(offset, 8))

        cache_key = f"txlist:{address}:{page}:{offset}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "chainid": self.chain_id,
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

    async def get_transaction_details(self, tx_hash: str) -> dict[str, Any]:
        """Fetch details for a single transaction by hash."""
        if self.demo_mode or not self.api_key:
            return self._demo_hash_transaction(tx_hash)

        cache_key = f"txdetail:{tx_hash}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "chainid": self.chain_id,
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
            "apikey": self.api_key,
        }
        payload = await self._get(params)
        result = payload.get("result") or {}
        detail = {
            "hash": tx_hash,
            "from": (result.get("from") or "").lower(),
            "to": (result.get("to") or "").lower(),
            "value_eth": int(result.get("value") or "0x0", 16) / 1e18,
            "timestamp": int(time.time()),
        }
        self._cache.set(cache_key, detail)
        return detail

    async def get_internal_transactions(self, tx_hash: str) -> list[dict[str, Any]]:
        """Fetch internal (trace) transactions for a parent tx hash."""
        if self.demo_mode or not self.api_key:
            return self._demo_internal_transactions(tx_hash)

        cache_key = f"txinternal:{tx_hash}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params = {
            "chainid": self.chain_id,
            "module": "account",
            "action": "txlistinternal",
            "txhash": tx_hash,
            "apikey": self.api_key,
        }
        payload = await self._get(params)
        result = payload.get("result", [])
        if isinstance(result, list):
            normalised = [self._normalize_internal(tx) for tx in result]
        else:
            normalised = []
        self._cache.set(cache_key, normalised)
        return normalised

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
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=200,
                        message=f"Etherscan API error: {error_msg}",
                        request_id=rid,
                        retryable=False,
                        raw=payload,
                    )
                return payload

            except httpx.TimeoutException as exc:
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
            except ConnectorError:
                raise  # already structured, re-raise directly

            # Exponential back-off before retry
            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        # All retries exhausted
        raise last_exc  # type: ignore[misc]

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

    def _demo_hash_transaction(self, tx_hash: str) -> dict[str, Any]:
        return {
            "hash": tx_hash,
            "from": _demo_address(tx_hash, 1),
            "to": _demo_address(tx_hash, 2),
            "value_eth": 4.2,
            "timestamp": int(time.time()) - 3600,
            "source": "demo",
        }

    def _demo_internal_transactions(self, tx_hash: str) -> list[dict[str, Any]]:
        """Deterministic internal transactions for demo mode."""
        base = int(hashlib.sha256(f"internal:{tx_hash}".encode()).hexdigest()[:8], 16)
        count = (base % 3) + 1  # 1-3 internal txs
        result: list[dict[str, Any]] = []
        for idx in range(count):
            value = round(((base + idx) % 7 + 1) / 10.0, 5)
            result.append(
                {
                    "hash": tx_hash,
                    "from": _demo_address(tx_hash, idx + 10),
                    "to": _demo_address(tx_hash, idx + 20),
                    "value_eth": value,
                    "timestamp": int(time.time()) - 3600 - idx * 60,
                    "block_number": str(19000000 + idx),
                    "is_error": "0",
                    "source": "demo",
                }
            )
        return result

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
    def _normalize_internal(tx: dict[str, Any]) -> dict[str, Any]:
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
            "source": "etherscan-internal",
        }

"""GoPlus Security API client with retries, structured errors, and demo fixtures."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.connectors.base import ConnectorError, new_request_id

PROVIDER = "goplus"

HIGH_RISK_BEHAVIORS = {
    "money_laundering",
    "mixer",
    "sanctioned",
    "phishing_activities",
    "darkweb_transactions",
    "cybercrime",
    "stealing_attack",
    "blackmail_activities",
}


@dataclass
class GoPlusClient:
    """GoPlus Security API connector.

    In demo mode, returns deterministic security data derived from the
    address hash so that screenings are reproducible without network access.
    """

    token: str = ""
    demo_mode: bool = True
    timeout_seconds: float = 10.0
    max_retries: int = 2
    _cache: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict, repr=False)
    _last_request_at: float = field(default=0.0, repr=False)
    _rate_limited_until: float = field(default=0.0, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_address_security(self, address: str, chain_id: str = "1") -> dict[str, Any]:
        """Fetch security assessment for an address."""
        if self.demo_mode:
            return self._demo_security(address)

        params = {"chain_id": chain_id}
        headers = self._auth_headers()
        url = f"https://api.gopluslabs.io/api/v1/address_security/{address}"
        cache_key = f"address:{chain_id}:{address.lower()}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        payload = await self._get(url, params=params, headers=headers)
        result = payload.get("result") or payload
        self._cache_result(cache_key, result)
        return result

    async def get_token_security(self, token_address: str, chain_id: str = "1") -> dict[str, Any]:
        """Fetch security assessment for a token contract."""
        if self.demo_mode:
            return self._demo_token_security(token_address)

        params = {"chain_id": chain_id}
        headers = self._auth_headers()
        url = f"https://api.gopluslabs.io/api/v1/token_security/{token_address}"
        cache_key = f"token:{chain_id}:{token_address.lower()}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached
        payload = await self._get(url, params=params, headers=headers)
        result = payload.get("result") or payload
        self._cache_result(cache_key, result)
        return result

    def _auth_headers(self) -> dict[str, str] | None:
        token = self.token.strip()
        if not token:
            return None
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token.startswith("eyJ"):
            return None
        return {"Authorization": f"Bearer {token}"}

    def _cached(self, key: str) -> dict[str, Any] | None:
        item = self._cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            del self._cache[key]
            return None
        return value

    def _cache_result(self, key: str, value: dict[str, Any]) -> None:
        self._cache[key] = (time.monotonic() + 60.0, value)

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < 0.4:
            await asyncio.sleep(0.4 - elapsed)
        self._last_request_at = time.monotonic()

    # ------------------------------------------------------------------
    # HTTP with retries
    # ------------------------------------------------------------------

    async def _get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """GET with bounded retry on 429/5xx/timeouts."""
        rid = new_request_id()
        last_exc: ConnectorError | None = None
        if time.monotonic() < self._rate_limited_until:
            raise ConnectorError(
                provider=PROVIDER,
                status_code=200,
                message="GoPlus API error (code=4029): too many requests",
                request_id=rid,
                retryable=True,
            )
        for attempt in range(1, self.max_retries + 1):
            try:
                await self._throttle()
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.get(url, params=params, headers=headers)

                if response.status_code == 429:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=429,
                        message="Rate limited by GoPlus",
                        request_id=rid,
                        retryable=True,
                    )
                if response.status_code >= 500:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"GoPlus server error: {response.text[:200]}",
                        request_id=rid,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"GoPlus client error: {response.text[:200]}",
                        request_id=rid,
                        retryable=False,
                    )

                payload = response.json()
                # GoPlus uses code=1 for success
                code = payload.get("code", 0)
                if code != 1:
                    retryable = code == 4029 or "too many" in str(payload.get("message", "")).lower()
                    err = ConnectorError(
                        provider=PROVIDER,
                        status_code=200,
                        message=f"GoPlus API error (code={code}): {payload.get('message', 'Unknown')}",
                        request_id=rid,
                        retryable=retryable,
                        raw=payload,
                    )
                    if retryable and attempt < self.max_retries:
                        last_exc = err
                        await asyncio.sleep(1.0 * attempt)
                        continue
                    if retryable:
                        self._rate_limited_until = time.monotonic() + 60.0
                    raise err
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

            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Demo fixtures
    # ------------------------------------------------------------------

    def _demo_security(self, address: str) -> dict[str, Any]:
        bucket = int(hashlib.sha256(address.encode()).hexdigest()[:2], 16) % 10
        if bucket in {0, 1}:
            behaviors = ["mixer", "money_laundering"]
            doubt = "1"
        elif bucket == 2:
            behaviors = ["phishing_activities"]
            doubt = "1"
        elif bucket == 3:
            behaviors = ["darkweb_transactions"]
            doubt = "1"
        else:
            behaviors = []
            doubt = "0"
        return {
            "address": address.lower(),
            "doubt_list": doubt,
            "trust_list": "1" if bucket == 9 else "0",
            "malicious_behavior": behaviors,
            "source": "demo-goplus",
        }

    def _demo_token_security(self, token_address: str) -> dict[str, Any]:
        """Deterministic token security data for demo mode."""
        bucket = int(hashlib.sha256(f"token:{token_address}".encode()).hexdigest()[:2], 16) % 10
        is_honeypot = bucket in {0, 1}
        is_open_source = bucket not in {0, 1, 2}
        return {
            "token_address": token_address.lower(),
            "token_name": f"DemoToken-{bucket}",
            "token_symbol": f"DT{bucket}",
            "is_honeypot": "1" if is_honeypot else "0",
            "is_open_source": "1" if is_open_source else "0",
            "owner_change_balance": "1" if bucket < 3 else "0",
            "hidden_owner": "1" if bucket == 0 else "0",
            "selfdestruct": "1" if bucket == 0 else "0",
            "external_call": "1" if bucket < 4 else "0",
            "trust_list": "1" if bucket == 9 else "0",
            "cannot_sell_all": "1" if is_honeypot else "0",
            "owner_can_pause": "1" if bucket < 3 else "0",
            "source": "demo-goplus",
        }

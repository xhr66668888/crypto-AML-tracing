from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.connectors.base import ConnectorError, new_request_id


PROVIDER = "stablecoin_blacklist"
ALCHEMY_ETH_MAINNET_PUBLIC_RPC = "https://eth-mainnet.g.alchemy.com/public"
CIRCLE_USDC_ETH_CONTRACT = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
TETHER_USDT_ETH_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"


@dataclass(frozen=True)
class StablecoinBlacklistCheck:
    provider: str
    category: str
    token_symbol: str
    token_address: str
    address: str
    blacklisted: bool
    checked_at: datetime
    evidence: str
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _TokenBlacklistContract:
    provider: str
    category: str
    token_symbol: str
    token_address: str
    selectors: tuple[tuple[str, str], ...]


TOKEN_BLACKLIST_CONTRACTS: dict[str, _TokenBlacklistContract] = {
    "USDC": _TokenBlacklistContract(
        provider="circle_blacklist",
        category="circle_blacklist",
        token_symbol="USDC",
        token_address=CIRCLE_USDC_ETH_CONTRACT,
        selectors=(("isBlacklisted(address)", "0xfe575a87"),),
    ),
    "USDT": _TokenBlacklistContract(
        provider="tether_blacklist",
        category="tether_blacklist",
        token_symbol="USDT",
        token_address=TETHER_USDT_ETH_CONTRACT,
        selectors=(("isBlackListed(address)", "0xe47d6060"), ("getBlackListStatus(address)", "0x59bf1abe")),
    ),
}
TOKEN_BLACKLIST_CONTRACTS_BY_ADDRESS: dict[str, _TokenBlacklistContract] = {
    contract.token_address.lower(): contract for contract in TOKEN_BLACKLIST_CONTRACTS.values()
}


@dataclass
class StablecoinBlacklistClient:
    rpc_url: str = ALCHEMY_ETH_MAINNET_PUBLIC_RPC
    demo_mode: bool = True
    timeout_seconds: float = 10.0
    max_retries: int = 2
    _transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    async def check_address(
        self,
        token_symbol: str,
        address: str,
        chain_id: str = "1",
        token_address: str | None = None,
    ) -> StablecoinBlacklistCheck | None:
        contract = _blacklist_contract(token_symbol, token_address)
        if contract is None or chain_id != "1":
            return None
        normalized = address.lower()
        if self.demo_mode:
            return _check_result(contract, normalized, False, "demo", {})
        if not self.rpc_url.strip():
            raise ConnectorError(
                provider=contract.provider,
                message="Ethereum RPC URL is not configured for stablecoin blacklist checks.",
                retryable=True,
            )

        last_error: ConnectorError | None = None
        for method_name, selector in contract.selectors:
            try:
                blacklisted, raw_payload = await self._eth_call_bool(contract.token_address, selector, normalized)
                return _check_result(contract, normalized, blacklisted, method_name, raw_payload)
            except ConnectorError as exc:
                last_error = exc
                if exc.retryable:
                    raise
                continue
        if last_error:
            raise last_error
        return None

    async def _eth_call_bool(self, contract_address: str, selector: str, address: str) -> tuple[bool, dict[str, Any]]:
        request_id = new_request_id()
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "eth_call",
            "params": [{"to": contract_address, "data": _call_data(selector, address)}, "latest"],
        }
        payload = await self._post_rpc(body, request_id)
        result = payload.get("result")
        if not isinstance(result, str) or not result.startswith("0x") or len(result) < 66:
            raise ConnectorError(
                provider=PROVIDER,
                message=f"Unexpected eth_call result for {contract_address}: {result!r}",
                request_id=request_id,
                retryable=False,
                raw=payload,
            )
        return int(result, 16) != 0, payload

    async def _post_rpc(self, body: dict[str, Any], request_id: str) -> dict[str, Any]:
        last_exc: ConnectorError | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds, transport=self._transport) as client:
                    response = await client.post(self.rpc_url, json=body)
                if response.status_code == 429:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=429,
                        message="Rate limited by Ethereum RPC provider.",
                        request_id=request_id,
                        retryable=True,
                    )
                if response.status_code >= 500:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"Ethereum RPC server error: {response.text[:200]}",
                        request_id=request_id,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"Ethereum RPC client error: {response.text[:200]}",
                        request_id=request_id,
                        retryable=False,
                    )
                payload = response.json()
                if "error" in payload:
                    error = payload.get("error") or {}
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=200,
                        message=f"Ethereum RPC error: {error.get('message', 'unknown error')}",
                        request_id=request_id,
                        retryable=False,
                        raw=payload,
                    )
                return payload
            except httpx.TimeoutException:
                last_exc = ConnectorError(
                    provider=PROVIDER,
                    message=f"Timeout after {self.timeout_seconds}s (attempt {attempt}/{self.max_retries})",
                    request_id=request_id,
                    retryable=True,
                )
            except httpx.HTTPError as exc:
                last_exc = ConnectorError(
                    provider=PROVIDER,
                    message=f"HTTP error: {exc} (attempt {attempt}/{self.max_retries})",
                    request_id=request_id,
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


def _check_result(
    contract: _TokenBlacklistContract,
    address: str,
    blacklisted: bool,
    method_name: str,
    raw_payload: dict[str, Any],
) -> StablecoinBlacklistCheck:
    checked_at = datetime.now(UTC)
    state = "blacklisted" if blacklisted else "not blacklisted"
    evidence = (
        f"{contract.token_symbol} issuer blacklist check: {address} is {state} "
        f"by {contract.provider} contract {contract.token_address} via {method_name} at latest block."
    )
    return StablecoinBlacklistCheck(
        provider=contract.provider,
        category=contract.category,
        token_symbol=contract.token_symbol,
        token_address=contract.token_address,
        address=address,
        blacklisted=blacklisted,
        checked_at=checked_at,
        evidence=evidence,
        raw_payload={**raw_payload, "method": method_name},
    )


def _blacklist_contract(token_symbol: str, token_address: str | None) -> _TokenBlacklistContract | None:
    if token_address:
        contract = TOKEN_BLACKLIST_CONTRACTS_BY_ADDRESS.get(token_address.lower())
        if contract:
            return contract
    return TOKEN_BLACKLIST_CONTRACTS.get(token_symbol.upper().strip())


def _call_data(selector: str, address: str) -> str:
    clean_selector = selector.removeprefix("0x")
    clean_address = address.lower().removeprefix("0x")
    return "0x" + clean_selector + clean_address.rjust(64, "0")

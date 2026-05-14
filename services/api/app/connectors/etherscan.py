from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

import httpx


def _demo_address(seed: str, index: int) -> str:
    digest = hashlib.sha256(f"{seed}:{index}".encode()).hexdigest()
    return "0x" + digest[:40]


def _demo_hash(seed: str, index: int) -> str:
    digest = hashlib.sha256(f"tx:{seed}:{index}".encode()).hexdigest()
    return "0x" + digest


@dataclass
class EtherscanClient:
    api_key: str
    base_url: str
    chain_id: str = "1"
    demo_mode: bool = True

    async def get_transactions_for_address(self, address: str, page: int = 1, offset: int = 25) -> list[dict[str, Any]]:
        if self.demo_mode or not self.api_key:
            return self._demo_transactions(address, page=page, offset=min(offset, 8))

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
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result", [])
        if isinstance(result, list):
            return [self._normalize_tx(tx) for tx in result]
        return []

    async def get_transaction_by_hash(self, tx_hash: str) -> dict[str, Any]:
        if self.demo_mode or not self.api_key:
            return self._demo_hash_transaction(tx_hash)

        params = {
            "chainid": self.chain_id,
            "module": "proxy",
            "action": "eth_getTransactionByHash",
            "txhash": tx_hash,
            "apikey": self.api_key,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result") or {}
        return {
            "hash": tx_hash,
            "from": (result.get("from") or "").lower(),
            "to": (result.get("to") or "").lower(),
            "value_eth": int(result.get("value") or "0x0", 16) / 1e18,
            "timestamp": int(time.time()),
        }

    def _demo_hash_transaction(self, tx_hash: str) -> dict[str, Any]:
        return {
            "hash": tx_hash,
            "from": _demo_address(tx_hash, 1),
            "to": _demo_address(tx_hash, 2),
            "value_eth": 4.2,
            "timestamp": int(time.time()) - 3600,
        }

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

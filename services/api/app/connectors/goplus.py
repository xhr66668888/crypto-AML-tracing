from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx


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
    token: str = ""
    demo_mode: bool = True

    async def get_address_security(self, address: str, chain_id: str = "1") -> dict[str, Any]:
        if self.demo_mode or not self.token:
            return self._demo_security(address)

        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"https://api.gopluslabs.io/api/v1/address_security/{address}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params={"chain_id": chain_id}, headers=headers)
            response.raise_for_status()
            payload = response.json()
        return payload.get("result") or payload

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

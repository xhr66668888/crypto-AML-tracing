#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))

from app.connectors.base import ConnectorError  # noqa: E402
from app.connectors.stablecoin_blacklist import ALCHEMY_ETH_MAINNET_PUBLIC_RPC, StablecoinBlacklistClient  # noqa: E402
from app.domain.validators import normalize_address  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Check Circle USDC and Tether USDT blacklist status through Ethereum RPC.")
    parser.add_argument("address", help="Ethereum address to check.")
    parser.add_argument("--token", choices=("USDC", "USDT", "all"), default="all")
    parser.add_argument("--chain-id", default="1")
    parser.add_argument("--rpc-url", default=os.getenv("ETHEREUM_RPC_URL", ALCHEMY_ETH_MAINNET_PUBLIC_RPC))
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-retries", type=int, default=2)
    args = parser.parse_args()

    address = normalize_address(args.address)
    tokens = ("USDC", "USDT") if args.token == "all" else (args.token,)
    client = StablecoinBlacklistClient(
        rpc_url=args.rpc_url,
        demo_mode=False,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
    )

    rows = []
    for token in tokens:
        try:
            result = await client.check_address(token, address, chain_id=args.chain_id)
        except ConnectorError as exc:
            rows.append(
                {
                    "token": token,
                    "address": address,
                    "query_ok": False,
                    "error": exc.message,
                    "retryable": exc.retryable,
                    "provider": exc.provider,
                }
            )
            continue
        rows.append(
            {
                "token": token,
                "address": address,
                "query_ok": result is not None,
                "blacklisted": result.blacklisted if result else None,
                "provider": result.provider if result else None,
                "token_address": result.token_address if result else None,
                "checked_at": result.checked_at.isoformat() if result else None,
                "evidence": result.evidence if result else "No blacklist contract configured for this token/chain.",
            }
        )

    print(json.dumps(rows, indent=2, sort_keys=True))
    return 1 if any(row.get("query_ok") is False for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

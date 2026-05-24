from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChainConfig:
    chain_id: str
    name: str
    native_asset: str
    explorer_url: str
    token_contracts: dict[str, str]

    @property
    def assets(self) -> list[str]:
        return [self.native_asset, *sorted(self.token_contracts)]


SUPPORTED_CHAINS: dict[str, ChainConfig] = {
    "1": ChainConfig(
        chain_id="1",
        name="Ethereum Mainnet",
        native_asset="ETH",
        explorer_url="https://etherscan.io",
        token_contracts={
            "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
        },
    ),
    "56": ChainConfig(
        chain_id="56",
        name="BNB Smart Chain",
        native_asset="BNB",
        explorer_url="https://bscscan.com",
        token_contracts={
            "USDC": "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
            "USDT": "0x55d398326f99059ff775485246999027b3197955",
        },
    ),
    "137": ChainConfig(
        chain_id="137",
        name="Polygon Mainnet",
        native_asset="MATIC",
        explorer_url="https://polygonscan.com",
        token_contracts={
            "USDC": "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359",
            "USDT": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
        },
    ),
    "42161": ChainConfig(
        chain_id="42161",
        name="Arbitrum One",
        native_asset="ETH",
        explorer_url="https://arbiscan.io",
        token_contracts={
            "USDC": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
            "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
        },
    ),
    "10": ChainConfig(
        chain_id="10",
        name="Optimism",
        native_asset="ETH",
        explorer_url="https://optimistic.etherscan.io",
        token_contracts={
            "USDC": "0x0b2c639c533813f4aa9d7837caf62653d097ff85",
            "USDT": "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58",
        },
    ),
    "8453": ChainConfig(
        chain_id="8453",
        name="Base",
        native_asset="ETH",
        explorer_url="https://basescan.org",
        token_contracts={
            "USDC": "0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913".lower(),
        },
    ),
}


def supported_chain_ids() -> set[str]:
    return set(SUPPORTED_CHAINS)


def get_chain(chain_id: str) -> ChainConfig:
    try:
        return SUPPORTED_CHAINS[str(chain_id)]
    except KeyError as exc:
        raise ValueError(f"Unsupported chain_id: {chain_id}") from exc


def is_native_asset(chain_id: str, asset: str) -> bool:
    return asset.upper() == get_chain(chain_id).native_asset


def resolve_token_contract(chain_id: str, asset: str, token_contract_address: str | None = None) -> str | None:
    if token_contract_address:
        return token_contract_address.lower()
    return get_chain(chain_id).token_contracts.get(asset.upper())

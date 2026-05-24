from __future__ import annotations

from dataclasses import dataclass

from app.domain.validators import normalize_address


@dataclass(frozen=True)
class AssetMetadata:
    symbol: str
    asset_type: str
    decimals: int | None = None
    token_address: str | None = None
    name: str = ""

    @property
    def is_erc20(self) -> bool:
        return self.asset_type == "erc20"


ETH = AssetMetadata(symbol="ETH", asset_type="native", decimals=18, name="Ether")

ETH_MAINNET_TOKENS: dict[str, AssetMetadata] = {
    "USDT": AssetMetadata(
        symbol="USDT",
        asset_type="erc20",
        decimals=6,
        token_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
        name="Tether USD",
    ),
    "USDC": AssetMetadata(
        symbol="USDC",
        asset_type="erc20",
        decimals=6,
        token_address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        name="USD Coin",
    ),
    "DAI": AssetMetadata(
        symbol="DAI",
        asset_type="erc20",
        decimals=18,
        token_address="0x6b175474e89094c44da98b954eedeac495271d0f",
        name="Dai Stablecoin",
    ),
    "WETH": AssetMetadata(
        symbol="WETH",
        asset_type="erc20",
        decimals=18,
        token_address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
        name="Wrapped Ether",
    ),
    "WBTC": AssetMetadata(
        symbol="WBTC",
        asset_type="erc20",
        decimals=8,
        token_address="0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        name="Wrapped BTC",
    ),
}

TOKEN_BY_ADDRESS: dict[str, AssetMetadata] = {
    token.token_address: token for token in ETH_MAINNET_TOKENS.values() if token.token_address
}


def resolve_screening_asset(
    asset: str,
    chain_id: str,
    asset_type: str | None = None,
    token_address: str | None = None,
) -> AssetMetadata:
    symbol = asset.strip().upper()
    requested_type = asset_type.strip().lower() if asset_type else ""
    normalized_token = normalize_address(token_address) if token_address else None

    if symbol == ETH.symbol and not normalized_token:
        return ETH

    if normalized_token:
        known = TOKEN_BY_ADDRESS.get(normalized_token) if chain_id == "1" else None
        if known:
            return known
        if requested_type == "native":
            raise ValueError("Native asset screening cannot include token_address.")
        if symbol == ETH.symbol:
            raise ValueError("ETH screening cannot include an ERC-20 token_address.")
        return AssetMetadata(
            symbol=symbol,
            asset_type="erc20",
            decimals=None,
            token_address=normalized_token,
            name=symbol,
        )

    if chain_id == "1" and symbol in ETH_MAINNET_TOKENS:
        return ETH_MAINNET_TOKENS[symbol]

    if requested_type == "erc20":
        raise ValueError("ERC-20 screening requires token_address.")
    raise ValueError(f"Unsupported asset {symbol}; provide token_address for ERC-20 screening.")

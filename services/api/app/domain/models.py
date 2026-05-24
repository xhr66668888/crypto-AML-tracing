from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.chains import SUPPORTED_CHAINS, get_chain, is_native_asset, resolve_token_contract
from app.domain.validators import normalize_address, normalize_hash, validate_chain_id


class InvestigationMode(str, Enum):
    stable = "stable"
    experimental = "experimental"


class TargetType(str, Enum):
    address = "address"
    transaction_hash = "transaction_hash"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RiskDisposition(str, Enum):
    allow = "allow"
    review = "review"
    hold_for_manual_review = "hold_for_manual_review"
    reject = "reject"


class TransferDirection(str, Enum):
    inbound = "inbound"
    outbound = "outbound"


class AssetSymbol(str, Enum):
    eth = "ETH"
    bnb = "BNB"
    matic = "MATIC"
    usdt = "USDT"
    usdc = "USDC"
    erc20 = "ERC20"


class ChainInfo(BaseModel):
    chain_id: str
    name: str
    native_asset: str
    explorer_url: str
    assets: list[str]
    token_contracts: dict[str, str]


def chain_infos() -> list[ChainInfo]:
    return [
        ChainInfo(
            chain_id=chain.chain_id,
            name=chain.name,
            native_asset=chain.native_asset,
            explorer_url=chain.explorer_url,
            assets=chain.assets,
            token_contracts=chain.token_contracts,
        )
        for chain in SUPPORTED_CHAINS.values()
    ]


def _normalize_token_contract(token_contract_address: str | None) -> str | None:
    if not token_contract_address:
        return None
    return normalize_address(token_contract_address)


def _resolve_asset_for_chain(
    chain_id: str,
    asset: AssetSymbol,
    token_contract_address: str | None,
) -> AssetSymbol:
    chain = get_chain(chain_id)
    asset_value = asset.value.upper()
    if token_contract_address:
        return AssetSymbol.erc20
    if asset_value == "ETH" and chain.native_asset != "ETH":
        return AssetSymbol(chain.native_asset)
    if is_native_asset(chain_id, asset_value):
        return AssetSymbol(asset_value)
    if resolve_token_contract(chain_id, asset_value):
        return AssetSymbol(asset_value)
    raise ValueError(
        f"Asset {asset_value} is not configured for chain_id {chain_id}. "
        "Provide token_contract_address for a custom ERC-20 asset."
    )


class InvestigationCreate(BaseModel):
    target: str = Field(..., min_length=42, max_length=66)
    chain_id: str = "1"
    asset: AssetSymbol = AssetSymbol.eth
    token_contract_address: str | None = Field(None, min_length=42, max_length=42)
    depth: int = Field(3, ge=1, le=5)
    mode: InvestigationMode = InvestigationMode.stable

    @model_validator(mode="after")
    def validate_target_chain_and_asset(self) -> "InvestigationCreate":
        self.chain_id = validate_chain_id(self.chain_id)
        self.target = normalize_hash(self.target) if len(self.target.strip()) == 66 else normalize_address(self.target)
        self.token_contract_address = _normalize_token_contract(self.token_contract_address)
        self.asset = _resolve_asset_for_chain(self.chain_id, self.asset, self.token_contract_address)
        return self


class InvestigationStatus(BaseModel):
    id: str
    target: str
    target_type: TargetType
    chain_id: str
    asset: AssetSymbol = AssetSymbol.eth
    token_contract_address: str | None = None
    depth: int
    mode: InvestigationMode
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    summary: str | None = None


class GraphNode(BaseModel):
    id: str
    address: str
    label: str
    hop: int
    node_type: str = "address"
    risk_score: float = 0
    risk_level: RiskLevel = RiskLevel.low
    tags: list[str] = Field(default_factory=list)
    source: str = "derived"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    tx_hash: str
    timestamp: int
    value_eth: float
    amount: float | None = None
    asset: str = "ETH"
    token_contract_address: str | None = None
    hop: int
    direction: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvestigationGraph(BaseModel):
    investigation_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RiskFinding(BaseModel):
    category: str
    severity: RiskLevel
    score: float
    subject: str
    evidence: str
    source: str
    hop: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskSourceHit(BaseModel):
    source: str
    category: str
    severity: RiskLevel
    address: str
    label: str
    evidence: str
    confidence: float = Field(1.0, ge=0, le=1)
    source_updated_at: datetime | None = None
    direct_hit: bool = False
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PatternSignal(BaseModel):
    name: str
    severity: RiskLevel
    score: float
    subject: str
    evidence: str
    confidence: float = Field(0.75, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkMetric(BaseModel):
    name: str
    value: float
    subject: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskResponse(BaseModel):
    investigation_id: str
    rule_score: float
    raindrop_score: float
    final_risk_score: float
    final_risk_level: RiskLevel
    findings: list[RiskFinding]
    top_risk_paths: list[list[str]]
    feature_summary: dict[str, float | int | str]
    pattern_signals: list[PatternSignal] = Field(default_factory=list)
    source_hits: list[RiskSourceHit] = Field(default_factory=list)
    network_metrics: list[NetworkMetric] = Field(default_factory=list)
    disposition_hint: RiskDisposition = RiskDisposition.allow
    recommended_actions: list[str] = Field(default_factory=list)


class ScreeningTransactionCreate(BaseModel):
    chain_id: str = "1"
    asset: AssetSymbol = AssetSymbol.eth
    token_contract_address: str | None = Field(None, min_length=42, max_length=42)
    direction: TransferDirection = TransferDirection.outbound
    from_address: str = Field(..., min_length=42, max_length=42)
    to_address: str = Field(..., min_length=42, max_length=42)
    amount: float = Field(..., gt=0)
    customer_id: str | None = None
    team_id: str | None = None
    tx_hash: str | None = Field(None, min_length=66, max_length=66)
    timestamp: int | None = None

    @model_validator(mode="after")
    def validate_screening_payload(self) -> "ScreeningTransactionCreate":
        self.chain_id = validate_chain_id(self.chain_id)
        self.from_address = normalize_address(self.from_address)
        self.to_address = normalize_address(self.to_address)
        if self.tx_hash:
            self.tx_hash = normalize_hash(self.tx_hash)
        self.token_contract_address = _normalize_token_contract(self.token_contract_address)
        self.asset = _resolve_asset_for_chain(self.chain_id, self.asset, self.token_contract_address)
        return self


class ScreeningResponse(BaseModel):
    id: str
    chain_id: str
    asset: AssetSymbol
    token_contract_address: str | None = None
    direction: TransferDirection
    from_address: str
    to_address: str
    amount: float
    risk_score: float
    risk_level: RiskLevel
    disposition: RiskDisposition
    findings: list[RiskFinding]
    pattern_signals: list[PatternSignal]
    source_hits: list[RiskSourceHit]
    evidence_summary: list[str]
    recommended_actions: list[str]
    data_freshness: dict[str, str]
    graph_investigation_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReportRequest(BaseModel):
    language: str = "en"
    include_raw_context: bool = True


class ReportResponse(BaseModel):
    investigation_id: str
    model: str
    report_markdown: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    used_external_llm: bool


class WatchlistEntry(BaseModel):
    address: str = Field(..., min_length=42, max_length=42)
    label: str = Field(..., min_length=1, max_length=160)
    category: str = Field("manual", min_length=1, max_length=80)
    severity: RiskLevel = RiskLevel.high
    notes: str = Field("", max_length=1000)

    @field_validator("address")
    @classmethod
    def validate_watchlist_address(cls, value: str) -> str:
        return normalize_address(value)


DIRECT_HIT_CATEGORIES: frozenset[str] = frozenset(
    {"ofac", "sanctions", "sanctioned", "pep", "circle_blacklist", "tether_blacklist", "stablecoin_blacklist"}
)


class WatchlistImportRequest(BaseModel):
    format: Literal["csv", "json"] = "csv"
    payload: str
    default_category: str = "manual"
    default_severity: RiskLevel = RiskLevel.high
    replace: bool = False


class WatchlistImportError(BaseModel):
    row: int
    reason: str


class WatchlistImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    direct_hit_count: int
    errors: list[WatchlistImportError] = Field(default_factory=list)


class ErrorPayload(BaseModel):
    code: str
    message: str
    category: Literal["validation", "not_found", "conflict", "upstream", "internal"]
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


class InvestigationRecord(BaseModel):
    status: InvestigationStatus
    graph: InvestigationGraph | None = None
    risk: RiskResponse | None = None
    reports: list[ReportResponse] = Field(default_factory=list)

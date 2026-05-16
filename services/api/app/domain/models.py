from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


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
    usdt = "USDT"
    usdc = "USDC"


class InvestigationCreate(BaseModel):
    target: str = Field(..., min_length=42, max_length=66)
    chain_id: str = "1"
    depth: int = Field(3, ge=1, le=5)
    mode: InvestigationMode = InvestigationMode.stable


class InvestigationStatus(BaseModel):
    id: str
    target: str
    target_type: TargetType
    chain_id: str
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
    direction: TransferDirection = TransferDirection.outbound
    from_address: str = Field(..., min_length=42, max_length=42)
    to_address: str = Field(..., min_length=42, max_length=42)
    amount: float = Field(..., ge=0)
    customer_id: str | None = None
    team_id: str | None = None
    tx_hash: str | None = Field(None, min_length=66, max_length=66)
    timestamp: int | None = None


class ScreeningResponse(BaseModel):
    id: str
    chain_id: str
    asset: AssetSymbol
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
    label: str
    category: str = "manual"
    severity: RiskLevel = RiskLevel.high
    notes: str = ""


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

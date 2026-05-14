from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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


class RiskResponse(BaseModel):
    investigation_id: str
    rule_score: float
    raindrop_score: float
    final_risk_score: float
    final_risk_level: RiskLevel
    findings: list[RiskFinding]
    top_risk_paths: list[list[str]]
    feature_summary: dict[str, float | int | str]


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
    address: str
    label: str
    category: str = "manual"
    severity: RiskLevel = RiskLevel.high
    notes: str = ""


class InvestigationRecord(BaseModel):
    status: InvestigationStatus
    graph: InvestigationGraph | None = None
    risk: RiskResponse | None = None
    reports: list[ReportResponse] = Field(default_factory=list)

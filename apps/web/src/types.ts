export type RiskLevel = "low" | "medium" | "high" | "critical";
export type RiskDisposition = "allow" | "review" | "hold_for_manual_review" | "reject";
export type TransferDirection = "inbound" | "outbound";
export type AssetSymbol = string;
export type AssetType = "native" | "erc20";

export interface InvestigationRecord {
  status: InvestigationStatus;
  graph?: InvestigationGraph;
  risk?: RiskResponse;
}

export interface InvestigationStatus {
  id: string;
  target: string;
  target_type: "address" | "transaction_hash";
  chain_id: string;
  depth: number;
  mode: "stable" | "experimental";
  status: string;
  summary?: string;
}

export interface GraphNode {
  id: string;
  address: string;
  label: string;
  hop: number;
  risk_score: number;
  risk_level: RiskLevel;
  tags: string[];
  source: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  tx_hash: string;
  value_eth: number;
  hop: number;
  metadata?: Record<string, unknown>;
}

export interface InvestigationGraph {
  investigation_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Finding {
  category: string;
  severity: RiskLevel;
  score: number;
  subject: string;
  evidence: string;
  source: string;
  hop?: number;
  metadata?: Record<string, unknown>;
}

export interface PatternSignal {
  name: string;
  severity: RiskLevel;
  score: number;
  subject: string;
  evidence: string;
  confidence: number;
  metadata: Record<string, unknown>;
}

export interface SourceHit {
  source: string;
  category: string;
  severity: RiskLevel;
  address: string;
  label: string;
  evidence: string;
  confidence: number;
  source_updated_at?: string | null;
  direct_hit: boolean;
  raw_payload?: Record<string, unknown>;
}

export interface RiskResponse {
  investigation_id: string;
  rule_score: number;
  raindrop_score: number;
  final_risk_score: number;
  final_risk_level: RiskLevel;
  findings: Finding[];
  top_risk_paths: string[][];
  feature_summary: Record<string, number | string>;
  pattern_signals: PatternSignal[];
  source_hits: SourceHit[];
  disposition_hint: RiskDisposition;
  recommended_actions: string[];
}

export interface ReportResponse {
  report_markdown: string;
  model: string;
  used_external_llm: boolean;
}

export interface ScreeningResponse {
  id: string;
  chain_id: string;
  asset: AssetSymbol;
  direction: TransferDirection;
  counterparty_address: string;
  from_address?: string | null;
  to_address?: string | null;
  amount: number;
  risk_score: number;
  risk_level: RiskLevel;
  disposition: RiskDisposition;
  findings: Finding[];
  pattern_signals: PatternSignal[];
  source_hits: SourceHit[];
  evidence_summary: string[];
  recommended_actions: string[];
  data_freshness: Record<string, string>;
  graph_investigation_id?: string | null;
  created_at?: string;
}

export interface ScreeningRequest {
  chain_id: string;
  direction: TransferDirection;
  asset?: string;
  asset_type?: AssetType;
  token_address?: string;
  counterparty_address: string;
  amount?: number;
  customer_id?: string;
  team_id?: string;
}

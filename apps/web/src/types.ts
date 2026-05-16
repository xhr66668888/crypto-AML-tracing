export type RiskLevel = "low" | "medium" | "high" | "critical";
export type RiskDisposition = "allow" | "review" | "hold_for_manual_review" | "reject";
export type TransferDirection = "inbound" | "outbound";
export type AssetSymbol = "ETH" | "USDT" | "USDC";

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
}

export interface PatternSignal {
  name: string;
  severity: RiskLevel;
  score: number;
  subject: string;
  evidence: string;
  confidence: number;
  metadata: Record<string, number | string | boolean>;
}

export interface SourceHit {
  source: string;
  category: string;
  severity: RiskLevel;
  address: string;
  label: string;
  evidence: string;
  confidence: number;
  direct_hit: boolean;
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
  from_address: string;
  to_address: string;
  amount: number;
  risk_score: number;
  risk_level: RiskLevel;
  disposition: RiskDisposition;
  findings: Finding[];
  pattern_signals: PatternSignal[];
  source_hits: SourceHit[];
  evidence_summary: string[];
  recommended_actions: string[];
}

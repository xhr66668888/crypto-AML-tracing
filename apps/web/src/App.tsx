import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  FileText,
  GitBranch,
  Loader2,
  Play,
  Shield,
  Target
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const DEMO_TARGET = "0x8a5847fd0e592b058c026c5fdc322aee834b87f5";
const DEMO_COUNTERPARTY = "0x1111111111111111111111111111111111111111";

type RiskLevel = "low" | "medium" | "high" | "critical";
type RiskDisposition = "allow" | "review" | "hold_for_manual_review" | "reject";
type TransferDirection = "inbound" | "outbound";
type AssetSymbol = "ETH" | "USDT" | "USDC";

interface InvestigationRecord {
  status: InvestigationStatus;
  graph?: InvestigationGraph;
  risk?: RiskResponse;
}

interface InvestigationStatus {
  id: string;
  target: string;
  target_type: "address" | "transaction_hash";
  chain_id: string;
  depth: number;
  mode: "stable" | "experimental";
  status: string;
  summary?: string;
}

interface GraphNode {
  id: string;
  address: string;
  label: string;
  hop: number;
  risk_score: number;
  risk_level: RiskLevel;
  tags: string[];
  source: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  tx_hash: string;
  value_eth: number;
  hop: number;
}

interface InvestigationGraph {
  investigation_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface Finding {
  category: string;
  severity: RiskLevel;
  score: number;
  subject: string;
  evidence: string;
  source: string;
  hop?: number;
}

interface PatternSignal {
  name: string;
  severity: RiskLevel;
  score: number;
  subject: string;
  evidence: string;
  confidence: number;
  metadata: Record<string, number | string | boolean>;
}

interface SourceHit {
  source: string;
  category: string;
  severity: RiskLevel;
  address: string;
  label: string;
  evidence: string;
  confidence: number;
  direct_hit: boolean;
}

interface RiskResponse {
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

interface ReportResponse {
  report_markdown: string;
  model: string;
  used_external_llm: boolean;
}

interface ScreeningResponse {
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

export default function App() {
  const [target, setTarget] = useState(DEMO_TARGET);
  const [depth, setDepth] = useState(3);
  const [mode, setMode] = useState<"stable" | "experimental">("stable");
  const [screeningFrom, setScreeningFrom] = useState(DEMO_TARGET);
  const [screeningTo, setScreeningTo] = useState(DEMO_COUNTERPARTY);
  const [screeningAmount, setScreeningAmount] = useState("9500");
  const [screeningAsset, setScreeningAsset] = useState<AssetSymbol>("USDC");
  const [screeningDirection, setScreeningDirection] = useState<TransferDirection>("outbound");
  const [screening, setScreening] = useState<ScreeningResponse | null>(null);
  const [record, setRecord] = useState<InvestigationRecord | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [screeningLoading, setScreeningLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");

  async function runScreening() {
    const amount = Number(screeningAmount);
    if (!Number.isFinite(amount) || amount < 0) {
      setError("Screening amount must be a positive number.");
      return;
    }
    setScreeningLoading(true);
    setError("");
    try {
      const result = await request<ScreeningResponse>("/api/v1/screening/transactions", {
        method: "POST",
        body: JSON.stringify({
          chain_id: "1",
          asset: screeningAsset,
          direction: screeningDirection,
          from_address: screeningFrom,
          to_address: screeningTo,
          amount
        })
      });
      setScreening(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screening failed");
    } finally {
      setScreeningLoading(false);
    }
  }

  async function runInvestigation() {
    setLoading(true);
    setError("");
    setReport(null);
    try {
      const created = await request<InvestigationRecord>("/api/v1/investigations", {
        method: "POST",
        body: JSON.stringify({ target, depth, mode, chain_id: "1" })
      });
      const graph = await request<InvestigationGraph>(`/api/v1/investigations/${created.status.id}/graph`);
      const risk = await request<RiskResponse>(`/api/v1/investigations/${created.status.id}/risk`);
      setRecord({ status: created.status, graph, risk });
      setSelectedNode(graph.nodes.find((node) => node.source === "target") ?? graph.nodes[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigation failed");
    } finally {
      setLoading(false);
    }
  }

  async function generateReport() {
    if (!record) return;
    setReportLoading(true);
    setError("");
    try {
      const nextReport = await request<ReportResponse>(`/api/v1/investigations/${record.status.id}/reports`, {
        method: "POST",
        body: JSON.stringify({ language: "en", include_raw_context: true })
      });
      setReport(nextReport);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setReportLoading(false);
    }
  }

  const findings = record?.risk?.findings ?? [];
  const highFindings = findings.slice(0, 6);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">C</div>
          <div className="eyebrow">Cregis AML Tracing</div>
          <h1>Risk Operations Workbench</h1>
        </div>
        <div className="status-pill">
          <Shield size={16} />
          ETH / USDT / USDC V1
        </div>
      </header>

      <section className="screening-strip">
        <div className="strip-header">
          <div>
            <div className="panel-title">
              <Shield size={18} />
              Pre-withdrawal Screening
            </div>
            <p>Live transfer control</p>
          </div>
          <button className="primary-button" onClick={runScreening} disabled={screeningLoading}>
            {screeningLoading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            Screen
          </button>
        </div>
        <div className="screening-grid">
          <label>
            <span>From address</span>
            <input value={screeningFrom} onChange={(event) => setScreeningFrom(event.target.value)} spellCheck={false} />
          </label>
          <label>
            <span>To address</span>
            <input value={screeningTo} onChange={(event) => setScreeningTo(event.target.value)} spellCheck={false} />
          </label>
          <label>
            <span>Asset</span>
            <select value={screeningAsset} onChange={(event) => setScreeningAsset(event.target.value as AssetSymbol)}>
              <option value="ETH">ETH</option>
              <option value="USDT">USDT</option>
              <option value="USDC">USDC</option>
            </select>
          </label>
          <label>
            <span>Direction</span>
            <select
              value={screeningDirection}
              onChange={(event) => setScreeningDirection(event.target.value as TransferDirection)}
            >
              <option value="outbound">Outbound</option>
              <option value="inbound">Inbound</option>
            </select>
          </label>
          <label>
            <span>Amount</span>
            <input value={screeningAmount} onChange={(event) => setScreeningAmount(event.target.value)} inputMode="decimal" />
          </label>
        </div>
      </section>

      <section className="query-strip">
        <label className="target-input">
          <span>Address or transaction hash</span>
          <input value={target} onChange={(event) => setTarget(event.target.value)} spellCheck={false} />
        </label>
        <label>
          <span>Depth</span>
          <select value={depth} onChange={(event) => setDepth(Number(event.target.value))}>
            <option value={1}>1 hop</option>
            <option value={2}>2 hops</option>
            <option value={3}>3 hops</option>
            <option value={5}>5 hops</option>
          </select>
        </label>
        <label>
          <span>Mode</span>
          <select value={mode} onChange={(event) => setMode(event.target.value as "stable" | "experimental")}>
            <option value="stable">Stable</option>
            <option value="experimental">Experimental</option>
          </select>
        </label>
        <button className="primary-button" onClick={runInvestigation} disabled={loading}>
          {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          Investigate
        </button>
      </section>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      <section className="workspace-grid">
        <aside className="left-column">
          <ScreeningSummary screening={screening} />
          <RiskSummary risk={record?.risk ?? null} />
          <EvidenceList findings={highFindings} />
        </aside>

        <section className="graph-panel">
          <div className="panel-header">
            <div>
              <h2>Transaction Graph</h2>
              <p>{record?.status.summary ?? "No graph loaded."}</p>
            </div>
            <GitBranch size={20} />
          </div>
          <GraphView graph={record?.graph ?? null} onSelectNode={setSelectedNode} />
        </section>

        <aside className="right-column">
          <NodeDetails node={selectedNode} />
          <PatternSignals signals={record?.risk?.pattern_signals ?? []} />
          <SourceHits hits={record?.risk?.source_hits ?? []} />
          <FeatureSummary risk={record?.risk ?? null} />
          <section className="panel">
            <div className="panel-title">
              <FileText size={18} />
              Report
            </div>
            <button className="secondary-button" onClick={generateReport} disabled={!record || reportLoading}>
              {reportLoading ? <Loader2 className="spin" size={16} /> : <FileText size={16} />}
              Generate English Report
            </button>
            {report && <pre className="report-preview">{report.report_markdown}</pre>}
          </section>
        </aside>
      </section>
    </main>
  );
}

function RiskSummary({ risk }: { risk: RiskResponse | null }) {
  return (
    <section className="panel score-panel">
      <div className="panel-title">
        <Target size={18} />
        Risk Summary
      </div>
      <div className={`score-dial ${risk?.final_risk_level ?? "low"}`}>
        <span>{risk ? Math.round(risk.final_risk_score) : "--"}</span>
        <small>{risk?.final_risk_level ?? "not run"}</small>
      </div>
      {risk && <div className={`risk-disposition ${risk.disposition_hint}`}>{risk.disposition_hint.replaceAll("_", " ")}</div>}
      <div className="metric-row">
        <Metric label="Rule" value={risk?.rule_score} icon={<Shield size={16} />} />
        <Metric label="Raindrop" value={risk?.raindrop_score} icon={<BrainCircuit size={16} />} />
      </div>
    </section>
  );
}

function Metric({ label, value, icon }: { label: string; value?: number; icon: ReactNode }) {
  return (
    <div className="metric">
      {icon}
      <span>{label}</span>
      <strong>{typeof value === "number" ? value.toFixed(1) : "--"}</strong>
    </div>
  );
}

function ScreeningSummary({ screening }: { screening: ScreeningResponse | null }) {
  return (
    <section className="panel screening-result">
      <div className="panel-title">
        <Shield size={18} />
        Screening Result
      </div>
      {!screening && <p className="empty">No screening result yet.</p>}
      {screening && (
        <>
          <div className={`disposition ${screening.disposition}`}>
            <span>{screening.disposition.replaceAll("_", " ")}</span>
            <strong>{Math.round(screening.risk_score)}</strong>
            <small>{screening.risk_level}</small>
          </div>
          <div className="screening-meta">
            <code>{compactAddress(screening.from_address)}</code>
            <span>to</span>
            <code>{compactAddress(screening.to_address)}</code>
          </div>
          <div className="tag-row">
            <span className="tag">{screening.asset}</span>
            <span className="tag">{screening.direction}</span>
            <span className="tag">{screening.amount.toLocaleString()}</span>
          </div>
          <ActionList title="Recommended Actions" items={screening.recommended_actions} />
          <ActionList title="Evidence Summary" items={screening.evidence_summary} />
        </>
      )}
    </section>
  );
}

function ActionList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="action-list">
      <strong>{title}</strong>
      {items.slice(0, 5).map((item) => (
        <p key={item}>{item}</p>
      ))}
    </div>
  );
}

function EvidenceList({ findings }: { findings: Finding[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <AlertTriangle size={18} />
        Evidence
      </div>
      <div className="evidence-list">
        {findings.length === 0 && <p className="empty">No evidence loaded.</p>}
        {findings.map((finding) => (
          <article key={`${finding.subject}-${finding.evidence}`} className={`finding ${finding.severity}`}>
            <div>
              <strong>{finding.severity.toUpperCase()}</strong>
              <span>{finding.category}</span>
            </div>
            <p>{finding.evidence}</p>
            <code>{compactAddress(finding.subject)}</code>
          </article>
        ))}
      </div>
    </section>
  );
}

function PatternSignals({ signals }: { signals: PatternSignal[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Activity size={18} />
        Pattern Signals
      </div>
      <div className="signal-list">
        {signals.length === 0 && <p className="empty">No pattern signals loaded.</p>}
        {signals.slice(0, 8).map((signal) => (
          <article className={`signal ${signal.severity}`} key={`${signal.name}-${signal.subject}`}>
            <div>
              <strong>{signal.name.replaceAll("_", " ")}</strong>
              <span>{signal.score.toFixed(1)}</span>
            </div>
            <p>{signal.evidence}</p>
            <code>{compactAddress(signal.subject)}</code>
          </article>
        ))}
      </div>
    </section>
  );
}

function SourceHits({ hits }: { hits: SourceHit[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Shield size={18} />
        Source Hits
      </div>
      <div className="source-list">
        {hits.length === 0 && <p className="empty">No source hits loaded.</p>}
        {hits.slice(0, 8).map((hit) => (
          <article className={`source-hit ${hit.severity}`} key={`${hit.source}-${hit.address}-${hit.category}`}>
            <div>
              <strong>{hit.direct_hit ? "DIRECT" : hit.source}</strong>
              <span>{hit.category}</span>
            </div>
            <p>{hit.evidence}</p>
            <code>{compactAddress(hit.address)}</code>
          </article>
        ))}
      </div>
    </section>
  );
}

function GraphView({
  graph,
  onSelectNode
}: {
  graph: InvestigationGraph | null;
  onSelectNode: (node: GraphNode) => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const nodeMap = useMemo(() => new Map((graph?.nodes ?? []).map((node) => [node.id, node])), [graph]);

  useEffect(() => {
    if (!ref.current || !graph) return;
    cyRef.current?.destroy();
    const elements = [
      ...graph.nodes.map((node) => ({
        data: { id: node.id, label: node.label, risk: node.risk_level, score: node.risk_score }
      })),
      ...graph.edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: `${edge.value_eth.toFixed(2)} ETH`
        }
      }))
    ];

    const cy = cytoscape({
      container: ref.current,
      elements,
      layout: { name: "cose", animate: false, fit: true, padding: 36 },
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#163300",
            label: "data(label)",
            color: "#0e0f0c",
            "font-size": 11,
            "text-valign": "bottom",
            "text-margin-y": 8,
            width: "mapData(score, 0, 100, 24, 58)",
            height: "mapData(score, 0, 100, 24, 58)",
            "border-color": "#9fe870",
            "border-width": 2
          }
        },
        { selector: 'node[risk = "medium"]', style: { "background-color": "#ffd11a", "border-color": "#b86700" } },
        { selector: 'node[risk = "high"]', style: { "background-color": "#ffc091", "border-color": "#b86700" } },
        { selector: 'node[risk = "critical"]', style: { "background-color": "#d03238", "border-color": "#a72027" } },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "#868685",
            "target-arrow-color": "#868685",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#454745",
            "font-size": 9,
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.9,
            "text-background-padding": "3px"
          }
        }
      ]
    });
    cy.on("tap", "node", (event) => {
      const node = nodeMap.get(event.target.id());
      if (node) onSelectNode(node);
    });
    cyRef.current = cy;
    return () => cy.destroy();
  }, [graph, nodeMap, onSelectNode]);

  if (!graph) {
    return (
      <div className="graph-empty">
        <Activity size={34} />
        <span>No graph loaded.</span>
      </div>
    );
  }
  return <div className="graph-canvas" ref={ref} />;
}

function NodeDetails({ node }: { node: GraphNode | null }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Target size={18} />
        Node Detail
      </div>
      {!node && <p className="empty">No node selected.</p>}
      {node && (
        <div className="node-detail">
          <code>{node.address}</code>
          <div className="detail-grid">
            <span>Hop</span>
            <strong>{node.hop}</strong>
            <span>Risk</span>
            <strong>{node.risk_score.toFixed(1)}</strong>
            <span>Level</span>
            <strong>{node.risk_level}</strong>
          </div>
          <div className="tag-row">
            {node.tags.length === 0 && <span className="tag neutral">no tags</span>}
            {node.tags.map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function FeatureSummary({ risk }: { risk: RiskResponse | null }) {
  const entries = Object.entries(risk?.feature_summary ?? {});
  return (
    <section className="panel">
      <div className="panel-title">
        <BrainCircuit size={18} />
        Raindrop Features
      </div>
      <div className="feature-grid">
        {entries.length === 0 && <p className="empty">No feature set.</p>}
        {entries.map(([key, value]) => (
          <div key={key}>
            <span>{key.replaceAll("_", " ")}</span>
            <strong>{String(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || response.statusText);
  }
  return response.json() as Promise<T>;
}

function compactAddress(address: string) {
  if (address.length <= 14) return address;
  return `${address.slice(0, 8)}...${address.slice(-6)}`;
}

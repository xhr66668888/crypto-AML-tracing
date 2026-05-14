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

type RiskLevel = "low" | "medium" | "high" | "critical";

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

interface RiskResponse {
  investigation_id: string;
  rule_score: number;
  raindrop_score: number;
  final_risk_score: number;
  final_risk_level: RiskLevel;
  findings: Finding[];
  top_risk_paths: string[][];
  feature_summary: Record<string, number | string>;
}

interface ReportResponse {
  report_markdown: string;
  model: string;
  used_external_llm: boolean;
}

export default function App() {
  const [target, setTarget] = useState(DEMO_TARGET);
  const [depth, setDepth] = useState(3);
  const [mode, setMode] = useState<"stable" | "experimental">("stable");
  const [record, setRecord] = useState<InvestigationRecord | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState("");

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
        <div>
          <div className="eyebrow">Cregis AML Tracing</div>
          <h1>Ethereum Investigation Workbench</h1>
        </div>
        <div className="status-pill">
          <Shield size={16} />
          Local-first MVP
        </div>
      </header>

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
          Run
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
          <RiskSummary risk={record?.risk ?? null} />
          <EvidenceList findings={highFindings} />
        </aside>

        <section className="graph-panel">
          <div className="panel-header">
            <div>
              <h2>Transaction Graph</h2>
              <p>{record?.status.summary ?? "Run an investigation to render graph evidence."}</p>
            </div>
            <GitBranch size={20} />
          </div>
          <GraphView graph={record?.graph ?? null} onSelectNode={setSelectedNode} />
        </section>

        <aside className="right-column">
          <NodeDetails node={selectedNode} />
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
            "background-color": "#4f6f52",
            label: "data(label)",
            color: "#dfe8df",
            "font-size": 11,
            "text-valign": "bottom",
            "text-margin-y": 8,
            width: "mapData(score, 0, 100, 24, 58)",
            height: "mapData(score, 0, 100, 24, 58)",
            "border-color": "#dfe8df",
            "border-width": 1
          }
        },
        { selector: 'node[risk = "medium"]', style: { "background-color": "#c0a23f" } },
        { selector: 'node[risk = "high"]', style: { "background-color": "#c9653a" } },
        { selector: 'node[risk = "critical"]', style: { "background-color": "#c43d4b" } },
        {
          selector: "edge",
          style: {
            width: 1.4,
            "line-color": "#78928a",
            "target-arrow-color": "#78928a",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#aebdb7",
            "font-size": 9,
            "text-background-color": "#111817",
            "text-background-opacity": 0.75,
            "text-background-padding": "2px"
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
        <span>Graph evidence will appear here.</span>
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
      {!node && <p className="empty">Select a node to inspect labels.</p>}
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
        {entries.length === 0 && <p className="empty">Run an investigation to compute features.</p>}
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

import { useEffect, useState } from "react";
import { Play, Loader2, AlertTriangle, GitBranch, BarChart3, FileText, ListChecks } from "lucide-react";
import type { InvestigationRecord, InvestigationGraph, RiskResponse, GraphNode, ChainInfo, AssetSymbol } from "../types";
import { request } from "../api";
import { RiskSummary } from "./RiskSummary";
import { GraphView } from "./GraphView";
import { EvidenceList } from "./EvidenceList";
import { ReportPreview } from "./ReportPreview";
import { PatternSignals, SourceHits, NodeDetails } from "./PanelWidgets";

const DEMO_TARGET = "0x8a5847fd0e592b058c026c5fdc322aee834b87f5";

type TabId = "overview" | "graph" | "evidence" | "report";

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <BarChart3 size={16} /> },
  { id: "graph", label: "Graph", icon: <GitBranch size={16} /> },
  { id: "evidence", label: "Evidence", icon: <ListChecks size={16} /> },
  { id: "report", label: "Report", icon: <FileText size={16} /> }
];

export function InvestigationPanel({ chains }: { chains: ChainInfo[] }) {
  const [target, setTarget] = useState(DEMO_TARGET);
  const [chainId, setChainId] = useState("1");
  const [asset, setAsset] = useState<AssetSymbol>("ETH");
  const [tokenContract, setTokenContract] = useState("");
  const [depth, setDepth] = useState(3);
  const [mode, setMode] = useState<"stable" | "experimental">("stable");
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [record, setRecord] = useState<InvestigationRecord | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const currentChain = chains.find((chain) => chain.chain_id === chainId) ?? chains[0];
  const assetOptions = Array.from(new Set([...(currentChain?.assets ?? ["ETH", "USDC", "USDT"]), "ERC20"])) as AssetSymbol[];

  useEffect(() => {
    if (asset !== "ERC20" && !assetOptions.includes(asset)) {
      setAsset((currentChain?.native_asset as AssetSymbol) ?? "ETH");
    }
  }, [asset, assetOptions, currentChain?.native_asset]);

  async function runInvestigation() {
    if (!target.trim()) {
      setError("Enter an address or transaction hash to investigate.");
      return;
    }
    if (asset === "ERC20" && !tokenContract.trim()) {
      setError("Token contract is required for custom ERC-20 investigation.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const created = await request<InvestigationRecord>("/api/v1/investigations", {
        method: "POST",
        body: JSON.stringify({
          target: target.trim(),
          depth,
          mode,
          chain_id: chainId,
          asset,
          token_contract_address: asset === "ERC20" ? tokenContract.trim() : undefined
        })
      });
      const graph = await request<InvestigationGraph>(
        `/api/v1/investigations/${created.status.id}/graph`
      );
      const risk = await request<RiskResponse>(
        `/api/v1/investigations/${created.status.id}/risk`
      );
      setRecord({ status: created.status, graph, risk });
      setSelectedNode(graph.nodes.find((n) => n.source === "target") ?? graph.nodes[0] ?? null);
      setActiveTab("overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Investigation failed");
    } finally {
      setLoading(false);
    }
  }

  const findings = record?.risk?.findings ?? [];
  const highFindings = findings.slice(0, 8);

  return (
    <div className="investigation-panel">
      <div className="query-strip">
        <label className="target-input">
          <span>Address or transaction hash</span>
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            spellCheck={false}
            placeholder="0x..."
          />
        </label>
        <label>
          <span>Chain</span>
          <select value={chainId} onChange={(e) => setChainId(e.target.value)}>
            {chains.map((chain) => (
              <option value={chain.chain_id} key={chain.chain_id}>
                {chain.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Asset</span>
          <select value={asset} onChange={(e) => setAsset(e.target.value as AssetSymbol)}>
            {assetOptions.map((option) => (
              <option value={option} key={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        {asset === "ERC20" && (
          <label className="wide-field">
            <span>Token contract</span>
            <input
              value={tokenContract}
              onChange={(e) => setTokenContract(e.target.value)}
              spellCheck={false}
              placeholder="0x..."
            />
          </label>
        )}
        <label>
          <span>Depth</span>
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={1}>1 hop</option>
            <option value={2}>2 hops</option>
            <option value={3}>3 hops</option>
            <option value={5}>5 hops</option>
          </select>
        </label>
        <label>
          <span>Mode</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as "stable" | "experimental")}>
            <option value="stable">Stable</option>
            <option value="experimental">Experimental</option>
          </select>
        </label>
        <button className="primary-button" onClick={runInvestigation} disabled={loading}>
          {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          Investigate
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      <div className="investigation-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === "overview" && (
          <OverviewTab
            record={record}
            loading={loading}
            selectedNode={selectedNode}
            findings={highFindings}
          />
        )}
        {activeTab === "graph" && (
          <GraphTab
            graph={record?.graph ?? null}
            loading={loading}
            onSelectNode={setSelectedNode}
            summary={record?.status.summary}
          />
        )}
        {activeTab === "evidence" && (
          <EvidenceTab risk={record?.risk ?? null} />
        )}
        {activeTab === "report" && (
          <ReportPreview investigationId={record?.status.id ?? null} />
        )}
      </div>
    </div>
  );
}

function OverviewTab({
  record,
  loading,
  selectedNode,
  findings
}: {
  record: InvestigationRecord | null;
  loading: boolean;
  selectedNode: GraphNode | null;
  findings: import("../types").Finding[];
}) {
  if (loading) {
    return (
      <div className="overview-loading">
        <div className="skeleton-card" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
      </div>
    );
  }

  if (!record) {
    return (
      <div className="empty-state large">
        <GitBranch size={48} />
        <h3>No investigation data</h3>
        <p>Enter an address above and click "Investigate" to begin analysis.</p>
      </div>
    );
  }

  return (
    <div className="overview-grid">
      <RiskSummary risk={record.risk ?? null} />
      <NodeDetails node={selectedNode} />
      <EvidenceList findings={findings} />
    </div>
  );
}

function GraphTab({
  graph,
  loading,
  onSelectNode,
  summary
}: {
  graph: InvestigationGraph | null;
  loading: boolean;
  onSelectNode: (node: GraphNode) => void;
  summary?: string;
}) {
  return (
    <div className="graph-panel">
      <div className="panel-header">
        <div>
          <h2>Transaction Graph</h2>
          <p>{summary ?? "No graph loaded."}</p>
        </div>
        <GitBranch size={20} />
      </div>
      <GraphView graph={graph} onSelectNode={onSelectNode} loading={loading} />
    </div>
  );
}

function EvidenceTab({ risk }: { risk: RiskResponse | null }) {
  if (!risk) {
    return (
      <div className="empty-state large">
        <ListChecks size={48} />
        <h3>No evidence available</h3>
        <p>Run an investigation to collect pattern signals and source hits.</p>
      </div>
    );
  }

  return (
    <div className="evidence-grid">
      <PatternSignals signals={risk.pattern_signals ?? []} />
      <SourceHits hits={risk.source_hits ?? []} />
    </div>
  );
}

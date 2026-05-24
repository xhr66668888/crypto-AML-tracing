import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Download,
  FileJson,
  Loader2,
  OctagonAlert,
  Play,
  ShieldAlert,
  ShieldCheck
} from "lucide-react";
import type {
  AssetType,
  Finding,
  PatternSignal,
  RiskDisposition,
  ScreeningRequest,
  ScreeningResponse,
  SourceHit,
  TransferDirection
} from "../types";
import { compactAddress, request } from "../api";

const DEMO_COUNTERPARTY = "0x1111111111111111111111111111111111111111";

const ASSETS: { symbol: string; label: string; assetType: AssetType; tokenAddress?: string }[] = [
  { symbol: "ETH", label: "ETH", assetType: "native" },
  { symbol: "USDC", label: "USDC", assetType: "erc20", tokenAddress: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48" },
  { symbol: "USDT", label: "USDT", assetType: "erc20", tokenAddress: "0xdac17f958d2ee523a2206206994597c13d831ec7" },
  { symbol: "DAI", label: "DAI", assetType: "erc20", tokenAddress: "0x6b175474e89094c44da98b954eedeac495271d0f" },
  { symbol: "WETH", label: "WETH", assetType: "erc20", tokenAddress: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2" },
  { symbol: "WBTC", label: "WBTC", assetType: "erc20", tokenAddress: "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599" }
];

export function ScreeningPanel({ demoMode }: { demoMode: boolean | null }) {
  const [chainId, setChainId] = useState("1");
  const [direction, setDirection] = useState<TransferDirection>("outbound");
  const [assetChoice, setAssetChoice] = useState("USDC");
  const [customSymbol, setCustomSymbol] = useState("TOKEN");
  const [customTokenAddress, setCustomTokenAddress] = useState("");
  const [counterpartyAddress, setCounterpartyAddress] = useState(DEMO_COUNTERPARTY);
  const [amount, setAmount] = useState("9500");
  const [customerId, setCustomerId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [result, setResult] = useState<ScreeningResponse | null>(null);
  const [history, setHistory] = useState<ScreeningResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copyState, setCopyState] = useState<"idle" | "copied">("idle");

  const selectedAsset = useMemo(() => ASSETS.find((asset) => asset.symbol === assetChoice), [assetChoice]);
  const isCustomAsset = assetChoice === "CUSTOM";
  const effectiveSymbol = isCustomAsset ? customSymbol.trim().toUpperCase() : assetChoice;
  const effectiveAssetType: AssetType = isCustomAsset ? "erc20" : selectedAsset?.assetType ?? "erc20";
  const effectiveTokenAddress = isCustomAsset ? customTokenAddress.trim() : selectedAsset?.tokenAddress;

  async function runScreening() {
    setError("");
    setCopyState("idle");

    const payload = buildPayload();
    if (!payload) return;

    setLoading(true);
    try {
      const data = await request<ScreeningResponse>("/api/v1/screening/pre-transactions", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setResult(data);
      setHistory((items) => [data, ...items.filter((item) => item.id !== data.id)].slice(0, 6));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screening failed");
    } finally {
      setLoading(false);
    }
  }

  function buildPayload(): ScreeningRequest | null {
    const base: ScreeningRequest = {
      chain_id: chainId,
      direction,
      counterparty_address: counterpartyAddress.trim(),
      customer_id: customerId.trim() || undefined,
      team_id: teamId.trim() || undefined
    };

    const amountNum = Number(amount);
    if (!Number.isFinite(amountNum) || amountNum <= 0) {
      setError("Amount must be a positive number.");
      return null;
    }
    if (!counterpartyAddress.trim()) {
      setError("Counterparty address is required.");
      return null;
    }
    if (!effectiveSymbol) {
      setError("Asset symbol is required.");
      return null;
    }
    if (effectiveAssetType === "erc20" && !effectiveTokenAddress) {
      setError("ERC-20 screening requires a token contract address.");
      return null;
    }

    return {
      ...base,
      asset: effectiveSymbol,
      asset_type: effectiveAssetType,
      token_address: effectiveTokenAddress || undefined,
      amount: amountNum
    };
  }

  async function copyResult() {
    if (!result) return;
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    setCopyState("copied");
    window.setTimeout(() => setCopyState("idle"), 1600);
  }

  function exportResult() {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `screening-${result.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="screening-console">
      <div className="console-grid">
        <section className="screening-form-panel" aria-label="Screening input">
          <div className="section-heading">
            <div>
              <h2>Pre-Transaction Screening</h2>
              <span>{direction === "outbound" ? "Outbound recipient" : "Inbound source"}</span>
            </div>
            {demoMode === true && <span className="demo-badge">DEMONSTRATION DATA</span>}
          </div>

          <div className="form-stack">
            <div className="field-grid two">
              <label>
                <span>Workflow</span>
                <select value={direction} onChange={(event) => setDirection(event.target.value as TransferDirection)}>
                  <option value="outbound">Outbound request</option>
                  <option value="inbound">Inbound source</option>
                </select>
              </label>
              <label>
                <span>Chain</span>
                <select value={chainId} onChange={(event) => setChainId(event.target.value)}>
                  <option value="1">Ethereum Mainnet</option>
                </select>
              </label>
            </div>

            <div className="field-grid two">
              <label>
                <span>Asset</span>
                <select value={assetChoice} onChange={(event) => setAssetChoice(event.target.value)}>
                  {ASSETS.map((asset) => (
                    <option value={asset.symbol} key={asset.symbol}>
                      {asset.label}
                    </option>
                  ))}
                  <option value="CUSTOM">Custom ERC-20</option>
                </select>
              </label>
              <label>
                <span>Amount</span>
                <input value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" />
              </label>
            </div>

            {isCustomAsset && (
              <div className="field-grid two">
                <label>
                  <span>Symbol</span>
                  <input value={customSymbol} onChange={(event) => setCustomSymbol(event.target.value)} />
                </label>
                <label>
                  <span>Token Contract</span>
                  <input
                    value={customTokenAddress}
                    onChange={(event) => setCustomTokenAddress(event.target.value)}
                    spellCheck={false}
                    placeholder="0x..."
                  />
                </label>
              </div>
            )}

            <label>
              <span>{direction === "outbound" ? "Recipient Address" : "Source Address"}</span>
              <input
                value={counterpartyAddress}
                onChange={(event) => setCounterpartyAddress(event.target.value)}
                spellCheck={false}
                placeholder="0x..."
              />
            </label>

            <div className="field-grid two">
              <label>
                <span>Customer ID</span>
                <input value={customerId} onChange={(event) => setCustomerId(event.target.value)} />
              </label>
              <label>
                <span>Team ID</span>
                <input value={teamId} onChange={(event) => setTeamId(event.target.value)} />
              </label>
            </div>

            {error && (
              <div className="inline-error">
                <AlertTriangle size={14} />
                <span>{error}</span>
              </div>
            )}

            <button className="primary-button full-width" onClick={runScreening} disabled={loading}>
              {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              Run Pre-Transaction Screening
            </button>
          </div>

          <RecentScreenings history={history} onSelect={setResult} />
        </section>

        <section className="decision-panel" aria-label="Screening decision">
          {loading ? <DecisionLoading /> : result ? (
            <ScreeningResult
              result={result}
              demoMode={demoMode}
              copyState={copyState}
              onCopy={copyResult}
              onExport={exportResult}
            />
          ) : (
            <DecisionEmpty />
          )}
        </section>
      </div>
    </section>
  );
}

function ScreeningResult({
  result,
  demoMode,
  copyState,
  onCopy,
  onExport
}: {
  result: ScreeningResponse;
  demoMode: boolean | null;
  copyState: "idle" | "copied";
  onCopy: () => void;
  onExport: () => void;
}) {
  const icon = dispositionIcon(result.disposition);
  const hits = result.source_hits ?? [];
  const signals = result.pattern_signals ?? [];
  const findings = result.findings ?? [];

  return (
    <div className="decision-content">
      <div className={`decision-hero ${result.disposition}`}>
        <div>
          <span className="decision-label">Decision</span>
          <h2>{formatDisposition(result.disposition)}</h2>
          <p>{result.risk_level.toUpperCase()} RISK</p>
        </div>
        <div className="decision-score">
          {icon}
          <strong>{Math.round(result.risk_score)}</strong>
        </div>
      </div>

      <div className="decision-toolbar">
        {demoMode === true && <span className="demo-badge">DEMONSTRATION DATA</span>}
        <button type="button" className="icon-button" onClick={onCopy} title="Copy result JSON" aria-label="Copy result JSON">
          <Clipboard size={16} />
          {copyState === "copied" ? "Copied" : "Copy"}
        </button>
        <button type="button" className="icon-button" onClick={onExport} title="Export result JSON" aria-label="Export result JSON">
          <Download size={16} />
          Export
        </button>
      </div>

      <div className="transaction-snapshot">
        <div>
          <span>Asset</span>
          <strong>{result.asset}</strong>
        </div>
        <div>
          <span>Amount</span>
          <strong>{formatNumber(result.amount)}</strong>
        </div>
        <div>
          <span>Workflow</span>
          <strong>{formatWorkflow(result.direction)}</strong>
        </div>
        <div>
          <span>Counterparty</span>
          <strong>{compactAddress(result.counterparty_address)}</strong>
        </div>
      </div>

      <div className="counterparty-route">
        <span>{result.direction === "outbound" ? "Recipient address" : "Source address"}</span>
        <code title={result.counterparty_address}>{result.counterparty_address}</code>
      </div>

      <div className="decision-metrics">
        <Metric label="Source hits" value={hits.length} />
        <Metric label="Signals" value={signals.length} />
        <Metric label="Findings" value={findings.length} />
        <Metric label="Freshness" value={Object.keys(result.data_freshness ?? {}).length} />
      </div>

      <EvidenceSummary title="Recommended Actions" items={result.recommended_actions} />
      <EvidenceSummary title="Evidence Summary" items={result.evidence_summary} />

      <div className="result-columns">
        <SourceHitList hits={hits} />
        <SignalList signals={signals} />
      </div>

      <FindingList findings={findings} />
    </div>
  );
}

function EvidenceSummary({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="evidence-band">
      <div className="band-title">
        <FileJson size={16} />
        <h3>{title}</h3>
      </div>
      {items.length === 0 ? (
        <p className="quiet-line">No entries.</p>
      ) : (
        <div className="evidence-lines">
          {items.slice(0, 6).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      )}
    </section>
  );
}

function SourceHitList({ hits }: { hits: SourceHit[] }) {
  return (
    <section className="result-list">
      <div className="band-title">
        <ShieldAlert size={16} />
        <h3>Source Hits</h3>
        <span>{hits.length}</span>
      </div>
      {hits.length === 0 ? (
        <p className="quiet-line">No source hits.</p>
      ) : (
        hits.slice(0, 6).map((hit) => (
          <article className={`evidence-card ${hit.severity}`} key={`${hit.source}-${hit.address}-${hit.category}`}>
            <div>
              <strong>{hit.direct_hit ? "DIRECT HIT" : hit.source}</strong>
              <span>{hit.category}</span>
            </div>
            <p>{hit.evidence}</p>
            <code title={hit.address}>{compactAddress(hit.address)}</code>
          </article>
        ))
      )}
    </section>
  );
}

function SignalList({ signals }: { signals: PatternSignal[] }) {
  return (
    <section className="result-list">
      <div className="band-title">
        <ShieldCheck size={16} />
        <h3>Pattern Signals</h3>
        <span>{signals.length}</span>
      </div>
      {signals.length === 0 ? (
        <p className="quiet-line">No pattern signals.</p>
      ) : (
        signals.slice(0, 6).map((signal) => (
          <article className={`evidence-card ${signal.severity}`} key={`${signal.name}-${signal.subject}`}>
            <div>
              <strong>{signal.name.replaceAll("_", " ")}</strong>
              <span>{signal.score.toFixed(1)}</span>
            </div>
            <p>{signal.evidence}</p>
            <code title={signal.subject}>{compactAddress(signal.subject)}</code>
          </article>
        ))
      )}
    </section>
  );
}

function FindingList({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) return null;
  return (
    <section className="result-list wide">
      <div className="band-title">
        <OctagonAlert size={16} />
        <h3>Findings</h3>
        <span>{findings.length}</span>
      </div>
      {findings.slice(0, 5).map((finding) => (
        <article className={`evidence-card ${finding.severity}`} key={`${finding.source}-${finding.subject}-${finding.category}`}>
          <div>
            <strong>{finding.category}</strong>
            <span>{finding.score.toFixed(1)}</span>
          </div>
          <p>{finding.evidence}</p>
          <code title={finding.subject}>{compactAddress(finding.subject)}</code>
        </article>
      ))}
    </section>
  );
}

function RecentScreenings({
  history,
  onSelect
}: {
  history: ScreeningResponse[];
  onSelect: (result: ScreeningResponse) => void;
}) {
  return (
    <section className="recent-screenings">
      <div className="section-heading compact">
        <h3>Recent Decisions</h3>
        <span>{history.length}</span>
      </div>
      {history.length === 0 ? (
        <p className="quiet-line">No decisions in this session.</p>
      ) : (
        <div className="recent-list">
          {history.map((item) => (
            <button type="button" key={item.id} onClick={() => onSelect(item)} className={`recent-item ${item.disposition}`}>
              <span>{formatDisposition(item.disposition)}</span>
              <strong>{item.asset}</strong>
              <code>{compactAddress(item.counterparty_address)}</code>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function DecisionEmpty() {
  return (
    <div className="decision-empty">
      <ShieldCheck size={42} />
      <h2>No decision loaded</h2>
      <div className="transaction-snapshot muted">
        <div>
          <span>Decision</span>
          <strong>--</strong>
        </div>
        <div>
          <span>Score</span>
          <strong>--</strong>
        </div>
        <div>
          <span>Evidence</span>
          <strong>--</strong>
        </div>
      </div>
    </div>
  );
}

function DecisionLoading() {
  return (
    <div className="decision-loading">
      <Loader2 className="spin" size={32} />
      <div className="skeleton-line w90" />
      <div className="skeleton-line w60" />
      <div className="skeleton-card" />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function dispositionIcon(disposition: RiskDisposition) {
  if (disposition === "allow") return <CheckCircle2 size={26} />;
  if (disposition === "hold_for_manual_review" || disposition === "reject") return <OctagonAlert size={26} />;
  return <AlertTriangle size={26} />;
}

function formatDisposition(disposition: RiskDisposition) {
  if (disposition === "hold_for_manual_review") return "Hold for review";
  return disposition.replaceAll("_", " ");
}

function formatWorkflow(direction: TransferDirection) {
  return direction === "outbound" ? "Outbound request" : "Inbound source";
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 8 }).format(value);
}

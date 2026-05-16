import { useState } from "react";
import { Shield, Play, Loader2, AlertTriangle } from "lucide-react";
import type {
  ScreeningResponse,
  AssetSymbol,
  TransferDirection,
  Finding,
  PatternSignal,
  SourceHit
} from "../types";
import { request, compactAddress } from "../api";

const DEMO_FROM = "0x8a5847fd0e592b058c026c5fdc322aee834b87f5";
const DEMO_TO = "0x1111111111111111111111111111111111111111";

export function ScreeningPanel() {
  const [fromAddress, setFromAddress] = useState(DEMO_FROM);
  const [toAddress, setToAddress] = useState(DEMO_TO);
  const [amount, setAmount] = useState("9500");
  const [asset, setAsset] = useState<AssetSymbol>("USDC");
  const [direction, setDirection] = useState<TransferDirection>("outbound");
  const [result, setResult] = useState<ScreeningResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runScreening() {
    const amountNum = Number(amount);
    if (!Number.isFinite(amountNum) || amountNum < 0) {
      setError("Amount must be a positive number.");
      return;
    }
    if (!fromAddress.trim()) {
      setError("From address is required.");
      return;
    }
    if (!toAddress.trim()) {
      setError("To address is required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await request<ScreeningResponse>("/api/v1/screening/transactions", {
        method: "POST",
        body: JSON.stringify({
          chain_id: "1",
          asset,
          direction,
          from_address: fromAddress.trim(),
          to_address: toAddress.trim(),
          amount: amountNum
        })
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Screening failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="screening-strip">
      <div className="strip-header">
        <div>
          <div className="panel-title">
            <Shield size={18} />
            Pre-withdrawal Screening
          </div>
          <p>Live transfer control — ETH / USDT / USDC</p>
        </div>
        <button className="primary-button" onClick={runScreening} disabled={loading}>
          {loading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
          Screen
        </button>
      </div>
      <div className="screening-grid">
        <label>
          <span>From address</span>
          <input
            value={fromAddress}
            onChange={(e) => setFromAddress(e.target.value)}
            spellCheck={false}
            placeholder="0x..."
          />
        </label>
        <label>
          <span>To address</span>
          <input
            value={toAddress}
            onChange={(e) => setToAddress(e.target.value)}
            spellCheck={false}
            placeholder="0x..."
          />
        </label>
        <label>
          <span>Asset</span>
          <select value={asset} onChange={(e) => setAsset(e.target.value as AssetSymbol)}>
            <option value="ETH">ETH</option>
            <option value="USDT">USDT</option>
            <option value="USDC">USDC</option>
          </select>
        </label>
        <label>
          <span>Direction</span>
          <select value={direction} onChange={(e) => setDirection(e.target.value as TransferDirection)}>
            <option value="outbound">Outbound</option>
            <option value="inbound">Inbound</option>
          </select>
        </label>
        <label>
          <span>Amount</span>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
        </label>
      </div>
      {error && (
        <div className="inline-error">
          <AlertTriangle size={14} />
          <span>{error}</span>
        </div>
      )}
      {loading && (
        <div className="screening-skeleton">
          <div className="skeleton-line w80" />
          <div className="skeleton-line w60" />
          <div className="skeleton-line w90" />
        </div>
      )}
      {result && !loading && <ScreeningResult result={result} />}
    </section>
  );
}

function ScreeningResult({ result }: { result: ScreeningResponse }) {
  const findings = result.findings ?? [];
  const signals = result.pattern_signals ?? [];
  const hits = result.source_hits ?? [];

  return (
    <div className="screening-results">
      <div className="screening-result-grid">
        <div className={`disposition ${result.disposition}`}>
          <span>{result.disposition.replaceAll("_", " ")}</span>
          <strong>{Math.round(result.risk_score)}</strong>
          <small>{result.risk_level}</small>
        </div>
        <div className="screening-meta">
          <code title={result.from_address}>{compactAddress(result.from_address)}</code>
          <span>to</span>
          <code title={result.to_address}>{compactAddress(result.to_address)}</code>
        </div>
        <div className="tag-row">
          <span className="tag">{result.asset}</span>
          <span className="tag">{result.direction}</span>
          <span className="tag">{result.amount.toLocaleString()}</span>
        </div>
      </div>

      {result.recommended_actions.length > 0 && (
        <div className="action-list">
          <strong>Recommended Actions</strong>
          {result.recommended_actions.slice(0, 5).map((action) => (
            <p key={action}>{action}</p>
          ))}
        </div>
      )}

      {result.evidence_summary.length > 0 && (
        <div className="action-list">
          <strong>Evidence Summary</strong>
          {result.evidence_summary.slice(0, 5).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      )}

      {hits.length > 0 && (
        <div className="screening-detail-section">
          <strong>Source Hits ({hits.length})</strong>
          {hits.slice(0, 3).map((hit) => (
            <article key={`${hit.source}-${hit.address}`} className={`source-hit ${hit.severity}`}>
              <div>
                <strong>{hit.direct_hit ? "DIRECT" : hit.source}</strong>
                <span>{hit.category}</span>
              </div>
              <p>{hit.evidence}</p>
            </article>
          ))}
        </div>
      )}

      {signals.length > 0 && (
        <div className="screening-detail-section">
          <strong>Pattern Signals ({signals.length})</strong>
          {signals.slice(0, 3).map((signal) => (
            <article key={`${signal.name}-${signal.subject}`} className={`signal ${signal.severity}`}>
              <div>
                <strong>{signal.name.replaceAll("_", " ")}</strong>
                <span>{signal.score.toFixed(1)}</span>
              </div>
              <p>{signal.evidence}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

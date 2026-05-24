import { useEffect, useState } from "react";
import { Shield, Database, AlertTriangle, Wifi, WifiOff } from "lucide-react";
import { ScreeningPanel } from "./components/ScreeningPanel";
import { InvestigationPanel } from "./components/InvestigationPanel";
import { WatchlistPanel } from "./components/WatchlistPanel";
import { request } from "./api";
import type { ChainInfo } from "./types";

type PanelView = "screening" | "investigation" | "watchlist";

const DEFAULT_CHAINS: ChainInfo[] = [
  {
    chain_id: "1",
    name: "Ethereum Mainnet",
    native_asset: "ETH",
    explorer_url: "https://etherscan.io",
    assets: ["ETH", "USDC", "USDT"],
    token_contracts: {}
  }
];

export default function App() {
  const [activePanel, setActivePanel] = useState<PanelView>("screening");
  const [connectionStatus, setConnectionStatus] = useState<"unknown" | "connected" | "error">("unknown");
  const [chains, setChains] = useState<ChainInfo[]>(DEFAULT_CHAINS);
  const [demoMode, setDemoMode] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    
    // Fetch health for demo mode status
    fetch(`${import.meta.env.VITE_API_BASE}/health`)
      .then(r => r.json())
      .then(d => {
        if (!cancelled) setDemoMode(Boolean(d.demo_mode));
      })
      .catch(() => {
        if (!cancelled) setDemoMode(null);
      });

    // Fetch chains
    request<ChainInfo[]>("/api/v1/chains")
      .then((data) => {
        if (!cancelled) {
          setChains(data.length > 0 ? data : DEFAULT_CHAINS);
          setConnectionStatus("connected");
        }
      })
      .catch(() => {
        if (!cancelled) setConnectionStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">C</div>
          <div>
            <div className="eyebrow">Cregis AML Tracing</div>
            <h1>Risk Operations Workbench</h1>
          </div>
        </div>
        <div className="topbar-right">
          <div className="status-pill">
            <Shield size={16} />
            EVM multi-chain
            {connectionStatus === "connected" ? (
              <Wifi size={14} style={{ marginLeft: '8px', color: '#4ade80' }} />
            ) : connectionStatus === "error" ? (
              <WifiOff size={14} style={{ marginLeft: '8px', color: '#f87171' }} />
            ) : null}
          </div>
        </div>
      </header>

      <nav className="main-nav">
        <button
          className={`nav-tab ${activePanel === "screening" ? "active" : ""}`}
          onClick={() => setActivePanel("screening")}
        >
          <Shield size={16} />
          Screening
        </button>
        <button
          className={`nav-tab ${activePanel === "investigation" ? "active" : ""}`}
          onClick={() => setActivePanel("investigation")}
        >
          <AlertTriangle size={16} />
          Investigation
        </button>
        <button
          className={`nav-tab ${activePanel === "watchlist" ? "active" : ""}`}
          onClick={() => setActivePanel("watchlist")}
        >
          <Database size={16} />
          Watchlist
        </button>
      </nav>

      {activePanel === "screening" && <ScreeningPanel chains={chains} />}
      {activePanel === "investigation" && <InvestigationPanel chains={chains} />}
      {activePanel === "watchlist" && <WatchlistPanel />}

      <footer className="app-footer">
        <p>Cregis AML Tracing &mdash; Risk Operations Workbench</p>
        {demoMode === true && (
          <p className="footer-note">Demo data &mdash; not real intelligence</p>
        )}
      </footer>
    </main>
  );
}

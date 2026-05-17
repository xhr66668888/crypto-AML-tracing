import { useState, useEffect } from "react";
import { Shield, Database, AlertTriangle } from "lucide-react";
import { ScreeningPanel } from "./components/ScreeningPanel";
import { InvestigationPanel } from "./components/InvestigationPanel";
import { WatchlistPanel } from "./components/WatchlistPanel";

type PanelView = "screening" | "investigation" | "watchlist";

export default function App() {
  const [activePanel, setActivePanel] = useState<PanelView>("screening");
  const [demoMode, setDemoMode] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE}/health`)
      .then(r => r.json())
      .then(d => setDemoMode(Boolean(d.demo_mode)))
      .catch(() => setDemoMode(null));
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
            ETH / USDT / USDC V1
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

      {activePanel === "screening" && <ScreeningPanel />}
      {activePanel === "investigation" && <InvestigationPanel />}
      {activePanel === "watchlist" && <WatchlistPanel />}

      <footer className="app-footer">
        <p>Cregis ETH AML Tracing &mdash; Risk Operations Workbench V1</p>
        {demoMode === true && <p className="footer-note">Demo data &mdash; not real intelligence</p>}
      </footer>
    </main>
  );
}

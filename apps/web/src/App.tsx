import { useState, useEffect } from "react";
import { Database, GitBranch, ShieldCheck } from "lucide-react";
import { request } from "./api";
import { InvestigationPanel } from "./components/InvestigationPanel";
import { ScreeningPanel } from "./components/ScreeningPanel";
import { WatchlistPanel } from "./components/WatchlistPanel";

type PanelView = "screening" | "watchlist" | "analysis";
type HealthResponse = { demo_mode?: boolean };

export default function App() {
  const [activePanel, setActivePanel] = useState<PanelView>("screening");
  const [demoMode, setDemoMode] = useState<boolean | null>(null);

  useEffect(() => {
    request<HealthResponse>("/health")
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
            <h1>Transfer Risk Decision Console</h1>
          </div>
        </div>
        <div className="topbar-right">
          <div className={`status-pill ${demoMode === true ? "demo" : "live"}`}>
            <ShieldCheck size={16} />
            {demoMode === true ? "Demo data" : demoMode === false ? "Live providers" : "Provider status"}
          </div>
        </div>
      </header>

      <nav className="main-nav">
        <button
          className={`nav-tab ${activePanel === "screening" ? "active" : ""}`}
          onClick={() => setActivePanel("screening")}
        >
          <ShieldCheck size={16} />
          Pre-Transaction Screening
        </button>
        <button
          className={`nav-tab ${activePanel === "watchlist" ? "active" : ""}`}
          onClick={() => setActivePanel("watchlist")}
        >
          <Database size={16} />
          Watchlist
        </button>
        <button
          className={`nav-tab ${activePanel === "analysis" ? "active" : ""}`}
          onClick={() => setActivePanel("analysis")}
        >
          <GitBranch size={16} />
          Address Analysis
        </button>
      </nav>

      {activePanel === "screening" && <ScreeningPanel demoMode={demoMode} />}
      {activePanel === "analysis" && <InvestigationPanel />}
      {activePanel === "watchlist" && <WatchlistPanel />}

      <footer className="app-footer">
        <p>Cregis ETH AML Tracing - Transfer Risk Decision V1</p>
        {demoMode === true && <p className="footer-note">Demo data - not real intelligence</p>}
      </footer>
    </main>
  );
}

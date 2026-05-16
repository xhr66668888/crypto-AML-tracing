import { useState } from "react";
import { Shield, Database, AlertTriangle, Wifi, WifiOff } from "lucide-react";
import { ScreeningPanel } from "./components/ScreeningPanel";
import { InvestigationPanel } from "./components/InvestigationPanel";
import { WatchlistPanel } from "./components/WatchlistPanel";

type PanelView = "screening" | "investigation" | "watchlist";

export default function App() {
  const [activePanel, setActivePanel] = useState<PanelView>("screening");
  const [connectionStatus, setConnectionStatus] = useState<"unknown" | "connected" | "error">("unknown");

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
          <ConnectionIndicator status={connectionStatus} />
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
        <p className="footer-note">Demo data &mdash; not real intelligence</p>
      </footer>
    </main>
  );
}

function ConnectionIndicator({ status }: { status: "unknown" | "connected" | "error" }) {
  if (status === "unknown") return null;

  return (
    <div className={`connection-indicator ${status}`}>
      {status === "connected" ? <Wifi size={14} /> : <WifiOff size={14} />}
      <span>{status === "connected" ? "Connected" : "Disconnected"}</span>
    </div>
  );
}

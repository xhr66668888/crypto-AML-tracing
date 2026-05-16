import { ReactNode } from "react";
import { Shield, BrainCircuit, Target } from "lucide-react";
import type { RiskResponse } from "../types";
import { compactAddress } from "../api";

export function RiskSummary({ risk }: { risk: RiskResponse | null }) {
  if (!risk) {
    return (
      <section className="panel score-panel">
        <div className="panel-title">
          <Target size={18} />
          Risk Summary
        </div>
        <div className="empty-state">
          <div className="empty-icon">?</div>
          <p>Run an investigation to see risk analysis</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel score-panel">
      <div className="panel-title">
        <Target size={18} />
        Risk Summary
      </div>
      <div className={`score-dial ${risk.final_risk_level}`}>
        <span>{Math.round(risk.final_risk_score)}</span>
        <small>{risk.final_risk_level}</small>
      </div>
      <div className={`risk-disposition ${risk.disposition_hint}`}>
        {risk.disposition_hint.replaceAll("_", " ")}
      </div>
      <div className="metric-row">
        <Metric label="Rule" value={risk.rule_score} icon={<Shield size={16} />} />
        <Metric label="Raindrop" value={risk.raindrop_score} icon={<BrainCircuit size={16} />} />
      </div>
      {risk.recommended_actions.length > 0 && (
        <div className="action-list">
          <strong>Recommended Actions</strong>
          {risk.recommended_actions.slice(0, 4).map((action) => (
            <p key={action}>{action}</p>
          ))}
        </div>
      )}
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

function compactAddr(addr: string) {
  return compactAddress(addr);
}

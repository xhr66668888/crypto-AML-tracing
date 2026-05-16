import { AlertTriangle } from "lucide-react";
import type { Finding } from "../types";
import { compactAddress } from "../api";

export function EvidenceList({ findings }: { findings: Finding[] }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <AlertTriangle size={18} />
        Evidence ({findings.length})
      </div>
      <div className="evidence-list">
        {findings.length === 0 && (
          <div className="empty-state">
            <p>No evidence loaded. Run an investigation to collect findings.</p>
          </div>
        )}
        {findings.map((finding) => (
          <article key={`${finding.subject}-${finding.evidence}`} className={`finding ${finding.severity}`}>
            <div>
              <strong>{finding.severity.toUpperCase()}</strong>
              <span>{finding.category}</span>
            </div>
            <p>{finding.evidence}</p>
            <code title={finding.subject}>{compactAddress(finding.subject)}</code>
          </article>
        ))}
      </div>
    </section>
  );
}

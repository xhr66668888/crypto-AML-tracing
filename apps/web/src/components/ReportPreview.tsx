import { useState } from "react";
import { FileText, Loader2 } from "lucide-react";
import type { ReportResponse } from "../types";
import { request } from "../api";

export function ReportPreview({ investigationId }: { investigationId: string | null }) {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function generateReport() {
    if (!investigationId) return;
    setLoading(true);
    setError("");
    try {
      const nextReport = await request<ReportResponse>(
        `/api/v1/investigations/${investigationId}/reports`,
        {
          method: "POST",
          body: JSON.stringify({ language: "en", include_raw_context: true })
        }
      );
      setReport(nextReport);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel report-panel">
      <div className="panel-title">
        <FileText size={18} />
        Report
      </div>
      <button
        className="secondary-button"
        onClick={generateReport}
        disabled={!investigationId || loading}
      >
        {loading ? <Loader2 className="spin" size={16} /> : <FileText size={16} />}
        Generate English Report
      </button>
      {error && (
        <div className="inline-error">
          <span>{error}</span>
        </div>
      )}
      {!report && !loading && !error && (
        <p className="empty">Generate a report to preview the investigation summary.</p>
      )}
      {report && (
        <div className="report-content">
          {report.used_external_llm && (
            <span className="report-badge external">AI-generated ({report.model})</span>
          )}
          {!report.used_external_llm && (
            <span className="report-badge local">Local template</span>
          )}
          <pre className="report-preview">{report.report_markdown}</pre>
        </div>
      )}
    </section>
  );
}

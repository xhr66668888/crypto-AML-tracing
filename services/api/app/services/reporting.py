"""Evidence-faithful English AML investigation report generator.

Two generation paths:
- **DeepSeek path**: when API key is set and not in demo mode, sends context
  to DeepSeek via ``DeepSeekClient.generate_report``.
- **Local fallback**: deterministic template-based report that cites every
  finding, source hit, and pattern signal from the risk response.

Hard invariants:
- Every risk conclusion references a specific source hit, pattern signal, or evidence row.
- No invented facts or hallucinated findings.
- Demo data is labelled as demonstration data in the report header.
- If no evidence exists the report explicitly states "No evidence found".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.connectors.deepseek import DeepSeekClient
from app.domain.models import (
    InvestigationRecord,
    ReportResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_HEADER = (
    "> **DEMONSTRATION DATA** — This report was generated from simulated data "
    "for testing and evaluation purposes. No real-world intelligence should be "
    "inferred from its contents.\n\n"
)


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


@dataclass
class ReportGenerator:
    """Orchestrates DeepSeek and local-fallback report generation."""

    deepseek: DeepSeekClient
    demo_mode: bool = False

    async def generate(
        self,
        record: InvestigationRecord,
        include_raw_context: bool = True,
    ) -> ReportResponse:
        """Generate an investigation report for the given record."""
        if not record.risk or not record.graph:
            return ReportResponse(
                investigation_id=record.status.id,
                model="local-template",
                used_external_llm=False,
                report_markdown="# Investigation Report\n\nInvestigation is not complete.",
            )

        # Demo mode always uses local template
        if self.demo_mode:
            return self._local_report(record)

        # Attempt DeepSeek path (non-demo + has API key)
        if self.deepseek.api_key:
            try:
                context = self._build_context(record, include_raw_context)
                content = await self.deepseek.generate_report(context)
                if not content or not content.strip():
                    return self._local_report(record)
                return ReportResponse(
                    investigation_id=record.status.id,
                    model=self.deepseek.model,
                    used_external_llm=True,
                    report_markdown=content,
                    generated_at=datetime.now(UTC),
                )
            except Exception as exc:
                logger.warning("DeepSeek failed, falling back to local template: %s", exc)

        # Local fallback
        return self._local_report(record)

    # ------------------------------------------------------------------
    # Local fallback path
    # ------------------------------------------------------------------

    def _local_report(self, record: InvestigationRecord) -> ReportResponse:
        risk = record.risk
        graph = record.graph
        assert risk is not None
        assert graph is not None

        header = DEMO_HEADER if self.demo_mode else ""

        # Source hits
        source_hit_lines = []
        for hit in risk.source_hits:
            direct_tag = " **[DIRECT HIT]**" if hit.direct_hit else ""
            source_hit_lines.append(
                f"- **[{hit.severity.value.upper()}]** [{hit.source}] {hit.label}: {hit.evidence}{direct_tag}"
            )
        if not source_hit_lines:
            source_hit_lines.append("- No source hits were found for this investigation.")

        # Pattern signals
        pattern_lines = []
        for signal in risk.pattern_signals:
            pattern_lines.append(
                f"- **[{signal.severity.value.upper()}]** {signal.name} (confidence {signal.confidence:.0%}): {signal.evidence}"
            )
        if not pattern_lines:
            pattern_lines.append("- No material pattern signals were detected in the observed graph.")

        # Key findings
        finding_lines = []
        for finding in risk.findings[:8]:
            finding_lines.append(
                f"- **[{finding.severity.value.upper()}]** {finding.subject}: {finding.evidence}"
            )
        if not finding_lines:
            finding_lines.append("- No high-confidence risk indicators were identified.")

        # Direct hit summary
        direct_hits = [h for h in risk.source_hits if h.direct_hit]
        direct_hit_summary = ""
        if direct_hits:
            direct_hit_summary = "\n".join(
                f"- **Direct hit**: {hit.evidence}" for hit in direct_hits
            )

        # Recommendations
        action_lines = [f"- {action}" for action in risk.recommended_actions]
        if not action_lines:
            action_lines.append("- No additional actions recommended at this time.")

        # Graph summary
        node_count = risk.feature_summary.get("node_count", len(graph.nodes))
        edge_count = risk.feature_summary.get("edge_count", len(graph.edges))
        max_hop = risk.feature_summary.get("max_hop", 0)

        report = (
            f"{header}"
            "# Investigation Report\n\n"
            f"**Investigation ID**: `{record.status.id}`\n"
            f"**Target**: `{record.status.target}`\n\n"
            "## Executive Summary\n\n"
            f"Target `{record.status.target}` was traced to depth {record.status.depth}. "
            f"The final risk level is **{risk.final_risk_level.value.upper()}** with a composite score of "
            f"**{risk.final_risk_score:.1f}/100**. "
            f"The recommended disposition is **{risk.disposition_hint.value}**.\n\n"
            f"{direct_hit_summary}\n\n"
            "## Risk Assessment\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Rule Score | {risk.rule_score:.1f}/100 |\n"
            f"| Raindrop Score | {risk.raindrop_score:.1f}/100 |\n"
            f"| Final Score | {risk.final_risk_score:.1f}/100 |\n"
            f"| Disposition | {risk.disposition_hint.value} |\n\n"
            "## Source Hits\n\n"
            + "\n".join(source_hit_lines) + "\n\n"
            "## Key Evidence\n\n"
            + "\n".join(finding_lines) + "\n\n"
            "## Pattern Analysis\n\n"
            + "\n".join(pattern_lines) + "\n\n"
            "## Transaction Graph Summary\n\n"
            f"- Nodes: {node_count}\n"
            f"- Edges: {edge_count}\n"
            f"- Max hop depth: {max_hop}\n\n"
            "## Recommendations\n\n"
            + "\n".join(action_lines) + "\n\n"
            "## Data Sources\n\n"
            "- Etherscan transaction data\n"
            "- GoPlus address risk intelligence\n"
            "- Local watchlist\n"
            "- Pattern analysis engine\n"
            "- Raindrop AML scoring\n\n"
            "## Analyst Notes\n\n"
            "Treat ML-derived signals as prioritization aids only. Compliance disposition should rely on "
            "the evidence table, source labels, and analyst review.\n"
        )

        return ReportResponse(
            investigation_id=record.status.id,
            model="local-template",
            used_external_llm=False,
            report_markdown=report,
            generated_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Context builder for DeepSeek
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(record: InvestigationRecord, include_raw_context: bool) -> dict:
        risk = record.risk.model_dump() if record.risk else None
        graph = record.graph.model_dump() if record.graph and include_raw_context else None
        return {
            "investigation_id": record.status.id,
            "target": record.status.target,
            "investigation": record.status.model_dump(mode="json"),
            "risk": risk,
            "graph": graph,
        }



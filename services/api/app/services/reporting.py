from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.domain.models import InvestigationRecord, ReportResponse


@dataclass
class DeepSeekReporter:
    api_key: str
    base_url: str
    model: str

    async def generate(self, record: InvestigationRecord, language: str = "en", include_raw_context: bool = True) -> ReportResponse:
        if not self.api_key:
            return ReportResponse(
                investigation_id=record.status.id,
                model="local-template",
                used_external_llm=False,
                report_markdown=self._local_report(record),
            )

        context = self._context(record, include_raw_context=include_raw_context)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an AML investigation report assistant. Produce an English compliance report. "
                        "Do not invent facts. Separate rule evidence from ML-derived risk signals."
                    ),
                },
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"].get("content") or ""
        return ReportResponse(
            investigation_id=record.status.id,
            model=self.model,
            used_external_llm=True,
            report_markdown=content,
        )

    def _local_report(self, record: InvestigationRecord) -> str:
        risk = record.risk
        graph = record.graph
        if not risk or not graph:
            return "# Investigation Report\n\nInvestigation is not complete."
        findings = "\n".join(
            f"- {finding.severity.value.upper()}: {finding.subject} - {finding.evidence}"
            for finding in risk.findings[:8]
        ) or "- No high-confidence external risk labels were found."
        patterns = "\n".join(
            f"- {signal.severity.value.upper()}: {signal.name} - {signal.evidence}"
            for signal in risk.pattern_signals[:6]
        ) or "- No material pattern signals were detected in the observed graph."
        actions = "\n".join(f"- {action}" for action in risk.recommended_actions) or "- No additional actions."
        return (
            "# AML Investigation Report\n\n"
            f"## Executive Summary\n"
            f"Target `{record.status.target}` was traced to depth {record.status.depth}. "
            f"The final risk level is **{risk.final_risk_level.value.upper()}** with score {risk.final_risk_score:.1f}. "
            f"Disposition hint: **{risk.disposition_hint.value}**.\n\n"
            "## Scores\n"
            f"- Rule score: {risk.rule_score:.1f}\n"
            f"- Raindrop score: {risk.raindrop_score:.1f}\n"
            f"- Final score: {risk.final_risk_score:.1f}\n\n"
            "## Key Evidence\n"
            f"{findings}\n\n"
            "## Pattern Signals\n"
            f"{patterns}\n\n"
            "## Recommended Actions\n"
            f"{actions}\n\n"
            "## Analyst Notes\n"
            "Treat ML-derived signals as prioritization aids. Compliance disposition should rely on the evidence table, "
            "source labels, and analyst review."
        )

    @staticmethod
    def _context(record: InvestigationRecord, include_raw_context: bool) -> dict:
        risk = record.risk.model_dump() if record.risk else None
        graph = record.graph.model_dump() if record.graph and include_raw_context else None
        return {
            "investigation": record.status.model_dump(mode="json"),
            "risk": risk,
            "graph": graph,
        }

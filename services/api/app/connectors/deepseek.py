"""DeepSeek chat completions client with retries, structured errors, and demo fixtures."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.connectors.base import ConnectorError, new_request_id

PROVIDER = "deepseek"


@dataclass
class DeepSeekClient:
    """DeepSeek LLM connector for report generation.

    In demo mode, returns a deterministic formatted English report without
    calling the external API.  This ensures investigations are reproducible
    and no API key is required for local development.
    """

    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    demo_mode: bool = True
    timeout_seconds: float = 30.0
    max_retries: int = 2

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_report(self, context: dict[str, Any]) -> str:
        """Generate an English AML investigation report from *context*.

        Parameters
        ----------
        context : dict
            Must contain at least ``investigation_id`` (str) and ``target`` (str).
            Optional keys: ``risk``, ``graph``, ``findings``, ``pattern_signals``.

        Returns
        -------
        str
            Markdown-formatted report.
        """
        investigation_id = context.get("investigation_id", "unknown")
        target = context.get("target", "unknown")

        if self.demo_mode or not self.api_key:
            return self._demo_report(investigation_id, target, context)

        return await self.chat(context)

    async def chat(self, context: dict[str, Any]) -> str:
        """Send a chat completion request to DeepSeek and return the response content."""
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
            "stream": False,
            "max_tokens": 1200,
        }

        data = await self._post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            payload=payload,
        )
        content = data["choices"][0]["message"].get("content") or ""
        return content

    # ------------------------------------------------------------------
    # HTTP with retries
    # ------------------------------------------------------------------

    async def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with bounded retry on 429/5xx/timeouts."""
        rid = new_request_id()
        last_exc: ConnectorError | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )

                if response.status_code == 429:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=429,
                        message="Rate limited by DeepSeek",
                        request_id=rid,
                        retryable=True,
                    )
                if response.status_code >= 500:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"DeepSeek server error: {response.text[:200]}",
                        request_id=rid,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=response.status_code,
                        message=f"DeepSeek client error: {response.text[:200]}",
                        request_id=rid,
                        retryable=False,
                    )

                data = response.json()
                if "choices" not in data:
                    raise ConnectorError(
                        provider=PROVIDER,
                        status_code=200,
                        message=f"DeepSeek unexpected response: missing 'choices' key",
                        request_id=rid,
                        retryable=False,
                        raw=data,
                    )
                return data

            except httpx.TimeoutException:
                last_exc = ConnectorError(
                    provider=PROVIDER,
                    status_code=None,
                    message=f"Timeout after {self.timeout_seconds}s (attempt {attempt}/{self.max_retries})",
                    request_id=rid,
                    retryable=True,
                )
            except httpx.HTTPError as exc:
                last_exc = ConnectorError(
                    provider=PROVIDER,
                    status_code=None,
                    message=f"HTTP error: {exc} (attempt {attempt}/{self.max_retries})",
                    request_id=rid,
                    retryable=True,
                )
            except ConnectorError:
                raise  # already structured

            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Demo fixtures
    # ------------------------------------------------------------------

    @staticmethod
    def _demo_report(investigation_id: str, target: str, context: dict[str, Any]) -> str:
        """Return a deterministic, realistic AML report for demo mode."""
        risk = context.get("risk") or {}
        risk_level = risk.get("final_risk_level", "low")
        risk_score = risk.get("final_risk_score", 0.0)
        findings = risk.get("findings", [])
        pattern_signals = risk.get("pattern_signals", [])
        recommended_actions = risk.get("recommended_actions", [])
        disposition = risk.get("disposition_hint", "allow")

        # Build evidence bullets
        evidence_lines = []
        for f in findings[:5]:
            severity = f.get("severity", "low").upper()
            subject = f.get("subject", "unknown")
            ev = f.get("evidence", "No evidence provided.")
            evidence_lines.append(f"- **{severity}**: {subject} — {ev}")
        if not evidence_lines:
            evidence_lines.append("- No high-confidence external risk labels were found.")

        # Build pattern bullets
        pattern_lines = []
        for p in pattern_signals[:5]:
            severity = p.get("severity", "low").upper()
            name = p.get("name", "unknown")
            ev = p.get("evidence", "No evidence provided.")
            pattern_lines.append(f"- **{severity}**: {name} — {ev}")
        if not pattern_lines:
            pattern_lines.append("- No material pattern signals were detected in the observed graph.")

        # Build action bullets
        action_lines = [f"- {a}" for a in recommended_actions[:5]]
        if not action_lines:
            action_lines.append("- No additional actions recommended at this time.")

        return (
            "# AML Investigation Report\n\n"
            f"**Investigation ID**: `{investigation_id}`\n"
            f"**Target**: `{target}`\n"
            f"**Generated by**: DeepSeek (demo mode)\n\n"
            "## Executive Summary\n\n"
            f"Target `{target}` was traced and analyzed. "
            f"The final risk level is **{risk_level.upper()}** with a composite score of "
            f"**{risk_score:.1f}**. "
            f"The recommended disposition is **{disposition}**.\n\n"
            "## Risk Scores\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Rule Score | {risk.get('rule_score', 0.0):.1f} |\n"
            f"| Raindrop Score | {risk.get('raindrop_score', 0.0):.1f} |\n"
            f"| Final Score | {risk_score:.1f} |\n\n"
            "## Key Evidence\n\n"
            + "\n".join(evidence_lines) + "\n\n"
            "## Pattern Signals\n\n"
            + "\n".join(pattern_lines) + "\n\n"
            "## Recommended Actions\n\n"
            + "\n".join(action_lines) + "\n\n"
            "## Analyst Notes\n\n"
            "Treat ML-derived signals as prioritization aids. Compliance disposition should rely on "
            "the evidence table, source labels, and analyst review. This report was generated in "
            "**demo mode** and does not represent real intelligence.\n"
        )

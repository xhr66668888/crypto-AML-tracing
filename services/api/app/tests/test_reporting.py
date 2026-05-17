"""Tests for the evidence-faithful report generator.

Covers:
- Report generation with no evidence (empty findings)
- Report generation with evidence (source hits + patterns)
- Report generation with a direct hit → hold_for_manual_review
- DeepSeek path (mocked)
- Local fallback path (when DeepSeek unavailable or errors)
- Demo mode header injection
- Evidence citation accuracy
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.connectors.base import ConnectorError
from app.connectors.deepseek import DeepSeekClient
from app.domain.models import (
    GraphEdge,
    GraphNode,
    InvestigationGraph,
    InvestigationMode,
    InvestigationRecord,
    InvestigationStatus,
    PatternSignal,
    RiskDisposition,
    RiskFinding,
    RiskLevel,
    RiskResponse,
    RiskSourceHit,
    TargetType,
)
from app.services.reporting import ReportGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_status(investigation_id: str = "inv-test-001", target: str = "0x" + "a" * 40) -> InvestigationStatus:
    return InvestigationStatus(
        id=investigation_id,
        target=target,
        target_type=TargetType.address,
        chain_id="1",
        depth=3,
        mode=InvestigationMode.stable,
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )


def _make_graph(node_count: int = 5, edge_count: int = 4) -> InvestigationGraph:
    nodes = [
        GraphNode(
            id=f"node-{i}",
            address=f"0x{i:040x}",
            label=f"addr-{i}",
            hop=i % 3,
        )
        for i in range(node_count)
    ]
    edges = [
        GraphEdge(
            id=f"edge-{i}",
            source=f"0x{i:040x}",
            target=f"0x{(i + 1) % node_count:040x}",
            tx_hash=f"0x{i:064x}",
            timestamp=1700000000 + i * 3600,
            value_eth=1.5 + i,
            hop=i % 3,
            direction="out",
        )
        for i in range(edge_count)
    ]
    return InvestigationGraph(investigation_id="inv-test-001", nodes=nodes, edges=edges)


def _make_risk(
    *,
    rule_score: float = 50.0,
    raindrop_score: float = 30.0,
    final_score: float = 50.0,
    level: RiskLevel = RiskLevel.medium,
    disposition: RiskDisposition = RiskDisposition.review,
    source_hits: list[RiskSourceHit] | None = None,
    pattern_signals: list[PatternSignal] | None = None,
    findings: list[RiskFinding] | None = None,
    recommended_actions: list[str] | None = None,
) -> RiskResponse:
    return RiskResponse(
        investigation_id="inv-test-001",
        rule_score=rule_score,
        raindrop_score=raindrop_score,
        final_risk_score=final_score,
        final_risk_level=level,
        findings=findings or [],
        top_risk_paths=[["0x" + "a" * 40, "0x" + "b" * 40]],
        feature_summary={
            "node_count": 5,
            "edge_count": 4,
            "max_hop": 2,
            "graph_density": 0.2,
            "singleton_ratio": 0.4,
        },
        pattern_signals=pattern_signals or [],
        source_hits=source_hits or [],
        network_metrics=[],
        disposition_hint=disposition,
        recommended_actions=recommended_actions or ["Queue for manual risk review with the attached evidence."],
    )


def _make_record(
    *,
    risk: RiskResponse | None = None,
    graph: InvestigationGraph | None = None,
    use_default_graph: bool = True,
) -> InvestigationRecord:
    actual_graph = _make_graph() if (graph is None and use_default_graph) else graph
    return InvestigationRecord(
        status=_make_status(),
        graph=actual_graph,
        risk=risk,
    )


def _sample_source_hit(
    *,
    source: str = "local_watchlist",
    category: str = "sanctions",
    severity: RiskLevel = RiskLevel.critical,
    address: str = "0x" + "b" * 40,
    label: str = "OFAC SDN",
    evidence: str = "Address appears on OFAC SDN list.",
    direct_hit: bool = True,
) -> RiskSourceHit:
    return RiskSourceHit(
        source=source,
        category=category,
        severity=severity,
        address=address,
        label=label,
        evidence=evidence,
        direct_hit=direct_hit,
    )


def _sample_pattern(
    *,
    name: str = "aggregation",
    severity: RiskLevel = RiskLevel.high,
    score: float = 72.0,
    subject: str = "0x" + "c" * 40,
    evidence: str = "5 source addresses aggregate 12.5 ETH into one address.",
    confidence: float = 0.76,
) -> PatternSignal:
    return PatternSignal(
        name=name,
        severity=severity,
        score=score,
        subject=subject,
        evidence=evidence,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Local fallback tests
# ---------------------------------------------------------------------------


class TestLocalReportNoEvidence:
    """Report with no source hits and no patterns must explicitly say so."""

    @pytest.mark.asyncio
    async def test_report_states_no_evidence(self):
        risk = _make_risk(
            source_hits=[],
            pattern_signals=[],
            findings=[],
            recommended_actions=[],
            level=RiskLevel.low,
            disposition=RiskDisposition.allow,
            final_score=10.0,
            rule_score=10.0,
            raindrop_score=5.0,
        )
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        response = await gen.generate(record)

        md = response.report_markdown
        assert "No source hits were found" in md
        assert "No material pattern signals were detected" in md
        assert "No high-confidence risk indicators were identified" in md
        assert response.used_external_llm is False
        assert response.model == "local-template"

    @pytest.mark.asyncio
    async def test_no_evidence_report_is_complete(self):
        """Even with no evidence, all report sections must be present."""
        risk = _make_risk(
            source_hits=[], pattern_signals=[], findings=[],
            level=RiskLevel.low, disposition=RiskDisposition.allow,
            final_score=10.0, rule_score=10.0, raindrop_score=5.0,
        )
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "# Investigation Report" in md
        assert "## Executive Summary" in md
        assert "## Risk Assessment" in md
        assert "## Source Hits" in md
        assert "## Pattern Analysis" in md
        assert "## Transaction Graph Summary" in md
        assert "## Recommendations" in md
        assert "## Data Sources" in md
        assert "## Analyst Notes" in md


class TestLocalReportWithEvidence:
    """Report with source hits and patterns must cite each one."""

    @pytest.mark.asyncio
    async def test_source_hits_are_cited(self):
        hit1 = _sample_source_hit(
            source="goplus", category="mixer", severity=RiskLevel.high,
            label="mixer", evidence="GoPlus malicious behavior: mixer",
            direct_hit=False,
        )
        hit2 = _sample_source_hit(
            source="local_watchlist", category="ofac",
            label="OFAC SDN demo", evidence="Authoritative sanctions list demo hit.",
        )
        risk = _make_risk(source_hits=[hit1, hit2])
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "GoPlus malicious behavior: mixer" in md
        assert "Authoritative sanctions list demo hit." in md
        assert "**[DIRECT HIT]**" in md
        assert "local_watchlist" in md
        assert "goplus" in md

    @pytest.mark.asyncio
    async def test_pattern_signals_are_cited(self):
        p1 = _sample_pattern(name="aggregation", evidence="5 source addresses aggregate 12.5 ETH into one address.")
        p2 = _sample_pattern(name="dusting", severity=RiskLevel.medium, score=50.0,
                             evidence="8 dust-sized transfers touch 6 recipient addresses.")
        risk = _make_risk(pattern_signals=[p1, p2])
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "5 source addresses aggregate 12.5 ETH" in md
        assert "8 dust-sized transfers touch 6 recipient addresses" in md
        assert "aggregation" in md
        assert "dusting" in md


class TestLocalReportDirectHit:
    """A direct hit must produce hold_for_manual_review in the report."""

    @pytest.mark.asyncio
    async def test_direct_hit_forces_manual_review(self):
        hit = _sample_source_hit(
            category="ofac", severity=RiskLevel.critical,
            evidence="Address is on the OFAC SDN sanctions list.",
        )
        risk = _make_risk(
            source_hits=[hit],
            level=RiskLevel.critical,
            disposition=RiskDisposition.hold_for_manual_review,
            final_score=95.0,
            rule_score=95.0,
            raindrop_score=70.0,
            recommended_actions=[
                "Hold funds for manual compliance review and verify the authoritative source evidence.",
                "Escalate to the sanctions/PEP review workflow before customer release.",
            ],
        )
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "hold_for_manual_review" in md
        assert "CRITICAL" in md or "critical" in md
        assert "OFAC" in md or "ofac" in md
        assert "Address is on the OFAC SDN sanctions list." in md
        assert "Hold funds for manual compliance review" in md

    @pytest.mark.asyncio
    async def test_direct_hit_key_finding_mentioned(self):
        hit = _sample_source_hit(
            category="sanctions", severity=RiskLevel.critical,
            evidence="Sanctions list match confirmed.",
        )
        risk = _make_risk(
            source_hits=[hit],
            level=RiskLevel.critical,
            disposition=RiskDisposition.hold_for_manual_review,
            final_score=95.0,
        )
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        # Direct hit must appear in executive summary key findings
        assert "Direct hit" in md
        assert "Sanctions list match confirmed." in md


# ---------------------------------------------------------------------------
# Demo mode tests
# ---------------------------------------------------------------------------


class TestDemoMode:
    """Demo mode must label the report as demonstration data."""

    @pytest.mark.asyncio
    async def test_demo_header_present(self):
        risk = _make_risk()
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=True)
        md = (await gen.generate(record)).report_markdown

        assert "DEMONSTRATION DATA" in md
        assert "simulated data" in md.lower()

    @pytest.mark.asyncio
    async def test_demo_data_sources_note(self):
        risk = _make_risk()
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=True)
        md = (await gen.generate(record)).report_markdown

        assert "demonstration mode" in md.lower() or "demonstration data" in md.lower()

    @pytest.mark.asyncio
    async def test_non_demo_mode_has_no_demo_header(self):
        risk = _make_risk()
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "DEMONSTRATION DATA" not in md


# ---------------------------------------------------------------------------
# DeepSeek path tests (mocked)
# ---------------------------------------------------------------------------


class TestDeepSeekPath:
    """Test the DeepSeek generation path with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_deepseek_success(self):
        """When DeepSeek returns valid content, it is used as the report."""
        mock_response = (
            "# Investigation Report\n\n"
            "## Executive Summary\n"
            "Target `0xaaaa...` is high risk.\n\n"
            "## Source Hits\n"
            "1. GoPlus — mixer — Evidence: GoPlus malicious behavior: mixer\n"
        )
        risk = _make_risk()
        record = _make_record(risk=risk)

        # DeepSeekClient in non-demo mode with API key
        client = DeepSeekClient(api_key="sk-test-key", demo_mode=False)
        gen = ReportGenerator(deepseek=client, demo_mode=False)

        with patch.object(client, "generate_report", new_callable=AsyncMock, return_value=mock_response):
            response = await gen.generate(record)

        assert response.used_external_llm is True
        assert response.model == "deepseek-v4-pro"
        assert "GoPlus malicious behavior: mixer" in response.report_markdown

    @pytest.mark.asyncio
    async def test_deepseek_fallback_on_connector_error(self):
        """When DeepSeek raises ConnectorError, the local template is used."""
        risk = _make_risk()
        record = _make_record(risk=risk)

        client = DeepSeekClient(api_key="sk-test-key", demo_mode=False)
        gen = ReportGenerator(deepseek=client, demo_mode=False)

        with patch.object(
            client, "generate_report", new_callable=AsyncMock,
            side_effect=ConnectorError(provider="deepseek", message="timeout"),
        ):
            response = await gen.generate(record)

        assert response.used_external_llm is False
        assert response.model == "local-template"
        assert "# Investigation Report" in response.report_markdown

    @pytest.mark.asyncio
    async def test_deepseek_no_api_key_uses_local(self):
        """When no API key is set, local template is used without attempting HTTP."""
        risk = _make_risk()
        record = _make_record(risk=risk)

        client = DeepSeekClient(api_key="", demo_mode=False)
        gen = ReportGenerator(deepseek=client, demo_mode=False)

        with patch.object(client, "generate_report", new_callable=AsyncMock) as mock_report:
            response = await gen.generate(record)

        assert response.used_external_llm is False
        mock_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_deepseek_demo_mode_uses_local(self):
        """In demo mode, local template is used even with API key."""
        risk = _make_risk()
        record = _make_record(risk=risk)

        client = DeepSeekClient(api_key="sk-test-key", demo_mode=False)
        gen = ReportGenerator(deepseek=client, demo_mode=True)

        with patch.object(client, "generate_report", new_callable=AsyncMock) as mock_report:
            response = await gen.generate(record)

        assert response.used_external_llm is False
        mock_report.assert_not_called()
        assert "DEMONSTRATION DATA" in response.report_markdown

    @pytest.mark.asyncio
    async def test_deepseek_empty_response_falls_back(self):
        """When DeepSeek returns empty content, fall back to local template."""
        risk = _make_risk()
        record = _make_record(risk=risk)

        client = DeepSeekClient(api_key="sk-test-key", demo_mode=False)
        gen = ReportGenerator(deepseek=client, demo_mode=False)

        with patch.object(client, "generate_report", new_callable=AsyncMock, return_value=""):
            response = await gen.generate(record)

        assert response.used_external_llm is False
        assert response.model == "local-template"


# ---------------------------------------------------------------------------
# Incomplete investigation tests
# ---------------------------------------------------------------------------


class TestIncompleteInvestigation:
    """Report for an incomplete investigation must say so."""

    @pytest.mark.asyncio
    async def test_no_risk_returns_incomplete(self):
        record = _make_record(risk=None)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        response = await gen.generate(record)

        assert "not complete" in response.report_markdown.lower()
        assert response.used_external_llm is False

    @pytest.mark.asyncio
    async def test_no_graph_returns_incomplete(self):
        record = _make_record(risk=_make_risk(), use_default_graph=False)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        response = await gen.generate(record)

        assert "not complete" in response.report_markdown.lower()
        assert response.used_external_llm is False


# ---------------------------------------------------------------------------
# Evidence citation accuracy
# ---------------------------------------------------------------------------


class TestEvidenceCitationAccuracy:
    """Every evidence string from the risk response must appear in the report."""

    def test_all_source_hit_evidence_cited(self):
        """Every source hit evidence string must appear in the generated report."""
        hits = [
            _sample_source_hit(
                source="goplus", category="mixer", severity=RiskLevel.high,
                label="mixer", evidence="GoPlus malicious behavior: mixer",
                direct_hit=False,
            ),
            _sample_source_hit(
                source="local_watchlist", category="ofac", severity=RiskLevel.critical,
                label="OFAC SDN", evidence="OFAC SDN sanctions list hit.",
            ),
            _sample_source_hit(
                source="goplus", category="phishing", severity=RiskLevel.high,
                label="phishing", evidence="GoPlus malicious behavior: phishing_activities",
                direct_hit=False,
            ),
        ]
        risk = _make_risk(source_hits=hits)
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        response = gen._local_report(record)
        md = response.report_markdown

        for hit in hits:
            assert hit.evidence in md, f"Evidence not found in report: {hit.evidence!r}"

    def test_all_pattern_evidence_cited(self):
        """Every pattern signal evidence string must appear in the generated report."""
        patterns = [
            _sample_pattern(name="aggregation", evidence="5 source addresses aggregate 12.5 ETH into one address."),
            _sample_pattern(name="dusting", evidence="8 dust-sized transfers touch 6 recipient addresses."),
            _sample_pattern(name="layering", evidence="Funds traverse 3 hops across 10 observed transfers."),
        ]
        risk = _make_risk(pattern_signals=patterns)
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        response = gen._local_report(record)
        md = response.report_markdown

        for pattern in patterns:
            assert pattern.evidence in md, f"Pattern evidence not found in report: {pattern.evidence!r}"

    @pytest.mark.asyncio
    async def test_no_invented_evidence(self):
        """Report must not contain claims not backed by provided evidence."""
        risk = _make_risk(source_hits=[], pattern_signals=[])
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        # Must not claim findings that don't exist
        assert "OFAC" not in md
        assert "sanctions" not in md.lower() or "no source hits" in md.lower()
        assert "mixer" not in md


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestReportEdgeCases:
    """Edge cases for report generation."""

    @pytest.mark.asyncio
    async def test_risk_scores_in_report_match_model(self):
        """Risk scores in the report must match the RiskResponse values."""
        risk = _make_risk(
            rule_score=77.5, raindrop_score=42.3, final_score=77.5,
            level=RiskLevel.high, disposition=RiskDisposition.review,
        )
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "77.5/100" in md
        assert "42.3/100" in md

    @pytest.mark.asyncio
    async def test_report_id_matches_investigation(self):
        risk = _make_risk()
        record = _make_record(risk=risk)
        record.status.id = "inv-custom-id"
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        response = await gen.generate(record)

        assert response.investigation_id == "inv-custom-id"

    @pytest.mark.asyncio
    async def test_graph_summary_uses_feature_summary(self):
        risk = _make_risk()
        risk.feature_summary = {
            "node_count": 42,
            "edge_count": 88,
            "max_hop": 4,
            "graph_density": 0.1234,
            "singleton_ratio": 0.5678,
        }
        record = _make_record(risk=risk)
        gen = ReportGenerator(deepseek=DeepSeekClient(api_key="", demo_mode=False), demo_mode=False)
        md = (await gen.generate(record)).report_markdown

        assert "42" in md
        assert "88" in md

    @pytest.mark.asyncio
    async def test_deepseek_context_includes_required_keys(self):
        """Context passed to DeepSeek must have investigation_id and target."""
        risk = _make_risk()
        record = _make_record(risk=risk)

        client = DeepSeekClient(api_key="sk-test-key", demo_mode=False)
        gen = ReportGenerator(deepseek=client, demo_mode=False)

        captured_context = {}

        async def capture_context(ctx):
            captured_context.update(ctx)
            return "# Report from DeepSeek"

        with patch.object(client, "generate_report", side_effect=capture_context):
            await gen.generate(record)

        assert "investigation_id" in captured_context
        assert "target" in captured_context
        assert "risk" in captured_context

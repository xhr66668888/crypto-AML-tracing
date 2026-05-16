---
name: cregis-evidence-integrity
description: Compliance-specific Karpathy adaptation for the Cregis ETH AML Tracing project. Use when editing any file that touches scoring, patterns, source hits, watchlists, the direct-hit policy, or the AI report. Enforces "every risk conclusion has source-backed evidence" and "demo data is never described as real intel".
license: MIT
applies_to:
  - services/api/app/domain/risk_intel.py
  - services/api/app/domain/scoring.py
  - services/api/app/domain/patterns.py
  - services/api/app/services/reporting.py
  - services/api/app/services/screening.py
---

# Cregis Evidence Integrity

This is a compliance-flavoured Karpathy guideline. Code under
`services/api/app/domain/` and `services/api/app/services/reporting.py` is
where wrong code becomes wrong compliance decisions. The project director
treats violations here as **blocking**, not advisory.

## 1. Every risk conclusion has an evidence row

Any `RiskFinding`, `RiskSourceHit`, `PatternSignal`, or sentence in a
generated report MUST cite one of:

- a `source_hit` from `RiskIntelAggregator` (provider name + label),
- a `pattern_signal` from `PatternAnalyzer` (detector name + evidence string),
- a `GraphEdge` or `GraphNode` from the bounded `InvestigationGraph`.

**Forbidden:** asserting "address X is high risk" without one of the above in
the same response payload or report markdown.

The reviewer should grep:

```bash
rg -n 'risk_score|risk_level|final_risk' services/api/app/domain
```

Each setter of `risk_score` must trace to a `RiskSourceHit` or `PatternSignal`
within the same scoring pass.

## 2. Demo data is never described as real intel

Anything originating from `_demo_*` helpers in
`services/api/app/connectors/` carries `source: "demo"` in normalised output.

- The Markdown report MUST include the `DEMONSTRATION DATA` header when
  `demo_mode=true`.
- The frontend MUST surface a "Demo data — not real intelligence" footer when
  the API responds with `demo_mode: true` in `/health`.

The reviewer should grep:

```bash
rg -n 'DEMONSTRATION DATA|source.*demo' services/api apps/web
```

## 3. Direct-hit overrides are non-negotiable

Categories in `DIRECT_HIT_CATEGORIES` (currently: `ofac`, `pep`, `sanctions`,
`sanctioned`, `circle_blacklist`, `tether_blacklist`, `stablecoin_blacklist`)
MUST force `RiskDisposition.hold_for_manual_review` regardless of the
behavioural score. This is enforced in `decide_disposition()` in
`services/api/app/domain/scoring.py`.

Any change that:

- removes a category from `DIRECT_HIT_CATEGORIES`,
- weakens the override (e.g. requires a score floor before triggering),
- replaces `hold_for_manual_review` with a softer disposition,

must have a `risk-logic-reviewer` verdict in the PR body **and** an
`aml-architect` approval line.

## 4. Raindrop score is advisory only

`raindrop_score` may *raise* the floor of `final_risk_score`. It MUST NOT
*lower* a rule-derived risk score or a direct-hit-derived disposition. The
current implementation in `scoring.py` enforces this via
`final_score = min(100.0, max(rule_score, raindrop_score))`. Do not change
this to `min(rule_score, raindrop_score)` or similar.

The frozen public surface is:

```python
class RaindropAmlScorer:
    def predict(self, graph: InvestigationGraph) -> RaindropResult: ...
```

Any change to this signature requires `aml-architect` approval.

## 5. No invented facts in reports

`services/api/app/services/reporting.py` MUST:

- Print "No source hits were found for this investigation." when
  `risk.source_hits` is empty.
- Print "No material pattern signals were detected in the observed graph."
  when `risk.pattern_signals` is empty.
- Print "No high-confidence risk indicators were identified." when
  `risk.findings` is empty.
- Never invent a `RiskFinding`, `RiskSourceHit`, or `PatternSignal` that is
  not in `record.risk`.

The DeepSeek path MUST fall back to the local template on any error and MUST
NOT silently retry indefinitely. The current implementation does this; do not
weaken it.

## Acceptance checks

```bash
# Direct-hit override is tested and passes
PYTHONPATH=services/api python -m pytest -q \
  services/api/app/tests/test_risk_intel.py::test_screening_direct_source_hit_forces_manual_hold

# Report invariants are tested and pass
PYTHONPATH=services/api python -m pytest -q \
  services/api/app/tests/test_reporting.py
```

Both must be green. A red test here is a **blocking** compliance regression.

# Architecture

## Product Shape

This project is a local AML risk operations tool for Cregis compliance and risk analysts. The first release supports Ethereum mainnet ETH/USDT/USDC. It prioritizes pre-release transfer screening, single-investigation workflows, explainable evidence, deterministic pattern analysis, and an experimental Raindrop-derived risk layer.

## Runtime Flow

1. Operator screens an inbound/outbound transfer through `POST /api/v1/screening/transactions`, or an analyst submits an address/transaction hash from the React workbench.
2. FastAPI validates the target and creates an investigation record.
3. `EtherscanClient` fetches or demo-generates transaction data.
4. `GraphBuilder` expands a bounded transaction graph to 3 stable hops or 5 experimental hops.
5. `RiskIntelAggregator` enriches graph nodes with GoPlus, local watchlist tags, and source-hit semantics for direct sanctions/PEP/stablecoin-blacklist style matches.
6. `PatternAnalyzer` detects deterministic AML patterns such as layering, aggregation, peel-chain behavior, threshold structuring, dusting, sparse-address large transfers, centrality hubs, and risk propagation.
7. `RiskScoringEngine` computes rule score, Raindrop score, final risk score, findings, top paths, disposition hints, and recommended actions.
8. `DeepSeekReporter` generates an English report when an API key is configured, or a local report otherwise.

## Module Boundaries

- `connectors`: third-party API clients and demo-mode fallbacks.
- `domain`: target validation, graph building, pattern analysis, risk intelligence, and scoring.
- `ml`: stable adapter surface for Raindrop AML scoring.
- `services`: screening, investigation orchestration, and report generation.
- `storage`: persistence boundary; currently in-memory, later PostgreSQL.
- `apps/web`: analyst workbench.

## Raindrop Placement

Raindrop is used in the experimental risk judgment layer. It must not override strong compliance evidence. The UI exposes `rule_score`, `raindrop_score`, and `final_risk_score` separately so analysts can distinguish source-backed findings from ML prioritization.

## Direct-Hit Policy

OFAC/sanctions, PEP, Circle/Tether/stablecoin blacklist, and local critical watchlist categories are direct-hit signals. They produce a high-risk label and `hold_for_manual_review` disposition even when the total behavioral score is below the normal high-risk threshold. Pattern-only signals produce review priority unless paired with source-backed evidence.

## Security Defaults

- Local service defaults to demo mode and browser-only usage.
- API keys are read from `.env` and never committed.
- DeepSeek receives full investigation context only when `DEEPSEEK_API_KEY` is configured and a report is requested.
- The API is intended to listen on localhost in production packaging unless Cregis explicitly enables network access.

## Subagent Ownership

Module boundaries map 1:1 to OpenCode subagents defined under [`.opencode/agents/`](../.opencode/agents). Two brain agents are pinned to **Codex GPT 5.5 with `reasoningEffort: high`** via [`opencode.json`](../opencode.json); the eight execution agents have no model override and **inherit the OpenCode default** (e.g. `mimo-v2.5-pro`).

| Module / Concern | Subagent | Model |
| --- | --- | --- |
| API contracts, schema boundary, `.env`, module boundaries, release | `aml-architect` | Codex GPT 5.5, high |
| Scoring, pattern, direct-hit, report audit (read-only) | `risk-logic-reviewer` | Codex GPT 5.5, high |
| `services/api/app/connectors/` (Etherscan, GoPlus, DeepSeek HTTP) | `connector-engineer` | OpenCode default |
| `services/api/app/domain/graph_builder.py` and `patterns.py` | `graph-pattern-engineer` | OpenCode default |
| `services/api/app/domain/risk_intel.py`, rule-score side of `scoring.py`, watchlist | `risk-intel-engineer` | OpenCode default |
| `services/api/app/ml/`, `services/ml/raindrop_aml/` | `raindrop-ml-engineer` | OpenCode default |
| `services/api/app/services/reporting.py` | `report-engineer` | OpenCode default |
| `apps/web/` | `web-workbench-engineer` | OpenCode default |
| `infra/scripts/`, `.github/workflows/`, `docker-compose.yml`, `pytest.ini`, smoke | `qa-devops-engineer` | OpenCode default |
| `docs/database/schema.sql`, `services/api/app/storage/` | `db-storage-engineer` | OpenCode default |

Coordination: every change touching API / schema / `.env` / module boundaries goes through `aml-architect` first. Every change touching scoring, patterns, direct-hit, or report content needs a `risk-logic-reviewer` verdict before merge. Execution agents stay in their owned files; cross-boundary changes are routed through `aml-architect`. The `RaindropAmlScorer.predict(graph) -> RaindropResult` interface is frozen until `aml-architect` approves a change. Detailed roles and deliverables: [`docs/team-assignments.md`](team-assignments.md).

## Code Quality (Karpathy Acceptance Gate)

Adopted 2026-05-16. Every diff must pass the project-customised Karpathy
guidelines and the project-director acceptance checks in:

- [`skills/cregis-code-quality/SKILL.md`](../skills/cregis-code-quality/SKILL.md)
  — Karpathy principles plus the hard blockers the project director enforces
  at merge.
- [`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
  — executable review skill, returns an `approved` / `approved-with-changes`
  / `blocked` verdict.
- [`skills/cregis-evidence-integrity/SKILL.md`](../skills/cregis-evidence-integrity/SKILL.md)
  — compliance-flavoured Karpathy adaptation; mandatory for any change that
  touches scoring, patterns, direct-hit, or report content.

Cursor auto-loads these via
[`.cursor/rules/cregis-code-quality.mdc`](../.cursor/rules/cregis-code-quality.mdc).
OpenCode subagents discover them through their per-agent `Required skills`
section and through the universal [`AGENTS.md`](../AGENTS.md) at the repo
root.

The open round-one findings from the first acceptance audit live in
[`docs/acceptance-review.md`](acceptance-review.md). They are mirrored in
[`docs/known-limitations.md § Code-quality limitations`](known-limitations.md#code-quality-limitations-round-one-acceptance-audit-2026-05-16)
and in
[`docs/release-checklist.md § 11`](release-checklist.md#11-karpathy-acceptance-gate-added-2026-05-16).

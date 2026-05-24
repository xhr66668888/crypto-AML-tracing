# Architecture

## Product Shape

This project is a local AML risk operations tool for Cregis compliance and risk analysts. The first release supports Ethereum mainnet ETH plus mainstream ERC-20 screening for USDT, USDC, DAI, WETH, WBTC, and custom ERC-20 contracts supplied by `token_address`. It prioritizes pre-release transfer screening, single-investigation workflows, explainable evidence, deterministic pattern analysis, and an experimental Raindrop-derived risk layer.

## Runtime Flow

1. Operator screens an inbound/outbound transfer through `POST /api/v1/screening/transactions`, or an analyst submits an address/transaction hash from the React workbench.
2. FastAPI validates the target and creates an investigation record.
3. `EtherscanClient` fetches or demo-generates native `txlist` data or ERC-20 `tokentx` data for screening.
4. `GraphBuilder` expands a bounded transaction graph to 3 stable hops or 5 experimental hops for investigations. Pre-transaction screening uses a lighter two-sided context graph: from-address and to-address are each expanded to at most 2 hops and 6 recent transactions per address.
5. `RiskIntelAggregator` enriches graph nodes with GoPlus, local watchlist tags, and source-hit semantics for direct sanctions/PEP/stablecoin-blacklist style matches.
6. `PatternAnalyzer` detects deterministic AML patterns such as layering, aggregation, peel-chain behavior, threshold structuring, dusting, sparse-address large transfers, centrality hubs, and risk propagation.
7. `RiskScoringEngine` computes rule score, Raindrop score, final risk score, findings, top paths, disposition hints, and recommended actions.
8. `DeepSeekReporter` generates an English report when an API key is configured, or a local report otherwise.

Screening context is evidence support only. It can show direct party hits,
recent high-risk exposure within one or two hops, amount-threshold signals, and
short-time repeated transfers, but it must not be described as complete fund
provenance.

## Module Boundaries

- `connectors`: third-party API clients and demo-mode fallbacks.
- `domain`: target validation, graph building, pattern analysis, risk intelligence, and scoring.
- `ml`: stable adapter surface for Raindrop AML scoring.
- `services`: screening, investigation orchestration, and report generation.
- `storage`: persistence boundary; currently in-memory, later PostgreSQL.
- `apps/web`: analyst workbench.

## Raindrop Placement

Raindrop is used in the experimental risk judgment layer. It must not override strong compliance evidence. The UI exposes `rule_score`, `raindrop_score`, and `final_risk_score` separately so analysts can distinguish source-backed findings from ML prioritization.

**Canonical interface (frozen):** `RaindropAmlScorer.predict(graph) -> RaindropResult` in `services/api/app/ml/raindrop_scorer.py`. The `RaindropResult` dataclass has fields `score`, `features`, `explanation`, and `model_version`. The duplicate `raindrop_aml.py` (which returned a `tuple[float, dict]`) was deleted during round-one Karpathy §2 cleanup.

## Direct-Hit Policy

OFAC/sanctions, PEP, Circle/Tether/stablecoin blacklist, and local critical watchlist categories are direct-hit signals. They produce a high-risk label and `hold_for_manual_review` disposition even when the total behavioral score is below the normal high-risk threshold. Pattern-only signals produce review priority unless paired with source-backed evidence.

## Security Defaults

- Local service defaults to demo mode and browser-only usage.
- API keys are read from `.env` and never committed.
- DeepSeek receives full investigation context only when `DEEPSEEK_API_KEY` is configured and a report is requested.
- The API is intended to listen on localhost in production packaging unless Cregis explicitly enables network access.

## Ownership Boundaries

Module boundaries map to repository ownership roles. These roles are used for
review routing and scope control; no separate per-agent markdown files are
required in the repository.

| Module / Concern | Owner |
| --- | --- |
| API contracts, schema boundary, `.env`, module boundaries, release | `aml-architect` |
| Scoring, pattern, direct-hit, report audit (read-only) | `risk-logic-reviewer` |
| `services/api/app/connectors/` (Etherscan, GoPlus, DeepSeek HTTP) | `connector-engineer` |
| `services/api/app/domain/graph_builder.py` and `patterns.py` | `graph-pattern-engineer` |
| `services/api/app/domain/risk_intel.py`, rule-score side of `scoring.py`, watchlist | `risk-intel-engineer` |
| `services/api/app/ml/`, `services/ml/raindrop_aml/` | `raindrop-ml-engineer` |
| `services/api/app/services/reporting.py` | `report-engineer` |
| `apps/web/` | `web-workbench-engineer` |
| `infra/scripts/`, `.github/workflows/`, `docker-compose.yml`, `pytest.ini`, smoke | `qa-devops-engineer` |
| `docs/database/schema.sql`, `services/api/app/storage/` | `db-storage-engineer` |

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

The concise live index for these skills is
[`docs/agent-skills.md`](agent-skills.md).

The open round-one findings from the first acceptance audit live in
[`docs/acceptance-review.md`](acceptance-review.md). They are mirrored in
[`docs/known-limitations.md § Code-quality limitations`](known-limitations.md#code-quality-limitations-round-one-acceptance-audit-2026-05-16)
and in
[`docs/release-checklist.md § 11`](release-checklist.md#11-karpathy-acceptance-gate-added-2026-05-16).

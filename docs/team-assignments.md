# Ownership and Required Skills

This project uses role-based ownership to keep changes small and reviewable.
The role names below are review and routing labels, not separate files that
must exist in the repository.

## Mandatory reading for every agent

Before editing any file, an agent MUST read:

1. [`docs/agent-skills.md`](agent-skills.md) — live skill index.
2. [`skills/cregis-code-quality/SKILL.md`](../skills/cregis-code-quality/SKILL.md)
   — project-customised Karpathy guidelines and project-director acceptance
   checks.
3. [`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
   — the verdict template to run on your own diff before claiming done.
4. The agent's own section in
   [`docs/acceptance-review.md`](acceptance-review.md) — the round-one
   required changes from the project director's audit.

If the agent touches scoring, patterns, direct-hit, or report content, also
read
[`skills/cregis-evidence-integrity/SKILL.md`](../skills/cregis-evidence-integrity/SKILL.md).

## Review Roles

### `aml-architect` — Principal Architect & Release Commander

- Owns: API routes in `services/api/app/main.py`, request/response models in
  `services/api/app/domain/models.py`, `docs/database/schema.sql`, module
  boundaries, `.env.example`, `services/api/app/core/`, direct-hit policy,
  release checklist, known-limitations list.
- Approves: every cross-module schema or contract change.
- Deliverables: API spec freezes, schema migrations, security/compliance
  review, final pre-release sign-off.
- Round-one acceptance status:
  [`acceptance-review.md § aml-architect`](acceptance-review.md#aml-architect)
  — `approved-with-changes` (5 required changes, no blockers).

### `risk-logic-reviewer` — Compliance Brain (read-only)

- Audits: pattern correctness, scoring calibration, direct-hit semantics,
  source-hit semantics, report hallucination risk, evidence-chain integrity.
- Deliverables: structured `approved` / `approved-with-changes` / `blocked`
  verdicts on every risk-affecting change before `aml-architect` merges it.
  Verdict template lives in
  [`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md).
- Round-one acceptance status:
  [`acceptance-review.md § risk-logic-reviewer`](acceptance-review.md#risk-logic-reviewer)
  — `approved`.

## Execution Roles

### `connector-engineer` — Third-Party Provider Integration

- Owns: `services/api/app/connectors/` (Etherscan, GoPlus) and the DeepSeek
  HTTP transport inside `services/api/app/services/reporting.py`.
- Deliverables: timeouts, bounded retries, structured `ConnectorError`,
  demo-mode determinism, caching with TTL, connector tests.
- Round-one acceptance status:
  [`acceptance-review.md § connector-engineer`](acceptance-review.md#connector-engineer)
  — `approved-with-changes` (1 required change, no blockers).

### `graph-pattern-engineer` — Graph & Pattern Algorithms

- Owns: `services/api/app/domain/graph_builder.py`,
  `services/api/app/domain/patterns.py`, network metrics, pattern fixtures.
- Deliverables: bounded 3-hop stable / 5-hop experimental tracing;
  deterministic detectors for layering, aggregation, peel chain, threshold
  structuring, high-frequency small-value, dusting, one-shot addresses,
  centrality hubs, risk propagation. Every `PatternSignal` carries `name`,
  `severity`, `score`, `subject`, `evidence`, `confidence`, `metadata`.
- Round-one acceptance status:
  [`acceptance-review.md § graph-pattern-engineer`](acceptance-review.md#graph-pattern-engineer)
  — `approved-with-changes` (2 required changes, no blockers).

### `risk-intel-engineer` — Risk Intelligence & Direct-Hit

- Owns: `services/api/app/domain/risk_intel.py`, the rule-score side of
  `services/api/app/domain/scoring.py`, watchlist persistence inside
  `services/api/app/storage/`, watchlist import endpoint in
  `services/api/app/main.py`.
- Deliverables: CSV/JSON watchlist import
  (`address,label,category,severity,notes`), explainable `SourceHit` rows,
  OFAC/PEP/sanctions/stablecoin-blacklist direct-hit semantics, calibrated
  rule weights.
- Round-one acceptance status:
  [`acceptance-review.md § risk-intel-engineer`](acceptance-review.md#risk-intel-engineer)
  — `approved-with-changes` (3 required changes, no blockers).

### `raindrop-ml-engineer` — Raindrop AML Risk Layer

- Owns: `services/api/app/ml/` and the future
  `services/ml/raindrop_aml/`.
- Deliverables: stable `RaindropAmlScorer.predict(graph) -> RaindropResult`
  adapter; AML feature tensor builder; CPU inference; optional GPU training;
  AUPRC / AUROC / Precision@K / Recall@K; versioned artefacts;
  `raindrop_score` stays advisory.
- Round-one acceptance status:
  [`acceptance-review.md § raindrop-ml-engineer`](acceptance-review.md#raindrop-ml-engineer)
  — **`blocked`** (1 blocker: duplicate scorer + isinstance branch).

### `report-engineer` — AI Report Generation

- Owns: `services/api/app/services/reporting.py` (prompt templates, local
  fallback, schema, content shape).
- Deliverables: evidence-faithful English report; explicit
  absence-of-evidence wording; demo-mode provenance markers; DeepSeek-or-local
  fallback parity.
- Round-one acceptance status:
  [`acceptance-review.md § report-engineer`](acceptance-review.md#report-engineer)
  — `approved-with-changes` (3 required changes, no blockers).

### `web-workbench-engineer` — React Analyst Workbench

- Owns: `apps/web/src/App.tsx`, `apps/web/src/styles.css`, OPPO Sans loading,
  Vite config.
- Deliverables: Wise design tokens from `DESIGN.md`; Cytoscape graph with
  loading/error/empty/loaded states; risk summary, evidence list, node
  detail, report preview; layouts at 1440 / 1180 / 390 widths.
- Round-one acceptance status:
  [`acceptance-review.md § web-workbench-engineer`](acceptance-review.md#web-workbench-engineer)
  — **`blocked`** (1 blocker: `"latest"` deps; 1 dead-state cleanup).

### `qa-devops-engineer` — Quality, Tests, Deploy

- Owns: `infra/scripts/`, `.github/workflows/`, `docker-compose.yml`,
  `pytest.ini`, smoke tests, `.env.example` implementation, deploy/run docs.
- Deliverables: one-command demo-mode boot, smoke script for the V1
  endpoints, CI green for `pytest` and `npm run build`, optional
  `docker compose up -d postgres redis`.
- Round-one acceptance status:
  [`acceptance-review.md § qa-devops-engineer`](acceptance-review.md#qa-devops-engineer)
  — **`blocked`** (1 blocker: broken `python-dotenv` pin + undocumented Python
  ≥ 3.11 requirement).

### `db-storage-engineer` — Persistence Boundary

- Owns: `docs/database/schema.sql`, `services/api/app/storage/`, migration /
  seed scripts.
- Deliverables: schema for screening events, source hits, pattern signals,
  network metrics, investigations, audit logs, watchlist; clean adapter
  interface so `InMemoryStore` and a future `PostgresStore` are
  interchangeable; documented swap path.
- Round-one acceptance status:
  [`acceptance-review.md § db-storage-engineer`](acceptance-review.md#db-storage-engineer)
  — **`blocked`** (1 blocker: speculative `PostgresStore` raising
  `NotImplementedError`).

## Coordination Rules

1. Every change proposal starts with `aml-architect` if it touches an API,
   schema, env, or module boundary.
2. Every change touching scoring, patterns, direct-hit, or report content
   needs a `risk-logic-reviewer` verdict before merge, using the template in
   [`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md).
3. Execution agents stay inside their owned files. Cross-boundary changes are
   routed through `aml-architect`.
4. `pytest` (`PYTHONPATH=services/api pytest -q`) and
   `cd apps/web && npm run build` and `bash scripts/smoke.sh` must all pass
   before any agent claims done.
5. Demo data must never be described as real intelligence in any artefact.
6. `RaindropAmlScorer.predict(graph) -> RaindropResult` interface is frozen
   until `aml-architect` approves a change.
7. **New, as of acceptance review 2026-05-16:** any diff must also pass the
   acceptance checks in
   [`skills/cregis-code-quality/SKILL.md § Acceptance Checks`](../skills/cregis-code-quality/SKILL.md#acceptance-checks-project-director-rejection-criteria).
   The project director will reject any PR that violates a hard blocker
   without re-review.

## Review Hints

- Mention by role inside a message: "Have `risk-logic-reviewer` audit the
  new direct-hit list."
- For a fresh acceptance audit at any time, run
  [`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
  against the current branch.

# Subagent Assignments

This project is delivered by ten OpenCode subagents instead of named human programmers. Two are brain agents (architecture + risk-logic review) pinned to **Codex GPT 5.5 with `reasoningEffort: high`** via [`opencode.json`](../opencode.json). Eight are execution agents that **inherit the OpenCode default model** (`mimo-v2.5-pro` in this setup) — no per-file model override, so they follow whatever default the user has configured. Definitions live in [.opencode/agents/](../.opencode/agents).

## Brain Agents (Codex GPT 5.5, `reasoningEffort: high`)

### `aml-architect` — Principal Architect & Release Commander

- File: [.opencode/agents/aml-architect.md](../.opencode/agents/aml-architect.md)
- Owns: API contracts in `services/api/app/api/`, request/response models in `services/api/app/domain/models.py`, `docs/database/schema.sql`, module boundaries, `.env.example`, `services/api/app/core/`, direct-hit policy, release checklist, known-limitations list.
- Approves: every cross-module schema or contract change.
- Deliverables: API spec freezes, schema migrations, security/compliance review, final pre-release sign-off.

### `risk-logic-reviewer` — Compliance Brain (read-only)

- File: [.opencode/agents/risk-logic-reviewer.md](../.opencode/agents/risk-logic-reviewer.md)
- Audits: pattern correctness, scoring calibration, direct-hit semantics, source-hit semantics, report hallucination risk, evidence-chain integrity.
- Deliverables: structured `approved` / `approved-with-changes` / `blocked` verdicts on every risk-affecting change before `aml-architect` merges it.

## Execution Agents (OpenCode default model, e.g. `mimo-v2.5-pro`)

### `connector-engineer` — Third-Party Provider Integration

- File: [.opencode/agents/connector-engineer.md](../.opencode/agents/connector-engineer.md)
- Owns: `services/api/app/connectors/` (Etherscan, GoPlus) and the DeepSeek HTTP transport inside `services/api/app/services/reporting.py`.
- Deliverables: timeouts, bounded retries, structured `ConnectorError`, demo-mode determinism, caching with TTL, connector tests.

### `graph-pattern-engineer` — Graph & Pattern Algorithms

- File: [.opencode/agents/graph-pattern-engineer.md](../.opencode/agents/graph-pattern-engineer.md)
- Owns: `services/api/app/domain/graph_builder.py`, `services/api/app/domain/patterns.py`, network metrics, pattern fixtures.
- Deliverables: bounded 3-hop stable / 5-hop experimental tracing; deterministic detectors for layering, aggregation, peel chain, threshold structuring, high-frequency small-value, dusting, one-shot addresses, centrality hubs, risk propagation. Every `PatternSignal` carries `name`, `severity`, `score`, `subject`, `evidence`, `confidence`, `metadata`.

### `risk-intel-engineer` — Risk Intelligence & Direct-Hit

- File: [.opencode/agents/risk-intel-engineer.md](../.opencode/agents/risk-intel-engineer.md)
- Owns: `services/api/app/domain/risk_intel.py`, the rule-score side of `services/api/app/domain/scoring.py`, watchlist persistence inside `services/api/app/storage/`, watchlist import endpoint in `services/api/app/api/`.
- Deliverables: CSV/JSON watchlist import (`address,label,category,severity,notes`), explainable `SourceHit` rows, OFAC/PEP/sanctions/stablecoin-blacklist direct-hit semantics, calibrated rule weights.

### `raindrop-ml-engineer` — Raindrop AML Risk Layer

- File: [.opencode/agents/raindrop-ml-engineer.md](../.opencode/agents/raindrop-ml-engineer.md)
- Owns: `services/api/app/ml/` and the future `services/ml/raindrop_aml/`.
- Deliverables: stable `RaindropAmlScorer.predict(graph)` adapter; AML feature tensor builder; CPU inference; optional GPU training; AUPRC/AUROC/Precision@K/Recall@K; versioned artefacts; `raindrop_score` stays advisory.

### `report-engineer` — AI Report Generation

- File: [.opencode/agents/report-engineer.md](../.opencode/agents/report-engineer.md)
- Owns: `services/api/app/services/reporting.py` (prompt templates, local fallback, schema, content shape).
- Deliverables: evidence-faithful English report; explicit absence-of-evidence wording; demo-mode provenance markers; DeepSeek-or-local fallback parity.

### `web-workbench-engineer` — React Analyst Workbench

- File: [.opencode/agents/web-workbench-engineer.md](../.opencode/agents/web-workbench-engineer.md)
- Owns: `apps/web/src/App.tsx`, `apps/web/src/styles.css`, OPPO Sans loading, Vite config.
- Deliverables: Wise design tokens from `DESIGN.md`; Cytoscape graph with loading/error/empty/loaded states; risk summary, evidence list, node detail, report preview; layouts at 1440 / 1180 / 390 widths.

### `qa-devops-engineer` — Quality, Tests, Deploy

- File: [.opencode/agents/qa-devops-engineer.md](../.opencode/agents/qa-devops-engineer.md)
- Owns: `infra/scripts/`, `.github/workflows/`, `docker-compose.yml`, `pytest.ini`, smoke tests, `.env.example` implementation, deploy/run docs.
- Deliverables: one-command demo-mode boot, smoke script for the V1 endpoints, CI green for `pytest` and `npm run build`, optional `docker compose up -d postgres redis`.

### `db-storage-engineer` — Persistence Boundary

- File: [.opencode/agents/db-storage-engineer.md](../.opencode/agents/db-storage-engineer.md)
- Owns: `docs/database/schema.sql`, `services/api/app/storage/`, migration / seed scripts.
- Deliverables: schema for screening events, source hits, pattern signals, network metrics, investigations, audit logs, watchlist; clean adapter interface so `InMemoryStore` and a future `PostgresStore` are interchangeable; documented swap path.

## Coordination Rules

1. Every change proposal starts with `aml-architect` if it touches an API, schema, env, or module boundary.
2. Every change touching scoring, patterns, direct-hit, or report content needs a `risk-logic-reviewer` verdict before merge.
3. Execution agents stay inside their owned files. Cross-boundary changes are routed through `aml-architect`.
4. `pytest` (`PYTHONPATH=services/api pytest -q`) and `cd apps/web && npm run build` must pass before any agent claims done.
5. Demo data must never be described as real intelligence in any artefact.
6. `RaindropAmlScorer.predict(graph)` interface is frozen until `aml-architect` approves a change.

## Invocation Hints

- Explicit invocation in the OpenCode chat box: `@aml-architect`, `@risk-logic-reviewer`, `@connector-engineer`, etc.
- Mention by role inside a message: "Have `risk-logic-reviewer` audit the new direct-hit list."
- Parallel work: ask the primary agent (Build) to "use the Task tool to dispatch X, Y, Z in parallel" in a single turn — they run as concurrent child sessions and report back. See [`.opencode/README.md`](../.opencode/README.md) for the one-shot delivery prompt.

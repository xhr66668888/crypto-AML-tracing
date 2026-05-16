# AGENTS.md — Cregis ETH AML Tracing

This file is the single discovery point for every agent runtime working in this
repository (Cursor, OpenCode, Codex, Claude Code, etc.). Read it before doing
anything.

## 1. Code quality

You MUST follow the project-customised Karpathy guidelines and acceptance
checks at:

- [`skills/cregis-code-quality/SKILL.md`](skills/cregis-code-quality/SKILL.md)
- [`skills/cregis-pre-merge-review/SKILL.md`](skills/cregis-pre-merge-review/SKILL.md)
- [`skills/cregis-evidence-integrity/SKILL.md`](skills/cregis-evidence-integrity/SKILL.md)

The project director enforces these at acceptance. A diff that violates a
**hard blocker** listed in the first skill will be rejected without
re-review.

## 2. Ownership

Edit only files inside the paths owned by your subagent role as defined in
[`docs/team-assignments.md`](docs/team-assignments.md). Cross-boundary changes
are routed through `aml-architect` first.

## 3. Acceptance commands

A change is "done" only when **all three** commands below exit zero:

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
cd apps/web && npm run build
bash scripts/smoke.sh   # against a running API
```

## 4. Compliance invariants

- Every risk conclusion cites a `source_hit`, `pattern_signal`, or `evidence`
  row.
- Demo data is never described as real intel. Reports in demo mode carry the
  `DEMONSTRATION DATA` header.
- Direct-hit categories (`ofac`, `pep`, `sanctions`, `sanctioned`,
  `circle_blacklist`, `tether_blacklist`, `stablecoin_blacklist`) force
  `hold_for_manual_review` regardless of behavioural score.
- `RaindropAmlScorer.predict(graph)` signature is frozen until `aml-architect`
  approves a change.

Full rationale lives in
[`skills/cregis-evidence-integrity/SKILL.md`](skills/cregis-evidence-integrity/SKILL.md).

## 5. Acceptance review

Open audit findings, per-subagent required changes, and pre-release blockers
live in [`docs/acceptance-review.md`](docs/acceptance-review.md). Read your
subagent's section before starting a new task.

# Project Skills

This file is the live skill index for agents and human contributors working in
this repository. It replaces the former root-level discovery file.

## Required Skills

Read these before changing any file under `services/`, `apps/web/`, `infra/`,
`scripts/`, or `docs/`:

- [`cregis-code-quality`](../skills/cregis-code-quality/SKILL.md): project
  code-quality rules, Karpathy-style simplicity checks, ownership boundaries,
  and hard acceptance blockers.
- [`cregis-pre-merge-review`](../skills/cregis-pre-merge-review/SKILL.md):
  executable review checklist and verdict template to run before claiming a
  change is done.

Also read this when touching scoring, patterns, source hits, watchlists,
direct-hit policy, screening decisions, or report content:

- [`cregis-evidence-integrity`](../skills/cregis-evidence-integrity/SKILL.md):
  compliance invariants for source-backed risk conclusions, demo-data wording,
  direct-hit overrides, Raindrop advisory scoring, and report faithfulness.

## Ownership Map

Path ownership and role responsibilities live in
[`docs/team-assignments.md`](team-assignments.md). If a change crosses an
ownership boundary, route it through `aml-architect` before editing.

## Acceptance Commands

A change is done only when the relevant targeted tests pass and the full
project gate is green:

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
cd apps/web && npm run build
bash scripts/smoke.sh
```

`scripts/smoke.sh` expects the API to be running.

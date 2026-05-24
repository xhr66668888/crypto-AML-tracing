---
name: cregis-pre-merge-review
description: Project-director pre-merge review checklist for the Cregis ETH AML Tracing repo. Use when reviewing a PR, an agent's diff, or your own diff before claiming "done". Returns a structured approved / approved-with-changes / blocked verdict with exact file:line citations.
license: MIT
applies_to:
  - services/api/**
  - apps/web/**
  - docs/**
---

# Cregis Pre-Merge Review

Use this skill to run the same review the project director runs at acceptance.
It is the *executable* form of `skills/cregis-code-quality/SKILL.md`. The
review must produce a structured verdict — `approved`, `approved-with-changes`,
or `blocked` — with exact file:line citations.

## When to use

- Before opening a PR for any change touching `services/`, `apps/web/`, or
  `docs/`.
- Before an agent claims "done".
- As the `risk-logic-reviewer` audit step for any scoring / pattern /
  direct-hit / report-content change.

## Procedure

Run the steps in order. Stop at the first **blocking** failure and report it.

### Step 1 — Dead-code sweep

```bash
# Python unused imports / unused symbols
ruff check --select F401,F811,F841 services/api/app

# TypeScript dead code
cd apps/web && npx tsc --noEmit && npx eslint --max-warnings 0 src
```

Then grep for the project-specific anti-patterns:

```bash
rg -n 'NotImplementedError|TODO|FIXME|XXX' services/api/app
rg -n '^\s*#.*=' services/api/app/domain/scoring.py   # commented-out alt code
```

Verdict:
- Any `NotImplementedError` raised in non-test code → **blocked**.
- Any commented-out alternative logic in `scoring.py`, `patterns.py`, or
  `reporting.py` → **blocked**.
- Any abstract method on `StorageAdapter` that is never called from
  `services/` or `app/main.py` → **blocked** (delete the method).

### Step 2 — Orphan-module sweep

For Python:

```bash
PYTHONPATH=services/api python -c "
import importlib, pkgutil, sys
roots = ['app.main', 'app.tests']
seen = set()
def visit(mod):
    if mod in seen: return
    seen.add(mod)
    m = importlib.import_module(mod)
    for _, name, _ in pkgutil.iter_modules(getattr(m, '__path__', [])):
        visit(f'{mod}.{name}')
for r in roots: visit(r)
all_mods = set()
for _, name, _ in pkgutil.walk_packages(['services/api/app'], prefix='app.'):
    all_mods.add(name)
orphans = sorted(all_mods - seen)
print('\n'.join(orphans) or 'no orphans')
"
```

Any orphan module → **blocked** unless the PR description explicitly justifies
why it must live in the tree (e.g. a feature flag is documented).

For TypeScript, run `npx ts-prune` or equivalent.

### Step 3 — Contract & ownership sweep

```bash
git diff --name-only origin/main...HEAD
```

For each changed path, look up its owner in `docs/team-assignments.md`:

- File touches `services/api/app/api/`, `services/api/app/domain/models.py`,
  `docs/database/schema.sql`, `.env.example`, `services/api/app/core/` → must
  have `aml-architect` approval line in the PR body.
- File touches scoring, patterns, direct-hit, or report content → must have
  `risk-logic-reviewer` verdict in the PR body.
- File is outside the diffing agent's owned paths → **blocked** unless
  routed through `aml-architect`.

### Step 4 — Reproducibility sweep

```bash
# No floating dependencies in the frontend
rg -n '"latest"' apps/web/package.json && echo "BLOCKED" || echo "ok"

# All Python deps installable
python -m pip install --dry-run -r services/api/requirements.txt

# Python version assumption stated
rg -n 'from datetime import UTC|datetime\.UTC' services/api/app && \
  grep -q 'python_requires\|Python 3.11\|python>=3.11' README.md services/api/requirements.txt || \
  echo "BLOCKED: code requires Python 3.11+ but README does not say so"
```

### Step 5 — Test & build sweep

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
cd apps/web && npm ci && npm run build
bash scripts/smoke.sh
```

Any non-zero exit code → **blocked**.

## Verdict template

Paste this into the PR or the agent reply:

```
Verdict: approved | approved-with-changes | blocked

Karpathy §1 (Think Before Coding):
  - <findings or "none">

Karpathy §2 (Simplicity First):
  - <file:line> — <why this is speculative>
  - ...

Karpathy §3 (Surgical Changes):
  - <file:line> — <why this is unrelated to the request>
  - ...

Karpathy §4 (Goal-Driven Execution):
  - pytest: PASS|FAIL (<N>/<M>)
  - npm run build: PASS|FAIL
  - smoke.sh: PASS|FAIL

Required changes (only if approved-with-changes / blocked):
  1. <file:line> — <action>
  2. ...
```

## Why this exists

See `docs/acceptance-review.md` for the round-one violations this skill is
designed to catch.

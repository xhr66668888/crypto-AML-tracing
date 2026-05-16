---
name: cregis-code-quality
description: Cregis ETH AML Tracing code-quality bar. Use when writing, reviewing, or refactoring any file under services/, apps/web/, infra/, scripts/, or docs/. Project-customised port of Andrej Karpathy's LLM-coding guidelines, with the concrete checks the project director enforces at acceptance.
license: MIT
applies_to:
  - services/api/**
  - apps/web/**
  - infra/**
  - scripts/**
  - docs/**
---

# Cregis Code Quality (Karpathy, project-customised)

This is the company quality bar for the Cregis ETH AML Tracing project. It is the
project-customised version of the Karpathy LLM-coding guidelines under
`andrej-karpathy-skills/skills/karpathy-guidelines/`. Every subagent under
`.opencode/agents/` and every human contributor MUST follow it.

The project director will reject any PR or subagent diff that violates one of
the **Acceptance Checks** at the bottom of this file.

**Tradeoff:** these rules bias toward caution over speed. For trivial typo-class
edits, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before editing any file in this repository:

- State your assumptions explicitly. If uncertain, ask the project director or
  the owning subagent listed in `docs/team-assignments.md`.
- If multiple interpretations of a request exist, present them — do not pick
  silently.
- If a simpler approach exists, say so and push back when warranted.
- If something is unclear, stop. Name what is confusing. Ask.

**Project-specific examples of confusion that MUST be surfaced, not guessed:**

- Anything that would change `RaindropAmlScorer.predict(graph)` signature — frozen
  by `aml-architect`.
- Anything that would change `DIRECT_HIT_CATEGORIES` in `domain/models.py`.
- Adding a new field to a `ScreeningResponse`, `RiskResponse`, `ReportResponse`,
  or `InvestigationStatus`.
- Adding a new endpoint to `services/api/app/main.py`.
- Adding a new env var to `.env.example` or `core/config.py`.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- No abstract methods on `StorageAdapter` that no caller in `services/` or
  `main.py` invokes.
- No alternative scorer / reporter / adapter "for future use" — delete it until
  there is a caller. Speculative code is the single most common Karpathy
  violation in this codebase.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: *"Would a senior compliance engineer say this is overcomplicated?"*
If yes, simplify.

**Project-specific anti-patterns that violate this rule and have been observed
at acceptance:**

- A second `RaindropAmlScorer` (`raindrop_aml.py`) that mirrors the live one
  (`raindrop_scorer.py`) but is not imported anywhere.
- A `PostgresStore` class with `TODO`s and `NotImplementedError` raised, kept
  next to a working `InMemoryStore` without a feature flag to switch to it.
- Demo helpers (`_demo_internal_transactions`) tested but with no production
  caller in `services/`.
- `isinstance(result, tuple)` branches in `scoring.py` that exist only to
  support a dead alternative adapter.
- A `DeepSeekReporter` "backward-compatible alias" in a V1 codebase that has
  never had a V0.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it in your PR description — do
  not silently delete it.

When your changes create orphans:

- Remove imports / variables / functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked or unless it sits inside
  the file you are editing AND is unambiguously dead.

**Cross-module rule:** Execution agents stay inside the files listed in their
`.opencode/agents/*.md` "owned paths". Any change outside owned paths goes
through `aml-architect` first.

The test: every changed line should trace directly to the user's request OR to
an `aml-architect`-approved contract change.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass."
- "Fix the bug" → "Write a test that reproduces it, then make it pass."
- "Refactor X" → "Ensure tests pass before and after."
- "Delete dead code" → "Run `pytest -q` and `npm run build`, both green."

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

**Project-specific verification commands (the ONLY ones that count for
"done"):**

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
cd apps/web && npm run build
bash scripts/smoke.sh   # against a running API
```

Strong success criteria let you loop independently. Weak criteria ("make it
work") require constant clarification.

## Acceptance Checks (project-director rejection criteria)

A diff fails acceptance if any of these are true. The reviewer should grep,
not skim:

1. **No dead imports.** `python -c "import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]"` then `ruff check --select F401` is clean for changed files. Equivalent for TypeScript: `tsc --noEmit` is clean.
2. **No unused parameters.** Every function parameter is read inside the function body, or is documented as part of a frozen public interface.
3. **No orphan modules.** Every `.py` file under `services/api/app/` is imported transitively from `app.main`, OR from `app.tests.*`. Every `.ts/.tsx` file under `apps/web/src/` is imported transitively from `apps/web/src/main.tsx`.
4. **No commented-out alternative code.** If the alternative is worth keeping, open an issue. Otherwise delete it.
5. **No `NotImplementedError` raised in non-test code.** A speculative implementation that raises `NotImplementedError` is dead code.
6. **No abstract methods without a production caller.** If `StorageAdapter.foo()` is `@abstractmethod` but `services/api/app/services/` and `services/api/app/main.py` never call `store.foo(...)`, delete `foo`.
7. **Dependency pins exist.** No `"latest"` in `apps/web/package.json` `dependencies` / `devDependencies`. Every version in `services/api/requirements.txt` is published on PyPI for the documented Python version.
8. **Python version assumption is documented.** If `from datetime import UTC` is used anywhere, `README.md` and `services/api/requirements.txt` document `python_requires>=3.11`.
9. **Every contract change goes through `aml-architect`.** A diff that touches `services/api/app/api/`, `services/api/app/domain/models.py`, `docs/database/schema.sql`, `.env.example`, or `services/api/app/core/` without an `aml-architect` approval line in the PR body is blocked.
10. **Every scoring / pattern / direct-hit / report-content change goes through `risk-logic-reviewer`.** Diff is blocked without a `risk-logic-reviewer` verdict.

## How to Invoke This Skill

- Cursor: this skill is auto-loaded via `.cursor/rules/cregis-code-quality.mdc`.
- OpenCode subagents: each agent definition under `.opencode/agents/` lists this
  skill in its `Inputs you must read before deciding` section.
- Humans: read this file before opening a PR. The project director enforces it
  at merge time.

## Why These Rules

These rules are working if: fewer unnecessary changes in diffs, fewer rewrites
due to overcomplication, and clarifying questions come **before**
implementation rather than after mistakes. See the audit findings in
`docs/acceptance-review.md` for the concrete violations these rules are
designed to prevent in this codebase.

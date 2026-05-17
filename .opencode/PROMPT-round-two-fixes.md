# Round-two acceptance fixes — paste-ready OpenCode prompt

This file is the one-shot dispatch prompt for the project director's
round-two re-audit. Paste the block below into the OpenCode chat box once,
and the Build primary agent will use the Task tool to dispatch all ten
subagents through three dependency waves. Each subagent already has its
specific round-two task documented in
[`docs/acceptance-review-round-two.md`](../docs/acceptance-review-round-two.md)
and in the `## Round-two task` section of its own
[`.opencode/agents/*.md`](./agents/) file.

Round-one prompt: [`PROMPT-acceptance-fixes.md`](PROMPT-acceptance-fixes.md).

## Why this prompt exists

The round-one audit declared `approved` but missed 3 hard blockers and 5
§2/§3 cleanups (orphan `postgres.py` import, real-shaped secrets in
`.env.example`, hard-coded "demo" footer, dead `ReportRequest.language`
field, 9 ruff F401/F841 findings, empty `services/api/app/api/` package,
dead `DATABASE_URL` lines in `.env.example`, an "approved" summary that
contradicts the live tree). See the round-two doc for file:line citations
and reproducers.

## The prompt — paste this whole block into the OpenCode chat box

```
You are the Build primary agent for Cregis ETH AML Tracing. Run the project
director's round-two acceptance fixes in this single turn.

Mandatory reading (every dispatched subagent must read these before editing
their file):
- docs/acceptance-review-round-two.md  (the round-two findings + per-agent task)
- skills/cregis-code-quality/SKILL.md   (the Karpathy quality bar)
- skills/cregis-pre-merge-review/SKILL.md (run on your own diff before reporting back)
- The "Round-two task" section of your own .opencode/agents/<name>.md file.

Use the Task tool to dispatch the following subagents in three waves. Each
subagent's task is already documented; the prompt below is the dispatch
instruction, not the task itself.

WAVE A — contract / boundary (must close before Wave B starts):
  @aml-architect : execute round-two items R2-C2 (unused model_validator on
    domain/models.py:7), R2-C3 (resolve services/api/app/api/ empty-package
    ambiguity, prefer Option A = delete + update agent docs), pre-approve
    report-engineer's R2-C1 contract change so the contract-changelog entry
    can land in the same wave. Hold R2-C5 until Wave C.

  @db-storage-engineer : execute R2-B1 (rewrite storage/factory.py to
    return InMemoryStore unconditionally; drop os/importlib/warnings/
    _psycopg2_available imports) and R2-C4 (delete the two DATABASE_URL
    comment lines from .env.example, add "Step 0" reminder to
    docs/database/swap-to-postgres.md). Verify the round-two reproducer
    prints "ok" not ModuleNotFoundError.

WAVE B — execution (run in parallel after Wave A is green):
  @qa-devops-engineer : execute R2-B2 (empty GOPLUS_TOKEN and
    DEEPSEEK_API_KEY values in .env.example; rotate at provider if either
    was ever real, scrub history with git filter-repo only after
    aml-architect approval) and R2-C2 follow-up (add
    services/api/requirements-dev.txt with the local ruff version, add a
    ruff F401/F811/F841 step to .github/workflows/ci.yml).

  @web-workbench-engineer : execute R2-B3 (replace the hard-coded "Demo
    data — not real intelligence" footer in apps/web/src/App.tsx with a
    single useEffect that polls /health on mount and renders the footer
    only when demo_mode === true). Touch App.tsx only — no styles.css,
    no component changes.

  @report-engineer : execute R2-C1 (delete `language: str = "en"` from
    services/api/app/domain/models.py:189 — coordinate with aml-architect
    for the contract-changelog entry) and R2-C2 (delete the unused
    DEMO_HEADER import from services/api/app/tests/test_reporting.py:37).

  @connector-engineer : execute R2-C2 (drop the unused `as exc` binding on
    services/api/app/connectors/etherscan.py:200 — leave the matching
    httpx.HTTPError block on line 208 alone, it uses exc).

  @graph-pattern-engineer : execute R2-C2 (drop unused `field` import on
    services/api/app/domain/graph_builder.py:4 and unused `pytest` import
    on services/api/app/tests/test_patterns.py:11).

  @risk-intel-engineer : execute R2-C2 (drop unused `json` import on
    services/api/app/tests/test_risk_intel.py:15). No risk-logic change.

  @raindrop-ml-engineer : execute R2-C2 (drop unused `math` import on
    services/api/app/ml/features.py:12, unused `field` on
    services/api/app/ml/raindrop_scorer.py:13, unused `RiskLevel` on
    services/api/app/tests/test_ml.py:21). RaindropAmlScorer.predict
    signature stays frozen.

WAVE C — gate (after Waves A + B return):
  @risk-logic-reviewer : read-only re-audit of services/api/app/domain/
    scoring.py, patterns.py, risk_intel.py, services/api/app/services/
    reporting.py, and apps/web/src/App.tsx. Run the full procedure in
    skills/cregis-pre-merge-review/SKILL.md and verify the five compliance
    invariants in your own .opencode/agents/risk-logic-reviewer.md
    Round-two section. Return an approved / approved-with-changes /
    blocked verdict using the verdict template.

  @aml-architect : final round-two sign-off. Once risk-logic-reviewer
    returns approved AND all four round-two exit criteria hold (ruff
    clean; .env.example has empty secrets; factory reproducer prints ok;
    frontend footer absent under DEMO_MODE=false), execute R2-C5: flip
    docs/acceptance-review.md overall verdict back to `approved`, add a
    one-line "Round two closed YYYY-MM-DD" entry under the round-two
    section. Cut the V1 tag only after this.

Hard invariants (every wave):
1. The Karpathy hard blockers in skills/cregis-code-quality/SKILL.md §
   "Acceptance Checks (project-director rejection criteria)" stay green
   on the merged diff. Re-run them before reporting back.
2. RaindropAmlScorer.predict(graph) -> RaindropResult signature is frozen.
3. DIRECT_HIT_CATEGORIES stays frozen until aml-architect approves a
   change.
4. Every diff must trace to a specific round-two task. No drive-by
   refactors. Karpathy §3 — surgical changes only.
5. Three commands must exit zero before any agent claims done:
     PYTHONPATH=services/api python -m pytest -q services/api/app/tests
     cd apps/web && npm run build
     bash scripts/smoke.sh
   plus the new check:
     ruff check --select F401,F811,F841 services/api/app
   plus the round-two-specific checks listed in each agent's
   Round-two task block.

When every subagent reports back, summarise:
- Which round-two items closed and which did not.
- Status of all four exit criteria from
  docs/acceptance-review-round-two.md § "Exit criteria for round two".
- The final risk-logic-reviewer verdict.
- Whether aml-architect re-declared `approved` in
  docs/acceptance-review.md.
```

## Dependency order (why three waves)

```
       Wave A                Wave B                       Wave C
┌─────────────────────┐    ┌────────────────────────┐    ┌──────────────────────┐
│ aml-architect       │    │ qa-devops-engineer     │    │ risk-logic-reviewer  │
│   R2-C2, R2-C3      │    │   R2-B2, R2-C2 CI step │    │   read-only verdict  │
│   pre-approve C1    │    │                         │    │                      │
│                     │    │ web-workbench-engineer │    └──────────┬───────────┘
│ db-storage-engineer │    │   R2-B3                 │               │
│   R2-B1, R2-C4      │    │                         │    ┌──────────▼───────────┐
└─────────┬───────────┘    │ report-engineer         │    │ aml-architect        │
          │                │   R2-C1, R2-C2 test     │    │   R2-C5 sign-off     │
          │                │                         │    └──────────────────────┘
          └────────────────► connector-engineer      │
                           │   R2-C2                 │
                           │                         │
                           │ graph-pattern-engineer  │
                           │   R2-C2 × 2             │
                           │                         │
                           │ risk-intel-engineer     │
                           │   R2-C2                 │
                           │                         │
                           │ raindrop-ml-engineer    │
                           │   R2-C2 × 3             │
                           └─────────────────────────┘
```

Wave A finishes the contract / boundary changes (R2-B1, R2-C3, R2-C4) so
Wave B's ruff-cleanup work is not blocked by a structural disagreement
about where routes live or whether `PostgresStore` exists. Wave C is the
gate.

## Exit criteria (paste back to the project director)

After all three waves report, confirm these four lines exit zero / behave
as described:

```bash
# 1. Ruff clean
ruff check --select F401,F811,F841 services/api/app

# 2. .env.example secrets empty
grep -E '^(GOPLUS_TOKEN|DEEPSEEK_API_KEY|DATABASE_URL)=.+' .env.example
# (expected: no output)

# 3. Factory reproducer prints `ok`
PYTHONPATH=.python-deps:services/api python3 -c "
import os; os.environ['DATABASE_URL']='postgresql://x:x@y/z'
from app.storage.factory import get_store
assert type(get_store()).__name__ == 'InMemoryStore'
print('ok')
"

# 4. Frontend footer follows demo_mode
# Boot with DEMO_MODE=true  → footer renders.
# Boot with DEMO_MODE=false → footer is absent.
```

Plus the always-green three:

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
cd apps/web && npm run build
bash scripts/smoke.sh
```

When all four round-two checks and the three always-green checks pass,
`aml-architect` flips `docs/acceptance-review.md` back to `approved` and
tags V1.

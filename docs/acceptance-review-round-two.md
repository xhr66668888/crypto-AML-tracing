# V1 Acceptance Review — Round Two

**Reviewer:** project director
**Date:** 2026-05-16 (round-two re-audit)
**Branch reviewed:** `main` at HEAD as of this commit
**Quality bar:** [`skills/cregis-code-quality/SKILL.md`](../skills/cregis-code-quality/SKILL.md)
(project-customised port of
[`andrej-karpathy-skills/skills/karpathy-guidelines/SKILL.md`](../andrej-karpathy-skills/skills/karpathy-guidelines/SKILL.md))

## Overall verdict

**`approved-with-changes` (NOT yet shippable).**
[`docs/acceptance-review.md`](acceptance-review.md) currently advertises a clean
`approved` verdict and a "Karpathy §2 cleanup removed ~1,200 lines" claim. The
round-two re-audit below shows that **3 hard blockers and 5 §2/§3 cleanups were
left open** after round one, so the round-one closure note is incorrect. The
fix list is small and bounded.

Acceptance commands still all pass on the happy path:

- `pytest -q services/api/app/tests` → 223/223 green.
- `npm run build` → green.
- `scripts/smoke.sh` → green in demo mode.

These prove the demo-mode happy path, but **none of them exercise the bugs
listed below**, so passing them is not sufficient for V1 sign-off.

## Why this review exists (Karpathy §1 — surface confusion before merging)

The round-one document states "All round-one findings closed" but
`ruff check --select F401,F811,F841 services/api/app` reports 9 violations
right now, half in non-test code, and `services/api/app/storage/factory.py:39`
imports a module (`app.storage.postgres`) that round-one explicitly deleted.
Either the round-one verdict was issued without re-running the acceptance
checks, or the checks were silently softened. Either way, the right response is
a public round-two list and per-agent tasks — not silent edits.

## Findings — hard blockers (must be fixed before tagging V1)

| # | File:line | Severity | Owner |
| - | --------- | -------- | ----- |
| **R2-B1** | [`services/api/app/storage/factory.py:39`](../services/api/app/storage/factory.py#L39) | **blocker** | `db-storage-engineer` + `aml-architect` |
| **R2-B2** | [`.env.example:7-8`](../.env.example) | **blocker (security)** | `qa-devops-engineer` + `aml-architect` |
| **R2-B3** | [`apps/web/src/App.tsx:60`](../apps/web/src/App.tsx#L60) | **blocker (compliance)** | `web-workbench-engineer` |

### R2-B1 — Orphan import to a module that round-one deleted

`services/api/app/storage/factory.py:39` does
`from app.storage.postgres import PostgresStore`, but
`services/api/app/storage/postgres.py` was deleted in round one. Reproduction:

```bash
PYTHONPATH=.python-deps:services/api python3 -c "
import os, app.storage.factory as f
f._psycopg2_available = lambda: True
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
f.get_store()
"
# → ModuleNotFoundError: No module named 'app.storage.postgres'
```

Round-one chose Option A ("delete the speculative adapter, schema is the
contract" — see [`docs/database/swap-to-postgres.md`](database/swap-to-postgres.md)),
but the factory branch that hands a request to that adapter was not deleted.
Karpathy §3: "Remove imports/variables/functions that **your** changes made
unused." Today the project ships a runtime trap door: a `DATABASE_URL` plus a
`pip install psycopg2-binary` is enough to crash the API at startup.

### R2-B2 — Real-shaped secrets committed in `.env.example`

```env
GOPLUS_TOKEN=FacJJ5VSnN63Z3fFQZYm3n2jwFSD6UFT
DEEPSEEK_API_KEY=sk-0f670fa8f14b4f608c22f37a0c7deb63
```

`.env.example` is committed to git and is the file `scripts/boot-demo.sh` copies
to `.env` on a fresh machine. If these tokens are real, the leak window starts
the moment the repo was pushed and we must rotate both providers and rewrite
git history with `git filter-repo`. If they were invented to "look real", we
still ship a file that trains operators to leave tokens in `.env.example` —
which is exactly the failure mode this file is supposed to prevent.

Karpathy §1 — wrong assumption: the original author silently assumed the
example file is for "shape only" while writing values that look like live
credentials. The right behaviour is empty strings (`GOPLUS_TOKEN=`,
`DEEPSEEK_API_KEY=`) and a one-line comment that says the operator must paste
their own key.

### R2-B3 — Frontend "DEMO" disclaimer is a lie

`apps/web/src/App.tsx:58-61` ships the line:

```tsx
<p className="footer-note">Demo data — not real intelligence</p>
```

This footer is **hard-coded**. It renders regardless of the `/health` endpoint's
`demo_mode` value. `cregis-evidence-integrity` §2 explicitly says:

> "The frontend MUST surface a 'Demo data — not real intelligence' footer when
> the API responds with `demo_mode: true` in `/health`."

When `DEMO_MODE=false` (the production case) the footer is misleading: it tells
an analyst the data is simulated even though it is real provider output. When
`DEMO_MODE=true` the footer is correct but its presence is coincidental, not
caused by the API state. Either way the invariant in the evidence-integrity
skill is violated.

The fix is a single `useEffect` that polls `/health` once on mount and renders
the footer only when `demo_mode === true`. (Round one rejected wiring
`connectionStatus` because nothing called the setter — this is the correct
caller.)

## Findings — Karpathy §2 / §3 cleanups (not blockers but reject at merge)

| # | File:line | Why it fails | Owner |
| - | --------- | ------------ | ----- |
| **R2-C1** | [`services/api/app/domain/models.py:189`](../services/api/app/domain/models.py#L189) | `ReportRequest.language: str = "en"` — no caller reads it | `report-engineer` + `aml-architect` |
| **R2-C2** | 5× live + 4× test ruff F401/F841 | acceptance check #1 fails today | per-owner (see below) |
| **R2-C3** | [`services/api/app/api/__init__.py`](../services/api/app/api/__init__.py) | empty package; `aml-architect.md` and `team-assignments.md` claim ownership of `services/api/app/api/` but all routes live in `main.py` | `aml-architect` |
| **R2-C4** | [`.env.example:3-4`](../.env.example) | advertises `DATABASE_URL` switch that R2-B1 made non-functional | paired with R2-B1, `db-storage-engineer` |
| **R2-C5** | [`docs/acceptance-review.md`](acceptance-review.md) overall verdict | declares `approved` while R2-B1/B2/B3 are still open | `aml-architect` |

### R2-C1 — Dead `language` field in `ReportRequest`

Round-one report-engineer §2 said "delete the `language` parameter". The fix
was applied to `services/api/app/services/reporting.py` but the field is still
present at `services/api/app/domain/models.py:189`. Because `ReportRequest` is
the public OpenAPI surface for `POST /api/v1/investigations/{id}/reports`, a
client today can send `{"language": "fr"}` and get a 200 — without anything in
the code consuming it. That is the precise definition of "speculative
configurability" the skill calls out.

### R2-C2 — Nine ruff findings (acceptance check #1 fails)

```bash
$ ruff check --select F401,F811,F841 services/api/app
Found 9 errors.
```

Live code:

| File | Line | Finding | Owner |
| ---- | ---- | ------- | ----- |
| `services/api/app/connectors/etherscan.py` | 200 | `F841` — unused `exc` in `except httpx.TimeoutException as exc` | `connector-engineer` |
| `services/api/app/domain/graph_builder.py` | 4 | `F401` — `dataclasses.field` unused | `graph-pattern-engineer` |
| `services/api/app/domain/models.py` | 7 | `F401` — `pydantic.model_validator` unused | `aml-architect` (models.py is contract) |
| `services/api/app/ml/features.py` | 12 | `F401` — `math` unused | `raindrop-ml-engineer` |
| `services/api/app/ml/raindrop_scorer.py` | 13 | `F401` — `dataclasses.field` unused | `raindrop-ml-engineer` |

Tests:

| File | Line | Finding | Owner |
| ---- | ---- | ------- | ----- |
| `services/api/app/tests/test_ml.py` | 21 | `F401` — `RiskLevel` unused | `raindrop-ml-engineer` |
| `services/api/app/tests/test_patterns.py` | 11 | `F401` — `pytest` unused | `graph-pattern-engineer` |
| `services/api/app/tests/test_reporting.py` | 37 | `F401` — `DEMO_HEADER` unused | `report-engineer` |
| `services/api/app/tests/test_risk_intel.py` | 15 | `F401` — `json` unused | `risk-intel-engineer` |

`qa-devops-engineer` then wires `ruff check --select F401,F811,F841 services/api/app`
into `.github/workflows/ci.yml` so the next regression fails CI, not the
acceptance audit.

### R2-C3 — Empty `services/api/app/api/` package

`services/api/app/api/__init__.py` exists with only `"""HTTP API routes."""`
inside. The package contains no `.py` files; every route lives inline in
`services/api/app/main.py`. Two of the contract documents
([`aml-architect.md`](../.opencode/agents/aml-architect.md) and
[`team-assignments.md § aml-architect`](team-assignments.md)) claim ownership of
"API contracts in `services/api/app/api/`". The codebase silently disagrees.

Pick one of two corrections and stay there:

- **Option A — keep routes in `main.py`.** Delete the empty `api/` package and
  remove all "in `services/api/app/api/`" wording from
  `.opencode/agents/aml-architect.md`,
  `.opencode/agents/risk-intel-engineer.md`, and
  `docs/team-assignments.md`. This is the lowest-touch fix and matches the
  current code.
- **Option B — split `main.py` into routers.** Move investigation, screening,
  watchlist, and report routes out of `main.py` into
  `services/api/app/api/{investigations,screening,watchlist,reports}.py` using
  FastAPI `APIRouter`. This matches the doc claim but is a real refactor that
  needs its own `risk-logic-reviewer` pass.

Round-two recommendation: **Option A**. V1 is 209 lines of routes in
`main.py` and the indirection is not paying for itself.

### R2-C4 — `.env.example` lines 3-4 advertise a non-functional switch

```env
# Set DATABASE_URL to use PostgreSQL instead of in-memory storage
# DATABASE_URL=postgresql://user:password@localhost:5432/aml_tracing
```

Paired with R2-B1: once the factory branch is gone, these two comment lines
must also go. Otherwise the example file teaches an operator a switch the code
no longer supports.

### R2-C5 — `docs/acceptance-review.md` says "approved" while blockers stay open

The aggregate fix summary at the bottom of `docs/acceptance-review.md` reads
"✅ closed" across every agent. With R2-B1/B2/B3 outstanding, that line is
wrong. Either flip the overall verdict back to `approved-with-changes` and link
this round-two doc, or wait until the round-two waves close before re-declaring
`approved`.

## Per-subagent fix list (Karpathy §4 — Goal-Driven Execution)

Each subagent has at most one round-two task. Tasks are written as
**verifiable goals, not instructions**. The agent must:

1. Read the cited file/line.
2. Apply the minimal patch.
3. Show that the listed acceptance command exits zero.

### `aml-architect`

Round-two tasks (all contract-shape):

1. **R2-C1** — approve `report-engineer`'s removal of `ReportRequest.language`
   and record it in [`docs/contract-changelog.md`](contract-changelog.md).
2. **R2-C2** — remove the `pydantic.model_validator` unused import on
   `services/api/app/domain/models.py:7` (this is `models.py`, your file).
3. **R2-C3** — decide Option A vs Option B above; if A, delete
   `services/api/app/api/__init__.py` and the parent directory; if B, hand the
   refactor to a new dedicated wave. Update
   `.opencode/agents/aml-architect.md`,
   `.opencode/agents/risk-intel-engineer.md`, and
   `docs/team-assignments.md` to match the decision.
4. **R2-C5** — once R2-B1/B2/B3 close, re-baseline
   `docs/acceptance-review.md` to point at this document and re-declare
   `approved`.

Verification:

```bash
ruff check --select F401 services/api/app/domain/models.py
grep -rn 'services/api/app/api/' .opencode/agents docs   # must agree with code reality
```

### `db-storage-engineer`

Round-two task (R2-B1 + R2-C4):

- **R2-B1** — delete the `if database_url: … from app.storage.postgres import PostgresStore`
  branch from `services/api/app/storage/factory.py`. After the deletion the
  function reduces to:

  ```python
  def get_store() -> StorageAdapter:
      return InMemoryStore()
  ```

  Remove the now-unused `import importlib`, `import os`, `import warnings`, and
  the `_psycopg2_available` helper. If a future agent wants the swap path
  back, they will re-write the adapter first and then re-add the branch with a
  passing integration test.

- **R2-C4** — delete the two `DATABASE_URL` lines from `.env.example`. Update
  [`docs/database/swap-to-postgres.md`](database/swap-to-postgres.md) so the
  "Architecture (for future implementation)" section explicitly states the
  factory branch was also removed and lists "re-add the factory branch" as
  step 0 of the future PR.

Verification:

```bash
PYTHONPATH=.python-deps:services/api python3 -c "
import os; os.environ['DATABASE_URL']='postgresql://x:x@y/z'
from app.storage.factory import get_store
assert type(get_store()).__name__ == 'InMemoryStore'
print('ok')
"
grep -n 'DATABASE_URL' .env.example                       # must print nothing
PYTHONPATH=services/api python -m pytest -q services/api/app/tests
```

### `qa-devops-engineer`

Round-two task (R2-B2 + R2-C2 follow-up):

- **R2-B2** — empty both secret values in `.env.example`:

  ```env
  GOPLUS_TOKEN=
  DEEPSEEK_API_KEY=
  ```

  If either token was a real credential at any point in repo history, rotate
  it at the provider and document the rotation in
  [`docs/release-checklist.md`](release-checklist.md). Then run
  `git log -p -- .env.example | grep -E 'sk-|FacJJ'` and, if matches exist,
  use `git filter-repo` to scrub them before tagging V1.

- **R2-C2** — add this step to `.github/workflows/ci.yml` so the next ruff
  regression fails CI:

  ```yaml
  - name: Ruff (unused imports / unused vars)
    run: ruff check --select F401,F811,F841 services/api/app
  ```

  Add `ruff==0.6.9` (or the version already in your dev environment) to a new
  `services/api/requirements-dev.txt` and `pip install -r` it in CI. Do NOT add
  ruff to runtime requirements.

Verification:

```bash
grep -E '^(GOPLUS_TOKEN|DEEPSEEK_API_KEY)=' .env.example   # must show "=" only
ruff check --select F401,F811,F841 services/api/app        # must exit 0 AFTER per-owner fixes land
bash scripts/smoke.sh                                       # still green
```

### `web-workbench-engineer`

Round-two task (R2-B3):

- Replace the hard-coded footer on `apps/web/src/App.tsx:58-61` with a small
  hook that fetches `/health` once on mount, stores `demo_mode` in component
  state, and renders the footer only when it is `true`. Use `fetch` against
  `import.meta.env.VITE_API_BASE` (already wired) — no extra dep.

  Minimal shape:

  ```tsx
  const [demoMode, setDemoMode] = useState<boolean | null>(null);
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE}/health`)
      .then(r => r.json())
      .then(d => setDemoMode(Boolean(d.demo_mode)))
      .catch(() => setDemoMode(null));
  }, []);
  // …
  {demoMode === true && <p className="footer-note">Demo data — not real intelligence</p>}
  ```

  Do not add a "loading" or "live" footer — keep the surgical scope. If
  `demoMode` is `null` (fetch failed) we render nothing, which matches the
  existing "no claim made" stance.

Verification:

```bash
cd apps/web && npm run build                              # green
# Run boot-demo.sh with DEMO_MODE=true → footer renders.
# Run boot-demo.sh with DEMO_MODE=false → footer is absent.
```

### `report-engineer`

Round-two task (R2-C1 + R2-C2 test cleanup):

- **R2-C1** — remove `language: str = "en"` from `ReportRequest` in
  `services/api/app/domain/models.py:189`. Coordinate with `aml-architect` for
  the contract-changelog entry. The field has no caller in `services/` or
  `main.py`, so the change is contract-clean and test-clean.
- **R2-C2** — remove the unused `DEMO_HEADER` import from
  `services/api/app/tests/test_reporting.py:37`. The fixture uses
  `report_markdown` substring assertions so the import is dead.

Verification:

```bash
ruff check --select F401 services/api/app/domain/models.py services/api/app/tests/test_reporting.py
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_reporting.py
```

### `connector-engineer`

Round-two task (R2-C2):

- Fix `services/api/app/connectors/etherscan.py:200` — replace
  `except httpx.TimeoutException as exc:` with `except httpx.TimeoutException:`
  because the bound `exc` is never used inside the block. The matching
  `except httpx.HTTPError as exc:` on line 208 IS used (`f"HTTP error: {exc}"`),
  so leave that one alone.

Verification:

```bash
ruff check --select F841 services/api/app/connectors/etherscan.py
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_connectors.py
```

### `graph-pattern-engineer`

Round-two task (R2-C2):

- Remove the unused `field` import from
  `services/api/app/domain/graph_builder.py:4`. The file uses `@dataclass` but
  never `field(...)`.
- Remove the unused `pytest` import from
  `services/api/app/tests/test_patterns.py:11`. The file uses bare assertions,
  not pytest fixtures or markers.

Verification:

```bash
ruff check --select F401 services/api/app/domain/graph_builder.py services/api/app/tests/test_patterns.py
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_patterns.py
```

### `risk-intel-engineer`

Round-two task (R2-C2):

- Remove the unused `json` import from
  `services/api/app/tests/test_risk_intel.py:15`. The file uses `csv` and
  inline dict literals, never `json`.

Verification:

```bash
ruff check --select F401 services/api/app/tests/test_risk_intel.py
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_risk_intel.py
```

### `raindrop-ml-engineer`

Round-two task (R2-C2):

- Remove the unused `math` import from `services/api/app/ml/features.py:12`.
- Remove the unused `field` import from
  `services/api/app/ml/raindrop_scorer.py:13`.
- Remove the unused `RiskLevel` import from
  `services/api/app/tests/test_ml.py:21`.

Verification:

```bash
ruff check --select F401 services/api/app/ml services/api/app/tests/test_ml.py
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_ml.py
```

### `risk-logic-reviewer`

Round-two task:

- Run [`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
  on the merged diff once Waves A + B close. Specifically verify:
  1. `services/api/app/domain/scoring.py` still enforces direct-hit
     `hold_for_manual_review` — R2 fixes do not touch this file, but you must
     re-confirm because the test suite is the only thing protecting it.
  2. `services/api/app/services/reporting.py` still falls back to the local
     template on DeepSeek error.
  3. The frontend footer change in R2-B3 does not relabel real data as demo.
  4. Issue an `approved` or `approved-with-changes` verdict using the template
     in `cregis-pre-merge-review/SKILL.md § Verdict template`.

You modify no files. Your output is the verdict.

## Aggregate round-two fix table

| Owner | Blockers | §2/§3 cleanups | Acceptance command |
| ----- | -------- | -------------- | ------------------ |
| `aml-architect` | 0 | 4 (R2-C1 approval, R2-C2 on models.py, R2-C3, R2-C5) | grep + ruff check on `domain/models.py` |
| `risk-logic-reviewer` | 0 | re-audit after Waves A+B | `pre-merge-review` verdict template |
| `connector-engineer` | 0 | 1 (R2-C2 etherscan.py:200) | `ruff check --select F841 …/etherscan.py` |
| `graph-pattern-engineer` | 0 | 2 (R2-C2) | `ruff check --select F401 graph_builder.py test_patterns.py` |
| `risk-intel-engineer` | 0 | 1 (R2-C2) | `ruff check test_risk_intel.py` |
| `raindrop-ml-engineer` | 0 | 3 (R2-C2) | `ruff check ml/ test_ml.py` |
| `report-engineer` | 0 | 2 (R2-C1, R2-C2) | `ruff check models.py test_reporting.py` + pytest |
| `web-workbench-engineer` | 1 (R2-B3) | 0 | `npm run build`, manual demo-on/demo-off check |
| `qa-devops-engineer` | 1 (R2-B2) | 1 (R2-C2 CI step) | `grep` on `.env.example` + `ruff` step in `ci.yml` |
| `db-storage-engineer` | 1 (R2-B1) | 1 (R2-C4) | factory smoke + `grep DATABASE_URL .env.example` |

## Exit criteria for round two

All four must be true:

1. `ruff check --select F401,F811,F841 services/api/app` exits 0.
2. `grep -E '^(GOPLUS_TOKEN|DEEPSEEK_API_KEY|DATABASE_URL)=.+' .env.example`
   returns no lines (empty values only).
3. The factory smoke reproducer above prints `ok`, not `ModuleNotFoundError`.
4. The frontend footer is absent when `DEMO_MODE=false` and present when
   `DEMO_MODE=true`.

When all four hold, `aml-architect` flips
[`docs/acceptance-review.md`](acceptance-review.md) overall verdict back to
`approved`, links this file as round-two history, and tags V1.

## How this list was produced (audit trail)

The findings above are the output of running
[`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
on the current HEAD. Each finding cites a file:line that the project director
verified by reading, by running `ruff`, or by reproducing the failure on a
clean shell. There are no findings derived from grep heuristics alone.

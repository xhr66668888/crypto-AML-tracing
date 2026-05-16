# V1 Acceptance Review

**Reviewer:** project director
**Date:** 2026-05-16
**Branch reviewed:** `main` at HEAD as of this commit
**Quality bar:** [`skills/cregis-code-quality/SKILL.md`](../skills/cregis-code-quality/SKILL.md)
(project-customised port of
[`andrej-karpathy-skills/skills/karpathy-guidelines/SKILL.md`](../andrej-karpathy-skills/skills/karpathy-guidelines/SKILL.md))

## Overall verdict

**`approved-with-changes`** — V1 demo path works end-to-end and the compliance
core (direct-hit override, evidence-faithful reporting, deterministic patterns)
is sound. However, the codebase carries enough speculative and orphan code
that it fails the Karpathy §2 ("Simplicity First") acceptance gate. Before V1
is tagged, every subagent must close the round-one findings under their
section below. The release checklist in
[`docs/release-checklist.md`](release-checklist.md) has been updated with a
new gate (§11) that mirrors these findings.

A baseline measurement of repository size, for reference when judging the
fixes:

| Layer | LoC | Notes |
| --- | --- | --- |
| `services/api/app` (non-test) | 3,431 | 442 lines are speculative (`storage/postgres.py`) |
| `services/api/app/tests` | 3,396 | ≈ 99 % of non-test LoC — tests exist for code that has no production caller |
| `apps/web/src` | 1,175 | `App.tsx` has dead `connectionStatus` state |
| `apps/web/src/styles.css` | 1,352 | not reviewed line-by-line for this round |

## Reproducibility blockers found at acceptance

| # | File | Symptom | Severity |
| --- | --- | --- | --- |
| R1 | `services/api/requirements.txt:5` | `python-dotenv==1.2.2` does not exist on PyPI (max published is `1.2.1`). `pip install -r requirements.txt` fails on a clean machine. | **blocker** |
| R2 | `apps/web/package.json` | every dependency pinned to `"latest"`. Non-reproducible build. | **blocker** |
| R3 | `services/api/app/domain/models.py:3`, `services/reporting.py:20`, several tests | `from datetime import UTC` requires Python ≥ 3.11. README and `scripts/boot-demo.sh` do not state this assumption. Stock macOS Python 3.9 silently fails. | **blocker** |
| R4 | `services/api/requirements.txt` | no `python_requires` / no constraint comment for ≥ 3.11. | **blocker** (paired with R3) |

These are owned by `qa-devops-engineer` and `aml-architect` jointly — see
their sections below.

## Per-subagent findings

Each section begins with a one-line verdict, lists the round-one required
changes, and ends with the acceptance command that must be green before
re-review.

---

### aml-architect

**Verdict:** `approved-with-changes`

You are the contract owner; the V1 contract itself is clean, but several
**speculative contract surfaces** leaked in. Karpathy §2: every public method
should have a caller before it ships.

Required changes:

1. Prune `services/api/app/storage/base.py` so it contains only methods that
   `services/api/app/services/` or `app/main.py` actually call. Today the
   following abstract methods are dead from the API's perspective:
   `add_risk_source_hit`, `list_risk_source_hits`, `add_pattern_signal`,
   `list_pattern_signals`, `add_network_metric`, `list_network_metrics`,
   `add_ai_report`, `list_ai_reports`, `append_audit_log`, `list_audit_logs`,
   `add_screening_event`-companion `get_screening_event` (the GET endpoint is
   not wired in `main.py`). Either expose them via real endpoints, or delete
   them from both adapters and from `storage/base.py`. Document the decision
   in `docs/architecture/api-contract.md`.
2. Re-baseline the release checklist (already updated in this commit) so it
   includes the Karpathy acceptance gate (§11).
3. Approve `qa-devops-engineer`'s fix to `services/api/requirements.txt`
   (R1, R3, R4) and the matching `python_requires`/README block.
4. Approve `web-workbench-engineer`'s switch from `"latest"` to pinned
   versions in `apps/web/package.json` (R2).
5. Approve `db-storage-engineer`'s decision on `PostgresStore` (delete vs.
   feature-gate; see their section).

Acceptance command:

```bash
rg -n 'add_risk_source_hit|list_risk_source_hits|add_pattern_signal|add_network_metric|add_ai_report|append_audit_log|get_screening_event' \
   services/api/app/services services/api/app/main.py
# must be empty after the prune, OR must show real callers
```

---

### risk-logic-reviewer

**Verdict:** `approved`

The audit protocol you defined is exactly what V1 needs. No changes required
to your scope.

Round-two responsibilities:

1. Re-audit the direct-hit chain after `risk-intel-engineer` and
   `raindrop-ml-engineer` close their round-one items.
2. Re-audit `services/reporting.py` after `report-engineer` removes the
   `DeepSeekReporter` alias and unused params.
3. Verify
   [`skills/cregis-evidence-integrity/SKILL.md`](../skills/cregis-evidence-integrity/SKILL.md)
   matches the live invariants every time scoring changes.

Acceptance command:

```bash
PYTHONPATH=services/api python -m pytest -q \
  services/api/app/tests/test_risk_intel.py \
  services/api/app/tests/test_reporting.py
```

---

### connector-engineer

**Verdict:** `approved-with-changes`

The connector layer is the strongest in the repo: structured `ConnectorError`,
bounded retries, demo-mode determinism. Two items remain.

Required changes:

1. `services/api/app/connectors/etherscan.py:146-170,288-307` —
   `get_internal_transactions()` and `_demo_internal_transactions()` have no
   call sites in `services/` or `main.py`; they are only exercised by tests.
   Karpathy §2 violation. **Decide with `aml-architect`:** either add the call
   site in `GraphBuilder` (and verify it ships before V1), or delete the
   method and the matching demo fixture and tests.
2. `services/api/app/connectors/etherscan.py:234,236-241` — the local variable
   `exc` is captured in the `except httpx.HTTPError as exc:` block but its
   value goes into a string that is fine — no change. Listed for awareness
   only.

Acceptance command:

```bash
rg -n 'get_internal_transactions' services/api/app/services services/api/app/main.py services/api/app/domain
# must show callers after the fix, OR the method is gone
```

---

### graph-pattern-engineer

**Verdict:** `approved-with-changes`

Detector logic is correct, deterministic, and well-tested. Karpathy §2 and §3
violations only.

Required changes:

1. `services/api/app/domain/patterns.py:3` — `import math` is unused. Remove.
2. `services/api/app/domain/patterns.py:36,45,493,584-589` — `_build_adjacency`
   is called once in `analyze_graph`, the result is passed to
   `_centrality_hubs(graph, adj)`, and `_centrality_hubs` never reads `adj`.
   Five other helpers each rebuild adjacency internally. Either:
   - delete `_build_adjacency` and the unused parameter on `_centrality_hubs`,
     OR
   - thread the prebuilt `adj` into all five helpers so it is computed once.
   The reviewer prefers option A on Karpathy §2 grounds (single-use abstraction).
3. Re-run `PYTHONPATH=services/api pytest -q services/api/app/tests/test_patterns.py`
   after the prune. No test should change behaviour.

Acceptance command:

```bash
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_patterns.py
ruff check --select F401 services/api/app/domain/patterns.py
```

---

### risk-intel-engineer

**Verdict:** `approved-with-changes`

Direct-hit, source-hit, and watchlist semantics are correct. Two cleanups.

Required changes:

1. `services/api/app/domain/scoring.py:181-184` — collapse the redundant
   disposition branch. Both `if score >= 65 or any(...): return review` and
   `if score >= 35: return review` return the same value; replace with the
   single inclusive condition.
2. `services/api/app/domain/scoring.py:71-72` — delete the commented-out
   alternative formula `# final_risk_score = max(rule_score, raindrop_score)`.
   Karpathy §3: no commented-out alternatives. The live formula on line 74 is
   the contract; keep it.
3. `services/api/app/main.py:135-212` — the CSV and JSON branches of
   `import_watchlist` repeat ~30 lines almost verbatim. Extract one helper
   `_ingest_watchlist_row(row, defaults) -> WatchlistEntry` and reuse it.
   This is the only Karpathy §2 "could be half the lines" case the reviewer
   flagged in `main.py`.

Acceptance command:

```bash
PYTHONPATH=services/api python -m pytest -q \
  services/api/app/tests/test_risk_intel.py \
  services/api/app/tests/test_domain.py
```

---

### raindrop-ml-engineer

**Verdict:** `blocked`

This is the most serious round-one finding. There are **two** files claiming
to be `RaindropAmlScorer`:

- `services/api/app/ml/raindrop_scorer.py` — the live one, imported by
  `main.py`, `scoring.py`, and the tests. Returns `RaindropResult`.
- `services/api/app/ml/raindrop_aml.py` — duplicate. Returns `(score,
  features)` tuple. **Not imported anywhere in the repo.** It's dead.

This duplicate then spawned a `isinstance(raindrop_result, tuple)`
compatibility branch in `services/api/app/domain/scoring.py:66-70`, which is
also dead.

Required changes (blocking):

1. Delete `services/api/app/ml/raindrop_aml.py`.
2. Delete the `if isinstance(raindrop_result, tuple)` branch in
   `services/api/app/domain/scoring.py:66-70`. After deletion the live code
   reduces to:

   ```python
   raindrop_result = self.raindrop.predict(graph)
   raindrop_score = raindrop_result.score
   raindrop_features = raindrop_result.features
   ```

3. Confirm with `aml-architect` that the canonical frozen interface is
   `predict(graph) -> RaindropResult` (the `RaindropResult` dataclass in
   `raindrop_scorer.py`), and update
   [`docs/architecture.md`](architecture.md) and
   [`docs/contract-changelog.md`](contract-changelog.md) to match.
4. Update `.opencode/agents/raindrop-ml-engineer.md` to document the single
   canonical return type (already partially patched in this commit).

Acceptance command:

```bash
test ! -f services/api/app/ml/raindrop_aml.py && echo "deleted ok"
rg -n 'isinstance.*tuple' services/api/app/domain/scoring.py
# must print nothing
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_ml.py
```

---

### report-engineer

**Verdict:** `approved-with-changes`

Local fallback is evidence-faithful and the `DEMONSTRATION DATA` header is in
place. Two Karpathy §2 cleanups.

Required changes:

1. `services/api/app/services/reporting.py:225-237` — delete `DeepSeekReporter`.
   It is labelled "backward-compatible alias" in a V1 codebase that has never
   had a V0. There is no caller that requires backward compatibility — fix
   the single import in `services/api/app/main.py:29,56` to use
   `ReportGenerator` directly. (The `main.py` wiring will also need to pass a
   `DeepSeekClient`; coordinate with `connector-engineer` on construction.)
2. `services/api/app/services/reporting.py:58-63,234` — delete the `language`
   parameter. It is accepted and forwarded but never consumed. Same for
   `include_raw_context` if no caller actually flips it; today `main.py:120`
   forwards `payload.include_raw_context`, so `include_raw_context` may stay
   — `language` must go.
3. `services/api/app/services/reporting.py:91` —
   `except (ConnectorError, Exception) as exc:` is `except Exception as exc:`
   in disguise (since `ConnectorError` is an `Exception`). Decide: either
   only catch `ConnectorError`, or only catch `Exception`. Bare `Exception`
   is acceptable here because the fallback path is the safe one, but the
   tuple is misleading.

Acceptance command:

```bash
rg -n 'DeepSeekReporter|language' services/api/app/services/reporting.py services/api/app/main.py
PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_reporting.py
```

---

### web-workbench-engineer

**Verdict:** `blocked`

The workbench renders correctly in demo, but two acceptance blockers must be
fixed before V1.

Required changes (blocking):

1. `apps/web/package.json:11-24` — every dependency is pinned to `"latest"`.
   Replace each with the version `npm install` resolves today, e.g.

   ```json
   "react": "^18.3.1",
   "react-dom": "^18.3.1",
   "vite": "^5.4.10",
   ...
   ```

   Commit the resulting `package-lock.json`. This is finding **R2**.
2. `apps/web/src/App.tsx:11-14,68-77` — `connectionStatus` state is created
   but `setConnectionStatus` is never called. `ConnectionIndicator` therefore
   always returns `null`. Decide with `aml-architect`:
   - **Option A (simpler, preferred by Karpathy §2):** delete the state, the
     setter, and the `ConnectionIndicator` component entirely.
   - **Option B:** wire it to poll `/health` on mount and on a 30 s interval,
     and document the new behaviour.

Acceptance command:

```bash
rg -n '"latest"' apps/web/package.json
# must print nothing
cd apps/web && npm run build
```

---

### qa-devops-engineer

**Verdict:** `blocked`

The boot script and CI workflow exist but they do not catch the
reproducibility blockers a clean machine hits.

Required changes (blocking):

1. `services/api/requirements.txt:5` — change `python-dotenv==1.2.2` to a
   version that exists on PyPI (`1.1.1` is the last stable that works on
   Python 3.11, `1.2.1` is the latest). This is finding **R1**.
2. `services/api/requirements.txt` (top of file) — add a comment header that
   states `# requires Python >= 3.11`. Confirm with `aml-architect`.
3. `README.md` — add a "Requirements" section that states
   "Python 3.11 or newer" before the "Run Locally" block. Make
   `scripts/boot-demo.sh` exit non-zero with a friendly error message when
   `python3 --version` is < 3.11. This is finding **R3**.
4. `.github/workflows/ci.yml` — pin `python-version: '3.11'` (or `'3.12'`) so
   CI reproduces the supported runtime. Add a step that runs
   `python -m pip install --dry-run -r services/api/requirements.txt` as the
   first job so a bad pin fails fast.
5. After **R2** is fixed by `web-workbench-engineer`, add a step
   `git diff --exit-code apps/web/package-lock.json` so the lockfile cannot
   drift silently.

Acceptance command:

```bash
python3 -c "import sys; assert sys.version_info >= (3, 11), sys.version"
python3 -m pip install --dry-run -r services/api/requirements.txt
bash scripts/boot-demo.sh   # must succeed end-to-end
```

---

### db-storage-engineer

**Verdict:** `blocked`

The schema is reasonable and the in-memory adapter works. The PostgreSQL
adapter is the largest single Karpathy §2 violation in the repo.

Required changes (blocking):

1. `services/api/app/storage/postgres.py` (442 lines) — choose one:
   - **Option A — delete.** Keep the SQL schema in
     `docs/database/schema.sql` as the contract. When V1 actually needs
     persistence, write the adapter then.
   - **Option B — gate behind `DATABASE_URL` and prove it works.** Add an
     integration test under `services/api/app/tests/` (skipped by default,
     enabled when `DATABASE_URL` is set) that boots against a real Postgres
     container from `docker-compose.yml`, runs `schema.sql`, and round-trips
     an investigation, a screening event, and a watchlist entry. Fix the
     `TODO`s on lines 213, 222-223. Remove the `NotImplementedError`.
   - **The reviewer recommends Option A** because no caller exists today and
     V1 ships in-memory.
2. `services/api/app/storage/base.py` — once `aml-architect` prunes the dead
   abstract methods (see their section), regenerate this file to match.
3. `services/api/app/storage/memory.py` — same prune as `base.py`. Today the
   adapter implements ~150 lines of methods (`add_risk_source_hit`,
   `add_pattern_signal`, …) that no service calls.

Acceptance command:

```bash
# Option A:
test ! -f services/api/app/storage/postgres.py && \
  PYTHONPATH=services/api python -m pytest -q

# Option B:
DATABASE_URL=postgresql://aml:aml@localhost:5432/aml \
  PYTHONPATH=services/api python -m pytest -q services/api/app/tests
```

---

## Aggregate fix summary

| Owner | Blockers | Required changes | Acceptance command |
| --- | --- | --- | --- |
| `aml-architect` | 0 | 5 (R1–R4 approvals + prune speculative `StorageAdapter`) | `rg` check on storage callers |
| `risk-logic-reviewer` | 0 | re-audit round-two only | pytest |
| `connector-engineer` | 0 | 1 (decide on `get_internal_transactions`) | rg + pytest |
| `graph-pattern-engineer` | 0 | 2 (`import math`, `_build_adjacency`) | pytest + ruff |
| `risk-intel-engineer` | 0 | 3 (collapse disposition, delete comment, dedupe watchlist) | pytest |
| `raindrop-ml-engineer` | **1** | 4 (delete duplicate, delete isinstance branch, docs, agent md) | pytest + rg |
| `report-engineer` | 0 | 3 (`DeepSeekReporter`, `language=`, except-tuple) | pytest + rg |
| `web-workbench-engineer` | **1** | 2 (pin deps, fix dead `connectionStatus`) | npm run build + rg |
| `qa-devops-engineer` | **1** | 5 (dotenv pin, py 3.11 docs, boot check, CI matrix, lockfile guard) | boot-demo.sh |
| `db-storage-engineer` | **1** | 3 (decide on PostgresStore, prune base.py, prune memory.py) | pytest |

Once every "blocker" row above is closed, `aml-architect` re-runs the full
[`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
procedure on the merged diff. Only then is V1 tagged.

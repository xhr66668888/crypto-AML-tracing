# One-shot prompt — round-one acceptance fixes

Paste the block between the `<<<` markers as a single message into the
OpenCode chat box. The `build` primary agent will dispatch every subagent
through the Task tool in one turn, organised into four dependency waves so
shared files (`scoring.py`, `main.py`, `storage/base.py`) don't collide.

The prompt assumes the audit findings in
[`docs/acceptance-review.md`](../docs/acceptance-review.md) and the skills
under [`skills/`](../skills/) are already on `main`. If your branch is
behind, rebase first.

---

<<<
You are the Build primary agent for Cregis ETH AML Tracing. Your single job in
this turn is to close the round-one acceptance-review findings the project
director filed on 2026-05-16. Every subagent has its own section, its own
required changes, and its own acceptance command. Your job is to dispatch
them in the correct waves so shared files don't collide.

Read first (these are the contract for this turn):
- AGENTS.md
- docs/acceptance-review.md
- docs/team-assignments.md
- docs/release-checklist.md  (§11 Karpathy Acceptance Gate)
- skills/cregis-code-quality/SKILL.md
- skills/cregis-pre-merge-review/SKILL.md
- skills/cregis-evidence-integrity/SKILL.md

Every subagent you dispatch MUST, before editing anything:
1. Read skills/cregis-code-quality/SKILL.md.
2. Read its own section in docs/acceptance-review.md (anchor links are at the
   bottom of that file).
3. If it touches scoring, patterns, direct-hit, or report content, also read
   skills/cregis-evidence-integrity/SKILL.md.
4. After making changes, run skills/cregis-pre-merge-review/SKILL.md on its
   own diff and report a structured verdict using that skill's template.

Hard invariants (enforced by every wave):
- Every changed line traces to a numbered item in docs/acceptance-review.md.
- No subagent edits a file outside its owned paths in docs/team-assignments.md
  unless this prompt explicitly pre-approves it below.
- Direct-hit categories still force hold_for_manual_review.
- RaindropAmlScorer.predict(graph) -> RaindropResult remains the only public
  surface; the duplicate raindrop_aml.py adapter is being deleted, not added.
- raindrop_score stays advisory; max(rule_score, raindrop_score) stays.
- Demo data still labelled as demo; "DEMONSTRATION DATA" header still present
  in demo-mode reports.

Pre-approved cross-boundary edits (aml-architect grants these for this turn,
to avoid a Wave 0 round-trip):
- report-engineer may edit services/api/app/main.py:29 and :56 to swap
  DeepSeekReporter for ReportGenerator(deepseek=DeepSeekClient(...), demo_mode=settings.demo_mode).
- risk-intel-engineer may edit services/api/app/main.py:135-212 to extract a
  single _ingest_watchlist_row helper that both the CSV and JSON branches call.
- qa-devops-engineer may edit README.md to add the "Requirements" section and
  may edit scripts/boot-demo.sh to fail fast on Python < 3.11.
- db-storage-engineer may edit services/api/app/storage/base.py and
  services/api/app/storage/memory.py to delete the abstract methods that
  Wave A confirms are unused (the list is in docs/acceptance-review.md
  § aml-architect, item 1).

Now dispatch the four waves in order. Use the Task tool to fan out parallel
agents inside a wave; wait for the wave to return before kicking off the
next one.

────────────────────────────────────────────────────────────────────
Wave A — decisions and contracts (serial; runs alone first)
────────────────────────────────────────────────────────────────────

@aml-architect : you are the only Wave A agent.

Tasks (each maps to docs/acceptance-review.md § aml-architect):
  1. Confirm the prune list for services/api/app/storage/base.py. The
     candidate methods are the ones with no caller in services/ or main.py:
       add_risk_source_hit, list_risk_source_hits,
       add_pattern_signal, list_pattern_signals,
       add_network_metric, list_network_metrics,
       add_ai_report, list_ai_reports,
       append_audit_log, list_audit_logs,
       get_screening_event.
     Either approve the prune (preferred per Karpathy §2) or document a real
     endpoint that will land in this same release for each method you keep.
     Write the decision into docs/architecture/api-contract.md.
  2. Approve qa-devops-engineer's planned fix: requirements.txt switches
     python-dotenv to 1.2.1, with a "# requires Python >= 3.11" header.
  3. Approve web-workbench-engineer's planned fix: every "latest" in
     apps/web/package.json becomes the version npm install resolves today,
     and apps/web/package-lock.json is committed.
  4. Approve db-storage-engineer's recommendation on PostgresStore. Default:
     delete services/api/app/storage/postgres.py. Document the choice in
     docs/database/swap-to-postgres.md and remove the blocking banner there
     iff Option B (integration-tested) is chosen.

Acceptance:
  - rg -n 'add_risk_source_hit|list_risk_source_hits|add_pattern_signal|list_pattern_signals|add_network_metric|list_network_metrics|add_ai_report|list_ai_reports|append_audit_log|list_audit_logs|get_screening_event' services/api/app/services services/api/app/main.py
    must be empty OR show a real caller for every method you decided to keep.
  - Your reply lists: prune list (final), 4 approvals (final), PostgresStore
    decision (A or B), and the exact line numbers Wave B/C agents will edit.

────────────────────────────────────────────────────────────────────
Wave B — independent fixes (parallel; no shared files inside the wave)
────────────────────────────────────────────────────────────────────

Dispatch all four in parallel with the Task tool.

@connector-engineer
  File: services/api/app/connectors/etherscan.py (+ tests/test_connectors.py)
  Tasks (docs/acceptance-review.md § connector-engineer):
    1. Decide with the Wave A output: either add the production call site for
       get_internal_transactions() inside GraphBuilder (and verify it ships
       in this PR), or delete the method, _demo_internal_transactions, and
       the test cases that exercise them. Default: delete.
  Acceptance:
    rg -n 'get_internal_transactions' services/api/app/services services/api/app/main.py services/api/app/domain
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_connectors.py
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

@graph-pattern-engineer
  File: services/api/app/domain/patterns.py
  Tasks (docs/acceptance-review.md § graph-pattern-engineer):
    1. Delete the unused `import math` on line 3.
    2. Delete _build_adjacency (line 584-589) and the unused `adj` parameter
       on _centrality_hubs (line 493). Update the call site in analyze_graph
       (line 45) to call _centrality_hubs(graph) directly. Do not thread
       a prebuilt adjacency into the other helpers (Karpathy §2 — single-use
       abstraction).
  Acceptance:
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_patterns.py
    ruff check --select F401,F811,F841 services/api/app/domain/patterns.py
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

@web-workbench-engineer
  Files: apps/web/package.json, apps/web/package-lock.json, apps/web/src/App.tsx
  Tasks (docs/acceptance-review.md § web-workbench-engineer):
    1. Replace every "latest" in apps/web/package.json with the version
       `npm install` resolves today. Commit the resulting package-lock.json.
       This closes R2 (blocker).
    2. Delete the dead connectionStatus state and the ConnectionIndicator
       component from apps/web/src/App.tsx (Option A in the audit — Karpathy
       §2 preferred). Do not add health-polling unless aml-architect
       explicitly asks for it.
  Acceptance:
    rg -n '"latest"' apps/web/package.json   # must print nothing
    cd apps/web && npm install && npm run build
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

@qa-devops-engineer
  Files: services/api/requirements.txt, README.md, scripts/boot-demo.sh,
         .github/workflows/ci.yml
  Tasks (docs/acceptance-review.md § qa-devops-engineer):
    1. R1 — change python-dotenv==1.2.2 to python-dotenv==1.2.1.
    2. R4 — add a `# requires Python >= 3.11` header to requirements.txt.
    3. R3 — add a "Requirements" section to README.md stating Python 3.11+
       and Node 18+. Update scripts/boot-demo.sh so it exits non-zero with
       a friendly error when `python3 -c 'import sys; assert sys.version_info
       >= (3,11)'` fails.
    4. Pin .github/workflows/ci.yml `python-version: '3.11'` and add a job
       step that runs `python -m pip install --dry-run -r services/api/requirements.txt`
       as the first action.
    5. After web-workbench-engineer commits package-lock.json, add a CI step:
       `git diff --exit-code apps/web/package-lock.json`.
  Acceptance:
    python3 -c "import sys; assert sys.version_info >= (3,11), sys.version"
    python3 -m pip install --dry-run -r services/api/requirements.txt
    bash scripts/boot-demo.sh
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

────────────────────────────────────────────────────────────────────
Wave C — shared-file fixes (serial inside the wave; ordered to avoid
                            merge conflicts on scoring.py and main.py)
────────────────────────────────────────────────────────────────────

C.1  @raindrop-ml-engineer   (must run before risk-intel-engineer)
  Files: services/api/app/ml/raindrop_aml.py, services/api/app/domain/scoring.py,
         docs/architecture.md, docs/contract-changelog.md,
         .opencode/agents/raindrop-ml-engineer.md
  Tasks (docs/acceptance-review.md § raindrop-ml-engineer — BLOCKER):
    1. Delete services/api/app/ml/raindrop_aml.py.
    2. Delete the `if isinstance(raindrop_result, tuple)` branch in
       services/api/app/domain/scoring.py:66-70. After the deletion the live
       code is:
         raindrop_result = self.raindrop.predict(graph)
         raindrop_score = raindrop_result.score
         raindrop_features = raindrop_result.features
    3. Update docs/architecture.md and docs/contract-changelog.md so the
       canonical contract is documented as
       `predict(graph) -> RaindropResult`.
  Acceptance:
    test ! -f services/api/app/ml/raindrop_aml.py
    rg -n 'isinstance.*tuple' services/api/app/domain/scoring.py   # empty
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_ml.py services/api/app/tests/test_domain.py
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

C.2  @risk-intel-engineer   (after C.1 lands; same scoring.py file)
  Files: services/api/app/domain/scoring.py, services/api/app/main.py
  Tasks (docs/acceptance-review.md § risk-intel-engineer):
    1. Collapse the redundant disposition branch in
       services/api/app/domain/scoring.py:181-184 into a single inclusive
       condition (both branches currently return `RiskDisposition.review`).
    2. Delete the commented-out alternative formula at
       services/api/app/domain/scoring.py:71-72 (Karpathy §3 — no
       commented-out alternatives).
    3. In services/api/app/main.py:135-212, extract a single
       `_ingest_watchlist_row(row, defaults) -> WatchlistEntry` helper and
       use it from both the CSV and JSON branches of import_watchlist.
  Acceptance:
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_risk_intel.py services/api/app/tests/test_domain.py
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

C.3  @report-engineer   (parallel with C.2 — different files except main.py;
                          coordinate with C.2 on main.py:29,56 lines vs
                          main.py:135-212 lines)
  Files: services/api/app/services/reporting.py, services/api/app/main.py
  Tasks (docs/acceptance-review.md § report-engineer):
    1. Delete the DeepSeekReporter alias at
       services/api/app/services/reporting.py:225-237.
    2. Update services/api/app/main.py:29 to import ReportGenerator instead
       of DeepSeekReporter, and main.py:56 to construct
       `ReportGenerator(deepseek=DeepSeekClient(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, model=settings.deepseek_model), demo_mode=settings.demo_mode)`.
    3. Delete the unused `language` parameter at
       services/api/app/services/reporting.py:58, :63, and any forwarder.
       Keep include_raw_context — main.py:120 actually uses it.
    4. Change `except (ConnectorError, Exception) as exc:` at
       services/api/app/services/reporting.py:91 to `except Exception as exc:`
       (the tuple was misleading; ConnectorError IS Exception).
  Acceptance:
    rg -n 'DeepSeekReporter|^\s*language\s*[:=]' services/api/app/services/reporting.py services/api/app/main.py
    # must print nothing
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests/test_reporting.py
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

C.4  @db-storage-engineer   (after Wave A decision lands)
  Files: services/api/app/storage/postgres.py, services/api/app/storage/base.py,
         services/api/app/storage/memory.py, docs/database/swap-to-postgres.md
  Tasks (docs/acceptance-review.md § db-storage-engineer — BLOCKER):
    1. Execute the PostgresStore decision from Wave A:
       - Option A (default): delete services/api/app/storage/postgres.py.
         Remove its tests if any. Remove the blocking banner from
         docs/database/swap-to-postgres.md and rewrite the doc as a
         forward-looking design note rather than a how-to.
       - Option B: keep the file, gate it behind DATABASE_URL, add an
         integration test that boots a real Postgres container and
         round-trips an investigation, a screening event, and a watchlist
         entry. Remove the NotImplementedError and the TODOs.
    2. Apply the StorageAdapter prune list Wave A confirmed:
       - Delete the matching abstract methods from
         services/api/app/storage/base.py.
       - Delete the matching concrete methods from
         services/api/app/storage/memory.py.
       - Delete the unused `RiskLevel` import at base.py:17.
  Acceptance:
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests
  Then run skills/cregis-pre-merge-review/SKILL.md on your own diff.

────────────────────────────────────────────────────────────────────
Wave D — audit and sign-off (after C returns)
────────────────────────────────────────────────────────────────────

D.1  @risk-logic-reviewer   (read-only; never edits)
  Re-audit, in order:
    - services/api/app/domain/scoring.py            (C.1 + C.2 changes)
    - services/api/app/services/reporting.py        (C.3 changes)
    - services/api/app/domain/risk_intel.py          (unchanged, but
                                                      confirm no regression)
    - services/api/app/domain/patterns.py            (Wave B graph-pattern)
  Run:
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests
  Return a single verdict using the template in
  skills/cregis-pre-merge-review/SKILL.md. Cite file:line for every finding.

D.2  @aml-architect   (final pre-merge gate)
  Run skills/cregis-pre-merge-review/SKILL.md against the merged branch.
  Cross-check every item in docs/release-checklist.md §11 is now checkable.
  Update docs/acceptance-review.md to flip each closed item to "closed"
  with a commit SHA. Update docs/known-limitations.md to delete the C1–C13
  rows for items that are now closed.

  Verdict accepted only if all three of these exit zero:
    PYTHONPATH=services/api python -m pytest -q services/api/app/tests
    cd apps/web && npm run build
    bash scripts/smoke.sh

────────────────────────────────────────────────────────────────────
Final summary you (build) must produce
────────────────────────────────────────────────────────────────────

When every wave has returned, write a single summary message containing:
  1. The pruned StorageAdapter method list aml-architect approved.
  2. The PostgresStore decision (A or B) and where the rationale lives.
  3. For each of the 8 execution agents: green/red on its acceptance
     command and a one-line description of what changed.
  4. The risk-logic-reviewer verdict, verbatim.
  5. The aml-architect final verdict and the three green/red lines from
     pytest, npm run build, and smoke.sh.
  6. A diff stat: files changed, insertions, deletions. Most of the
     deltas should be deletions — this is a Karpathy §2 cleanup.
>>>

## What to expect

After you paste the block above:

1. `build` will stream its plan and emit a Task call for `aml-architect`.
2. Wave A finishes; `build` then emits four parallel Task calls for Wave B.
3. Wave B returns; `build` runs Wave C in order (C.1 → C.2 / C.3 in parallel
   → C.4).
4. Wave D returns; `build` writes the final summary.

If any wave returns a `blocked` verdict, `build` will stop and surface the
exact file:line that blocked it — fix the upstream item, then re-paste
**only** the block for the affected wave (e.g. just Wave C.1) to retry.

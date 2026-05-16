# OpenCode subagents — Cregis ETH AML Tracing

This folder defines the 10 [OpenCode](https://opencode.ai/docs/agents) subagents that deliver the workbench. Each `*.md` in `agents/` is a self-contained subagent definition — the filename (without `.md`) is the agent name.

## Layout

```
.opencode/
├── README.md
└── agents/
    ├── aml-architect.md           # principal architect & release commander  (brain)
    ├── risk-logic-reviewer.md     # read-only compliance / risk auditor      (brain)
    ├── connector-engineer.md      # Etherscan / GoPlus / DeepSeek HTTP
    ├── db-storage-engineer.md     # schema, storage adapter, migrations
    ├── graph-pattern-engineer.md  # graph builder + deterministic AML patterns
    ├── qa-devops-engineer.md      # CI, smoke tests, docker-compose, .env shape
    ├── raindrop-ml-engineer.md    # Raindrop AML scorer / ML port
    ├── report-engineer.md         # English investigation report (DeepSeek + fallback)
    ├── risk-intel-engineer.md     # watchlist, source hits, direct-hit, rule score
    └── web-workbench-engineer.md  # React/Vite analyst workbench (apps/web)
```

Model strategy — split between brain and execution roles. Only the two brain agents are pinned in [`opencode.json`](../opencode.json); the other eight inherit your OpenCode default model:

| Role         | Agents                                                                                                                                       | Model                                                       |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Brain        | `aml-architect`, `risk-logic-reviewer`                                                                                                       | `opencode/gpt-5.5-codex`, `reasoningEffort: "high"`         |
| Execution    | `connector-engineer`, `graph-pattern-engineer`, `risk-intel-engineer`, `raindrop-ml-engineer`, `report-engineer`, `web-workbench-engineer`, `qa-devops-engineer`, `db-storage-engineer` | inherits your OpenCode default (e.g. `mimo-v2.5-pro`)       |

`opencode.json` only overrides the two brain agents:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "aml-architect":       { "model": "opencode/gpt-5.5-codex", "reasoningEffort": "high", "textVerbosity": "low" },
    "risk-logic-reviewer": { "model": "opencode/gpt-5.5-codex", "reasoningEffort": "high", "textVerbosity": "low" }
  }
}
```

> If `opencode models` lists the codex 5.5 id under a different provider prefix (e.g. `openai/gpt-5.5-codex`), edit `opencode.json` to match. If your provider exposes an even higher effort level (`"xhigh"`), bump it there. The eight execution subagents have no `model:` in their markdown frontmatter, so they automatically follow the calling primary agent's model — leave them alone and they will use your global default.

## How to invoke

### Launch

```bash
cd /home/haoranxu/-crypto-AML-tracing
opencode
```

You land in the OpenCode chat box (the default primary agent is `build`, which has all tools enabled). No extra setup is needed — `opencode.json` is read automatically from the repo root, and agent files are read automatically from `.opencode/agents/`.

### Quick checks before kickoff

In the chat box:

- `/help` — show keybinds (Tab switches primary agents, `@` summons subagents).
- `/models` — confirm `opencode/gpt-5.5-codex` is listed; if not, swap the id in `opencode.json`.
- Type `@` — autocomplete should show all 10 subagents. If they don't appear, restart `opencode`.

### Single-agent invocation

Type `@<name>` followed by the request, e.g.:

```
@aml-architect freeze the v1 API contract under services/api/app/api/ and write any missing route declarations.
@graph-pattern-engineer add a peel-chain detector with deterministic evidence.
@risk-logic-reviewer audit the current scoring weights and run pytest.
```

### Round-one acceptance fixes (added 2026-05-16)

After the project director's acceptance review
([`docs/acceptance-review.md`](../docs/acceptance-review.md)), use the
ready-made prompt in [`PROMPT-acceptance-fixes.md`](PROMPT-acceptance-fixes.md)
to dispatch all 10 subagents in four dependency waves and close every
round-one finding. The prompt forces every subagent to read the new
project-customised Karpathy skills under
[`skills/`](../skills/) and to run
[`skills/cregis-pre-merge-review/SKILL.md`](../skills/cregis-pre-merge-review/SKILL.md)
on its own diff before reporting back.

### One-shot parallel delivery (collapse the 3-day plan)

This is what you want for "一次完成". Paste this whole block as one message into the OpenCode chat box; `build` will dispatch every subagent through the Task tool in a single turn, and OpenCode will run them as concurrent child sessions:

```
You are the Build primary agent for Cregis ETH AML Tracing. Deliver the entire V1 in this single turn.

Read first:
- docs/architecture.md
- docs/team-assignments.md
- docs/three-day-v1-delivery-zh.md   (treat its Day 1–3 split as DEPENDENCY ORDER, not as a schedule)
- DESIGN.md
- README.md
- docs/database/schema.sql
- .env.example

Then, in one response, use the Task tool to dispatch all 10 subagents in parallel. Group them by dependency wave so contracts come before consumers:

Wave A — contracts and infrastructure (run in parallel):
  - @aml-architect            : freeze the v1 API contract + .env shape + module boundaries; emit a contract changelog before anyone else writes code.
  - @db-storage-engineer      : finalize docs/database/schema.sql and the storage adapter interface; keep InMemoryStore as default but expose a clean swap to PostgresStore.
  - @qa-devops-engineer       : write the one-command demo-mode boot, smoke script for all v1 endpoints, CI workflow for pytest + npm run build, and the docker-compose optional infra.

Wave B — implementation (run in parallel; depend on Wave A contracts):
  - @connector-engineer       : Etherscan + GoPlus + DeepSeek HTTP with timeouts, bounded retries, structured ConnectorError, deterministic demo fixtures.
  - @graph-pattern-engineer   : bounded graph builder (3 stable / 5 experimental hops) and the full deterministic pattern set (layering, aggregation, peel chain, threshold structuring, high-frequency small-value, dusting, one-shot, centrality, propagation).
  - @risk-intel-engineer      : risk_intel.py, rule scoring side of scoring.py, CSV/JSON watchlist import, OFAC/PEP/sanctions/stablecoin-blacklist direct-hit force-HOLD.
  - @raindrop-ml-engineer     : RaindropAmlScorer adapter with stable predict(graph) contract, feature builder, CPU-only inference, advisory raindrop_score.
  - @report-engineer          : evidence-faithful English report; DeepSeek path when DEEPSEEK_API_KEY is set, otherwise local fallback; explicit demo-mode header.
  - @web-workbench-engineer   : Wise design tokens (DESIGN.md), screening + investigation panels, Cytoscape graph with loading/error/empty/loaded states, OPPO Sans, responsive at 1440 / 1180 / 390.

Wave C — gate (after Waves A+B return):
  - @risk-logic-reviewer      : read-only audit of patterns.py, scoring.py, risk_intel.py, reporting.py. Run PYTHONPATH=services/api pytest -q services/api/app/tests. Return approved / approved-with-changes / blocked with exact file + line patches.
  - @aml-architect            : final pre-release sign-off, release checklist, known-limitations list.

Hard invariants (enforced by every wave):
1. Every risk conclusion must point to a source_hit, pattern_signal, or evidence row. No invented facts in reports.
2. Direct-hit categories (OFAC, sanctions, PEP, Circle/Tether/stablecoin blacklist, critical local watchlist) FORCE hold_for_manual_review regardless of behavioural score.
3. raindrop_score is advisory; it never overrides source-backed evidence.
4. RaindropAmlScorer.predict(graph) signature is frozen unless aml-architect approves a change.
5. Demo data is always labelled demo in API responses and reports.
6. Acceptance commands that must be green before any agent claims done:
     PYTHONPATH=services/api pytest -q services/api/app/tests
     cd apps/web && npm run build
     scripts/smoke.sh   (or the equivalent qa-devops-engineer ships)

When every subagent reports back, summarize: what shipped, what each agent owns, the green/red status of the three acceptance commands, and the known-limitations list authored by aml-architect.
```

After you send that single message, OpenCode will:

1. Build streams its own thinking and emits 10 `task` tool calls — visible as child sessions in the right-hand session tree.
2. Each subagent runs in its own child session with its own permission posture from the markdown frontmatter (which is why `risk-logic-reviewer` will refuse to edit and `web-workbench-engineer` is sandboxed to `apps/web/**`).
3. Navigate the child sessions with the default keybinds: `Shift+Down` to enter the first child, `Right`/`Left` to cycle, `Shift+Up` to return to the parent. (See [Agents docs § Usage](https://opencode.ai/docs/agents#usage).)
4. When a child session asks for permission (e.g. `npm install`, `psql`, `docker compose`), approve it once and OpenCode remembers it for that session.
5. When all child sessions return, Build will produce the final summary you asked for.

## What changed vs the previous Cursor setup

| Before (Cursor)                                  | Now (OpenCode)                                                  |
| ------------------------------------------------ | --------------------------------------------------------------- |
| `.cursor/agents/*.md` with `name:` field         | `.opencode/agents/*.md`; filename is the agent name             |
| `model: claude-opus-4-7[]` / `mimo-v2.5-pro`     | Brain agents → `opencode/gpt-5.5-codex` + `reasoningEffort: high` in `opencode.json`; execution agents → inherit OpenCode default (still `mimo-v2.5-pro` for you) |
| `is_background: true`                            | dropped — OpenCode spawns child sessions automatically          |
| `readonly: true`                                 | `permission: { edit: deny, bash: <strict allowlist> }`          |
| Slash-command invocation `/aml-architect`        | `@aml-architect` from the chat box, or Task-tool dispatch       |
| Project-scoped skill files under `.cursor/skills/` | Removed — skill content has been folded into each agent's `Goals` / `Acceptance` sections |

## Permission posture (full access — Codex-style)

`opencode.json` sets `"permission": "allow"` globally, which is the documented stable equivalent of YOLO mode (since v1.1.1). Every tool call — `edit`, `write`, `bash`, `webfetch`, `task`, etc. — runs without prompting. None of the agent markdown files declare per-agent permission overrides anymore, so nothing reins this in.

Two safeties OpenCode still enforces regardless of `"permission": "allow"`:

- `.env` files default to `deny` for reads (only `.env.example` is allowed). If an agent legitimately needs to read `.env`, add to `opencode.json`:
  ```json
  "permission": { "read": { "*.env": "allow" }, "*": "allow" }
  ```
- `doom_loop` detection (3 identical tool calls in a row) still prompts. That's a runaway-loop guard, not a confirmation prompt — leave it on.

If your installed OpenCode is recent enough to support the newer YOLO CLI (`opencode --yolo`, `opencode yolo status`), you can swap `"permission": "allow"` for `"yolo": true` for a slightly more aggressive posture that also short-circuits the doom-loop guard. The CLI flags only exist in versions after the YOLO PRs landed (#9073, #11833, #14583) — if `opencode --yolo` prints the help screen instead of starting, your version doesn't have it yet and `"permission": "allow"` is the correct config to use.

## Pinning a different model per agent (optional)

`opencode.json` accepts per-agent overrides. If you ever want to bump the brain agents to a higher reasoning tier (only if your provider exposes it):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "aml-architect":       { "model": "opencode/gpt-5.5-codex", "reasoningEffort": "xhigh" },
    "risk-logic-reviewer": { "model": "opencode/gpt-5.5-codex", "reasoningEffort": "xhigh" }
  }
}
```

Or, if you ever want one specific execution agent on a beefier model:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "graph-pattern-engineer": { "model": "opencode/gpt-5.5-codex", "reasoningEffort": "high" }
  }
}
```

Unspecified agents fall back to the OpenCode global default (`mimo-v2.5-pro` in your setup). The markdown agent files don't need to be touched.

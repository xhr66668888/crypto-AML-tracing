# Cregis ETH AML Tracing

Local-first Ethereum AML risk operations workbench for Cregis.

The V1 workbench has two entrypoints:

- Real-time ETH/USDT/USDC screening for inbound/outbound transfers before funds are released.
- Deep investigation for an Ethereum address or transaction hash, with transaction graph evidence, deterministic AML pattern signals, source-backed risk hits, rule and Raindrop-inspired scores, and an English investigation report.

## Current Implementation

- `services/api`: FastAPI backend with demo-mode Etherscan/GoPlus connectors, transfer screening, graph builder, pattern analysis, source-hit risk intelligence, rule risk engine, Raindrop AML scoring boundary, DeepSeek reporting adapter, and tests.
- `apps/web`: React/Vite workbench with pre-withdrawal screening, investigation input, Cytoscape graph, risk evidence, pattern/source-hit panels, node details, Raindrop features, and report preview.
- `docs`: architecture, team ownership, database schema, and Raindrop migration notes.

## Requirements

- **Python 3.11 or newer** (uses `from datetime import UTC` and other 3.11+ features)
- **Node 18+** (for the Vite frontend)

## Run Locally

**One command** (recommended):

```bash
bash scripts/boot-demo.sh
```

This copies `.env.example` to `.env`, installs dependencies, starts the FastAPI backend on port 8000, installs frontend deps, and starts the Vite dev server on port 5173.

**Manual setup:**

```bash
cp .env.example .env

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/api/requirements.txt
PYTHONPATH=services/api uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If `python3-venv` is unavailable on the machine, use the local dependency target used during implementation:

```bash
python3 -m pip install --target .python-deps -r services/api/requirements.txt
PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another shell:

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`.

## Smoke Tests

Run the V1 endpoint smoke tests against a running API:

```bash
bash scripts/smoke.sh
```

Tests: `/health`, screening, investigation CRUD, graph, risk, reports, watchlist import, and direct-hit `hold_for_manual_review` verification.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on push/PR to `main`:
- `PYTHONPATH=services/api pytest -q services/api/app/tests`
- `cd apps/web && npm run build`
- Smoke tests against a live API instance

## Optional Infrastructure

```bash
docker compose up -d postgres redis
```

Or run the full stack:

```bash
docker compose up -d
```

The current API keeps investigations and screening events in memory so the
application remains easy to run locally. Watchlist rows persist to
`WATCHLIST_DATA_PATH` (`.data/watchlist.json` by default). The PostgreSQL schema
in `docs/database/schema.sql` defines the later persistence target for screening
events, source hits, pattern signals, network metrics, investigations, and audit
logs.

## API Keys

Demo mode is enabled by default. To call real providers, set `DEMO_MODE=false` and configure:

- `ETHERSCAN_API_KEY`
- `ETHEREUM_RPC_URL` for Ethereum JSON-RPC. The default is Alchemy's public
  mainnet endpoint; for production use an Alchemy private endpoint such as
  `https://eth-mainnet.g.alchemy.com/v2/<api-key>`.
- `GOPLUS_TOKEN`
- `DEEPSEEK_API_KEY`

Keep `.env` local; it is ignored by git.

## Project Skills and Ownership

Project contributors should use the live skill index in
[`docs/agent-skills.md`](docs/agent-skills.md) before editing code or docs.
It points to the required quality, pre-merge, and evidence-integrity skills.

Ownership is still role-based:

- `aml-architect` — API contracts, schema, `.env`, module boundaries, release.
- `risk-logic-reviewer` — read-only audit for scoring, patterns, direct-hit,
  and reports.
- `connector-engineer`, `graph-pattern-engineer`, `risk-intel-engineer`,
  `raindrop-ml-engineer`, `report-engineer`, `web-workbench-engineer`,
  `qa-devops-engineer`, `db-storage-engineer` — implementation ownership.

Detailed roles, owned paths, and deliverables live in
[`docs/team-assignments.md`](docs/team-assignments.md).

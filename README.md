# Cregis ETH AML Tracing

Local-first Ethereum AML risk operations workbench for Cregis.

The V1 workbench has two entrypoints:

- Real-time ETH/USDT/USDC screening for inbound/outbound transfers before funds are released.
- Deep investigation for an Ethereum address or transaction hash, with transaction graph evidence, deterministic AML pattern signals, source-backed risk hits, rule and Raindrop-inspired scores, and an English investigation report.

## Current Implementation

- `services/api`: FastAPI backend with demo-mode Etherscan/GoPlus connectors, transfer screening, graph builder, pattern analysis, source-hit risk intelligence, rule risk engine, Raindrop AML scoring boundary, DeepSeek reporting adapter, and tests.
- `apps/web`: React/Vite workbench with pre-withdrawal screening, investigation input, Cytoscape graph, risk evidence, pattern/source-hit panels, node details, Raindrop features, and report preview.
- `docs`: architecture, team ownership, database schema, and Raindrop migration notes.

## Run Locally

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

## Optional Infrastructure

```bash
docker compose up -d postgres redis
```

The current API uses an in-memory store so the application remains easy to run locally. The PostgreSQL schema in `docs/database/schema.sql` defines the persistence target for screening events, source hits, pattern signals, network metrics, investigations, and audit logs.

## API Keys

Demo mode is enabled by default. To call real providers, set `DEMO_MODE=false` and configure:

- `ETHERSCAN_API_KEY`
- `GOPLUS_TOKEN`
- `DEEPSEEK_API_KEY`

Keep `.env` local; it is ignored by git.

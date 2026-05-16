# Deploy & Run Guide

## Requirements

- **Python 3.11 or newer.** The codebase uses `from datetime import UTC`
  (added in Python 3.11). On stock macOS Python 3.9 the import fails before
  the app starts. Until finding **R3** in
  [`docs/acceptance-review.md`](acceptance-review.md) is closed,
  `scripts/boot-demo.sh` may not detect this for you.
- **Node 18 or newer** (LTS). Required by Vite 5.

## Local Development

### Quick Start (One Command)

```bash
bash scripts/boot-demo.sh
```

This will:
1. Copy `.env.example` to `.env` if needed
2. Install Python dependencies
3. Start the FastAPI backend on port 8000
4. Install frontend npm dependencies
5. Start the Vite dev server on port 5173
6. Wait for health check and print URLs

### Manual Setup

#### Backend

```bash
cp .env.example .env

# Option A: virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt
PYTHONPATH=services/api uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option B: local deps (no venv)
python3 -m pip install --target .python-deps -r services/api/requirements.txt
PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Option C: script
infra/scripts/run_api.sh
```

#### Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`.

### Smoke Tests

```bash
bash scripts/smoke.sh
```

Tests all V1 endpoints against `http://localhost:8000`. Pass a custom URL as argument:

```bash
bash scripts/smoke.sh http://staging.example.com:8000
```

## Demo Mode vs Production Mode

### Demo Mode (Default)

- `DEMO_MODE=true` in `.env`
- No API keys required
- Etherscan and GoPlus connectors return deterministic demo data
- DeepSeek reporter falls back to local template
- All features work without external dependencies

### Production Mode

1. Set `DEMO_MODE=false` in `.env`
2. Configure API keys:

```env
DEMO_MODE=false
ETHERSCAN_API_KEY=your_etherscan_key
GOPLUS_TOKEN=your_goplus_token
DEEPSEEK_API_KEY=your_deepseek_key
```

3. Restart the backend

## Provider Key Configuration

| Variable | Purpose | Required for Production |
|---|---|---|
| `ETHERSCAN_API_KEY` | Ethereum transaction data | Yes |
| `GOPLUS_TOKEN` | Address risk intelligence | Yes |
| `DEEPSEEK_API_KEY` | AI report generation | Optional (local fallback) |
| `DEEPSEEK_MODEL` | DeepSeek model name | No (default: deepseek-v4-pro) |
| `DEEPSEEK_BASE_URL` | DeepSeek API base URL | No |
| `CHAIN_ID` | Ethereum chain ID | No (default: 1 = mainnet) |

### Timeout Configuration

| Variable | Default | Description |
|---|---|---|
| `ETHERSCAN_TIMEOUT_SECONDS` | 10 | Etherscan request timeout |
| `GOPLUS_TIMEOUT_SECONDS` | 10 | GoPlus request timeout |
| `DEEPSEEK_TIMEOUT_SECONDS` | 30 | DeepSeek request timeout |
| `CONNECTOR_MAX_RETRIES` | 2 | Max retries for connectors |

## Docker Compose

### Optional Infrastructure Only

```bash
docker compose up -d postgres redis
```

Starts PostgreSQL (port 5432) and Redis (port 6379). The API still uses in-memory storage until `db-storage-engineer` flips the adapter.

### Full Stack

```bash
# Copy env first
cp .env.example .env

# Build and start everything
docker compose up -d
```

Services:
- `postgres`: PostgreSQL 16 on port 5432
- `redis`: Redis 7 on port 6379
- `api`: FastAPI backend on port 8000
- `web`: Nginx-served frontend on port 5173

### Stopping

```bash
docker compose down           # stop all
docker compose down -v        # stop all and remove volumes
```

## CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR to `main`:

1. **api** job: `PYTHONPATH=services/api pytest -q services/api/app/tests`
2. **web** job: `cd apps/web && npm run build`
3. **smoke** job: starts API, runs `scripts/smoke.sh`

All three must pass for CI to be green.

## Running Tests Locally

### Backend Tests

```bash
PYTHONPATH=services/api pytest -q services/api/app/tests
```

### Frontend Build

```bash
cd apps/web && npm run build
```

### Smoke Tests

```bash
# Start API first
PYTHONPATH=services/api uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Run smoke
bash scripts/smoke.sh
```

## Troubleshooting

### API won't start

- Check Python version: `python3 --version` (needs **3.11+** — `from datetime import UTC` is Python 3.11).
- Check dependencies: `pip install -r services/api/requirements.txt`. If pip
  refuses to install `python-dotenv`, you are hitting acceptance finding
  **R1**; replace the version in `services/api/requirements.txt` with a
  PyPI-published one (`1.1.1` or `1.2.1`) and retry.
- Check port: `lsof -i :8000` — kill conflicting processes

### Frontend build fails

- Check Node version: `node --version` (needs 18+)
- Clear cache: `cd apps/web && rm -rf node_modules && npm install`
- Check TypeScript: `cd apps/web && npx tsc --noEmit`

### Smoke tests fail

- Ensure API is running: `curl http://localhost:8000/health`
- Check demo mode: response should show `"demo_mode": true`
- Check logs for errors

### Docker compose issues

- Check Docker version: `docker --version` (needs 20+)
- Check compose: `docker compose version`
- Rebuild: `docker compose build --no-cache`
- Check logs: `docker compose logs api`

### Provider keys not working

- Verify `.env` has correct values (no quotes needed)
- Restart API after changing `.env`
- Check `DEMO_MODE=false` is set
- Test with: `curl http://localhost:8000/health` — should show `"demo_mode": false`

### PostgreSQL connection issues

- PostgreSQL is optional; API defaults to in-memory.
- Check container: `docker compose ps postgres`
- Check health: `docker compose exec postgres pg_isready`
- Connection string: `postgresql://cregis:cregis_dev@localhost:5432/cregis_aml`
- The `PostgresStore` adapter is round-one **blocked** (acceptance finding
  C6) — setting `DATABASE_URL` today will raise `NotImplementedError` on
  some read paths. See
  [`docs/acceptance-review.md § db-storage-engineer`](acceptance-review.md#db-storage-engineer).

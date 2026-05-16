#!/usr/bin/env bash
# boot-demo.sh — One-command demo-mode boot for Cregis ETH AML Tracing
# Usage: bash scripts/boot-demo.sh
#
# Starts the FastAPI backend and Vite frontend in demo mode.
# No API keys required; demo data is generated deterministically.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ── 1. Environment ──────────────────────────────────────────────────
if [ ! -f .env ]; then
  echo "[boot] Copying .env.example -> .env"
  cp .env.example .env
else
  echo "[boot] .env already exists, skipping copy"
fi

# ── 2. Python dependencies ──────────────────────────────────────────
echo "[boot] Installing Python dependencies..."
if [ -d ".venv" ]; then
  echo "[boot] Found .venv, using pip install"
  .venv/bin/pip install -q -r services/api/requirements.txt 2>/dev/null \
    || python3 -m pip install -q -r services/api/requirements.txt
else
  echo "[boot] No .venv found, using --target .python-deps"
  python3 -m pip install --target .python-deps -q -r services/api/requirements.txt
fi

# ── 3. Start FastAPI backend ────────────────────────────────────────
echo "[boot] Starting FastAPI backend on http://0.0.0.0:8000 ..."
if [ -d ".venv" ]; then
  PYTHONPATH=services/api .venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 --reload &
else
  PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 &
fi
API_PID=$!
echo "[boot] API PID: $API_PID"

# ── 4. Frontend dependencies ────────────────────────────────────────
echo "[boot] Installing frontend dependencies..."
(cd apps/web && npm install --silent)

# ── 5. Start Vite dev server ────────────────────────────────────────
echo "[boot] Starting Vite dev server on http://0.0.0.0:5173 ..."
(cd apps/web && npm run dev) &
WEB_PID=$!
echo "[boot] Web PID: $WEB_PID"

# ── 6. Wait for API health ──────────────────────────────────────────
echo "[boot] Waiting for API health check..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Cregis ETH AML Tracing — Demo Mode"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://localhost:8000"
    echo "  Health:    http://localhost:8000/health"
    echo "  API docs:  http://localhost:8000/docs"
    echo ""
    echo "  Press Ctrl+C to stop all services."
    echo "═══════════════════════════════════════════════════════════"
    wait
    exit 0
  fi
  printf "."
  sleep 1
done

echo ""
echo "[boot] ERROR: API did not become healthy within 30 seconds."
kill $API_PID $WEB_PID 2>/dev/null || true
exit 1

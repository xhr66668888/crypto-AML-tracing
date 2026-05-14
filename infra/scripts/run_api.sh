#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ ! -d ".python-deps" ]; then
  python3 -m pip install --target .python-deps -r services/api/requirements.txt
fi

PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

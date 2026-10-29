#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python scripts/bootstrap.py
.venv/bin/python -m pip install -r backend/requirements.txt
(cd frontend && npm ci --no-fund --no-audit && npm run build)
printf '%s\n' 'Open http://localhost:8000. Sign in with a token from .local-keys.txt.'
exec .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

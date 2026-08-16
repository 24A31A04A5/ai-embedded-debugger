#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Checking local development configuration..."
echo

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and set DATABASE_URL to your Neon PostgreSQL URL." >&2
  exit 1
fi

if ! grep -Eq '^[[:space:]]*DATABASE_URL[[:space:]]*=[[:space:]]*.+' .env; then
  echo "ERROR: DATABASE_URL is not set in .env. Add your Neon PostgreSQL connection string." >&2
  exit 1
fi

echo "Configuration looks ready."
echo
echo "Next steps:"
echo "  1. pip install -e \".[dev]\""
echo "  2. alembic -c db/alembic.ini upgrade head"
echo "  3. uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000"

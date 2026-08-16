#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Starting local infrastructure (PostgreSQL 16 + MinIO)..."
docker compose up -d

echo ""
echo "Waiting for PostgreSQL..."
until docker compose exec -T postgres pg_isready -U aed -d aed >/dev/null 2>&1; do
  sleep 1
done

echo "Local infrastructure is ready."
echo "  PostgreSQL: localhost:5432"
echo "  MinIO API:  http://localhost:9000"
echo "  MinIO UI:   http://localhost:9001"

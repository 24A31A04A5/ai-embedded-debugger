# Benchmark Development Environment Setup Guide

## Overview

This guide sets up an **isolated development environment** for running the 6-request benchmark smoke test without touching production resources.

---

## 1. Prerequisites

### Windows (PowerShell)

```powershell
# Install Docker Desktop from https://www.docker.com/products/docker-desktop/
# Ensure WSL 2 backend is enabled in Docker Desktop settings

# Verify installation
docker --version
docker compose version
```

### Linux/macOS

```bash
# Install Docker Engine and Docker Compose
# https://docs.docker.com/engine/install/

# Verify installation
docker --version
docker compose version
```

---

## 2. Start Isolated pgvector Database

```powershell
# From the project root (C:\Users\DELL\OneDrive\Desktop\ai-embedded-debugger\ai-embedded-debugger\ai-embedded-debugger)
docker compose -f docker-compose.benchmark.yml up -d

# Verify container is healthy
docker compose -f docker-compose.benchmark.yml ps
```

**Expected output:**
```
NAME                IMAGE                  STATUS
pgvector-benchmark  pgvector/pgvector:pg16  Up (healthy)
```

**Port mapping:** PostgreSQL listens on **localhost:5433** (not 5432) to avoid conflicts.

---

## 3. Verify pgvector Installation

```powershell
# Test connection with psql
docker exec -it pgvector-benchmark psql -U benchmark -d aed_benchmark -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Expected output:
#  extname | extowner | extnamespace | extrelocatable | extversion | extconfig | extcondition
# ---------+----------+--------------+----------------+------------+-----------+-------------
#  vector  |       10 |         2200 | t              | 0.7.0      |           |
```

---

## 4. Apply Schema Migrations

```powershell
# Set environment variables for the migration
$env:DATABASE_URL = "postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark"

# Run migrations from project root
alembic -c db/alembic.ini upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial_users_projects, ...
INFO  [alembic.runtime.migration] Running upgrade 001_initial_users_projects -> 003_add_project_files, ...
...
```

---

## 5. Configure Environment Variables

Create `.env.benchmark.local` from the template:

```powershell
# Copy template
Copy-Item .env.benchmark .env.benchmark.local

# Edit with your values (NEVER commit this file)
notepad .env.benchmark.local
```

**Required values:**
```ini
# DATABASE (SQLAlchemy format with +psycopg)
DATABASE_URL=postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark

# AI Provider - REQUIRED
GEMINI_API_KEY=your_gemini_api_key_here

# Clerk (optional for benchmark - auth is mocked in dev)
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=

# App config
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=storage_data_benchmark
```

---

## 6. Connection String Formats

| Tool | Format | Example |
|------|--------|---------|
| **SQLAlchemy (psycopg)** | `postgresql+psycopg://user:pass@host:port/db` | `postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark` |
| **psql (libpq)** | `postgresql://user:pass@host:port/db` | `postgresql://benchmark:benchmark@localhost:5433/aed_benchmark` |
| **asyncpg** | `postgresql+asyncpg://user:pass@host:port/db` | `postgresql+asyncpg://benchmark:benchmark@localhost:5433/aed_benchmark` |

**Important:** The benchmark runner uses **SQLAlchemy format** (`+psycopg`). psql uses the libpq format without the driver prefix.

---

## 6. Seed Technical Documents (Optional)

For the two selected cases, the benchmark only needs the documents that would be retrieved during RAG. The cases are:

1. **dev_01_missing_semicolon** — Compiler error (no document retrieval needed)
2. **dev_15_uart_baudrate_mismatch** — Serial log analysis (no document retrieval needed)

For full_pipeline testing with RAG, you can upload sample datasheets:

```powershell
# Using the API (after starting the API server)
# POST /v1/projects/{project_id}/documents with PDF files
```

For the smoke test, **no documents are required** — the mock responses for full_pipeline already handle the RAG flow.

---

## 7. Verify Embeddings & Retrieval

```powershell
# Start the API server locally (optional - for manual testing)
$env:DATABASE_URL = "postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark"
$env:GEMINI_API_KEY = "your_key"
$env:CLERK_SECRET_KEY = "dev-key"
$env:APP_ENV = "development"

uvicorn app.main:app --app-dir apps/api --reload --port 8000

# In another terminal, test retrieval
curl -X POST http://localhost:8000/v1/projects/{project_id}/debug \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -d '{"firmware_code": "void setup() { pinMode(2, OUTPUT); }", "user_question": "Test"}'
```

---

## 7. Run Benchmark Smoke Test

### Dry-run (verify configuration without API calls)

```powershell
$env:DATABASE_URL = "postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark"
$env:GEMINI_API_KEY = "your_gemini_key"
$env:CLERK_SECRET_KEY = "dev-key"
$env:APP_ENV = "development"

python tests/evaluation/benchmark_runner.py `
  --split dev `
  --repeat 1 `
  --approaches plain_gemini prompt_only full_pipeline `
  --case-ids dev_01_missing_semicolon dev_15_uart_baudrate_mismatch `
  --dry-run
```

**Expected dry-run output:**
```
[PASS] database_isolation: Database isolation verified (local/test/dev database with pgvector)
[PASS] api_keys: API keys present
[PASS] storage_isolation: Storage isolation verified (local or test bucket)
[PASS] environment_mode: Environment mode: development
[PASS] migrations_blocked: Migrations configuration appears safe
Filtered to 2 case(s): dev_01_missing_semicolon, dev_15_uart_baudrate_mismatch
Running benchmark with approaches: ['plain_gemini', 'prompt_only', 'full_pipeline']
Repeat runs: 1
Mock mode: False

=== DRY-RUN: REQUEST BUDGET ===
Cases: 2 (dev_01_missing_semicolon, dev_15_uart_baudrate_mismatch)
Approaches: 3 (plain_gemini, prompt_only, full_pipeline)
Repeats: 1
Generation requests: 6
Embedding requests (full_pipeline): 2
Estimated total (with ~10% retries): 8

Environment checks:
  [PASS] database_isolation: Database isolation verified (local/test/dev database with pgvector)
  [PASS] api_keys: API keys present
  [PASS] storage_isolation: Storage isolation verified (local or test bucket)
  [PASS] environment_mode: Environment mode: development
  [PASS] migrations_blocked: Migrations configuration appears safe

Dry-run complete. No API calls made.
```

### Run Actual Smoke Test

```powershell
python tests/evaluation/benchmark_runner.py `
  --split dev `
  --repeat 1 `
  --approaches plain_gemini prompt_only full_pipeline `
  --case-ids dev_01_missing_semicolon dev_15_uart_baudrate_mismatch `
  --output tests/evaluation/benchmark_results_smoke_test.json
```

**Expected output:**
```
[PASS] database_isolation: Database isolation verified (local/test/dev database with pgvector)
[PASS] api_keys: API keys present
[PASS] storage_isolation: Storage isolation verified (local or test bucket)
[PASS] environment_mode: Environment mode: development
[PASS] migrations_blocked: Migrations configuration appears safe
Filtered to 2 case(s): dev_01_missing_semicolon, dev_15_uart_baudrate_mismatch
Running benchmark with approaches: ['plain_gemini', 'prompt_only', 'full_pipeline']
Repeat runs: 1
Mock mode: False
Output: tests/evaluation/benchmark_results_smoke_test.json
  [dev_01_missing_semicolon] plain_gemini run 1/1: correct (XXXms)
  [dev_01_missing_semicolon] prompt_only run 1/1: correct (XXXms)
  [dev_01_missing_semicolon] full_pipeline run 1/1: correct (XXXms)
  [dev_15_uart_baudrate_mismatch] plain_gemini run 1/1: correct (XXXms)
  [dev_15_uart_baudrate_mismatch] prompt_only run 1/1: correct (XXXms)
  [dev_15_uart_baudrate_mismatch] full_pipeline run 1/1: correct (XXXms)

========================================================================================================================
BENCHMARK RESULTS - TECHNICAL SCORING
========================================================================================================================
Metric                    | Plain Gemini | Prompt Only | Full Pipeline
------------------------------------------------------------------------
Total Cases               | 2            | 2           | 2           
Successful Cases          | 2            | 2           | 2           
API Success Rate          | 100.0%       | 100.0%      | 100.0%       
Root Cause Accuracy       | XX.X%        | XX.X%       | XX.X%        
Fix Accuracy              | XX.X%        | XX.X%       | XX.X%        
Citation Relevance        | XX.X%        | XX.X%       | XX.X%        
Valid Relevant Citations  | X.XX         | X.XX        | X.XX         
...
```

---

## 8. Verify Results

```powershell
# Check results file
Get-Content tests/evaluation/benchmark_results_smoke_test.json | ConvertFrom-Json

# Verify key fields:
# - metadata.use_mock == false
# - metadata.dev_mode == true
# - aggregates.*.successful_cases == 2
# - aggregates.*.api_success_rate == 1.0
# - raw_results contain citation_validation with actual retrieved chunks
```

---

## 9. Cleanup

```powershell
# Stop and remove benchmark database (removes all data)
docker compose -f docker-compose.benchmark.yml down -v

# Or keep for future runs:
docker compose -f docker-compose.benchmark.yml down
```

---

## Quick Reference: Environment Variables

| Variable | Development Value | Purpose |
|----------|-------------------|---------|
| `DATABASE_URL` | `postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark` | SQLAlchemy connection (required) |
| `GEMINI_API_KEY` | *your key* | Required for real benchmark |
| `CLERK_SECRET_KEY` | `dev-key` or real dev key | Auth (mocked in dev) |
| `APP_ENV` | `development` | Enables dev mode |
| `STORAGE_BACKEND` | `local` | Local file storage |
| `LOCAL_STORAGE_PATH` | `storage_data_benchmark` | Isolated storage |
| `RUN_DATABASE_INTEGRATION_TESTS` | `1` | Enables DB tests |

---

## Security Checklist

- [ ] `.env.benchmark.local` is in `.gitignore`
- [ ] No production credentials in benchmark files
- [ ] Benchmark database is separate from production Neon
- [ ] pgvector container only exposes port 5433 locally
- [ ] Secrets stored in `.env.benchmark.local` (ignored by git)
- [ ] No production Clerk credentials used

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `docker: command not found` | Install Docker Desktop, restart terminal |
| `port 5433 already in use` | Change port in `docker-compose.benchmark.yml` |
| `pgvector extension not found` | Use `pgvector/pgvector:pg16` image |
| `alembic: command not found` | `pip install -e ".[dev]"` |
| `GEMINI_API_KEY not set` | Set in `.env.benchmark.local` |
| `database_isolation FAIL` | Check `DATABASE_URL` format and pgvector indicator |

---

## Verification Commands Summary

```powershell
# 1. Start database
docker compose -f docker-compose.benchmark.yml up -d

# 2. Verify pgvector
docker exec pgvector-benchmark psql -U benchmark -d aed_benchmark -c "SELECT * FROM pg_extension WHERE extname='vector';"

# 3. Run migrations
$env:DATABASE_URL = "postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark"
alembic -c db/alembic.ini upgrade head

# 4. Dry-run smoke test
$env:DATABASE_URL = "postgresql+psycopg://benchmark:benchmark@localhost:5433/aed_benchmark"
$env:GEMINI_API_KEY = "your_key"
$env:CLERK_SECRET_KEY = "dev-key"
python tests/evaluation/benchmark_runner.py --split dev --repeat 1 --approaches plain_gemini prompt_only full_pipeline --case-ids dev_01_missing_semicolon dev_15_uart_baudrate_mismatch --dry-run

# 5. Run smoke test
python tests/evaluation/benchmark_runner.py --split dev --repeat 1 --approaches plain_gemini prompt_only full_pipeline --case-ids dev_01_missing_semicolon dev_15_uart_baudrate_mismatch --output tests/evaluation/benchmark_results_smoke_test.json
```
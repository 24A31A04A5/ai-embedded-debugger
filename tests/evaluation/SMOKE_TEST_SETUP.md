# Smoke Test Setup Guide

## Prerequisites

### 1. Isolated PostgreSQL Database with pgvector

Create a dedicated Neon project for benchmarking (or local PostgreSQL):

```bash
# Option A: Neon (recommended)
# 1. Go to https://console.neon.tech
# 2. Create new project: "ai-embedded-debugger-benchmark"
# 3. Enable pgvector extension in SQL editor:
#    CREATE EXTENSION IF NOT EXISTS vector;
# 4. Copy connection string

# Option B: Local PostgreSQL with pgvector
# docker run -d \
#   --name pgvector-benchmark \
#   -e POSTGRES_DB=aed_benchmark \
#   -e POSTGRES_USER=benchmark \
#   -e POSTGRES_PASSWORD=benchmark \
#   -p 5432:5432 \
#   pgvector/pgvector:pg16
```

### 2. Configure Environment Variables

Create a `.env.benchmark` file (never commit this):

```bash
# Required for real benchmark execution
DATABASE_URL=postgresql+psycopg://benchmark:benchmark@localhost:5432/aed_benchmark
GEMINI_API_KEY=your_gemini_api_key_here
CLERK_SECRET_KEY=your_clerk_secret_key_here
APP_ENV=development
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=storage_data_benchmark

# Optional: Override defaults
# EMBEDDING_PROVIDER=gemini
# EMBEDDING_MODEL=gemini-embedding-001
```

### 3. Verify Database Setup

```bash
# Test connection and pgvector
python -c "
import os
os.environ['DATABASE_URL'] = 'postgresql+psycopg://benchmark:benchmark@localhost:5432/aed_benchmark'
from app.core.database import probe_database
print('DB reachable:', probe_database())
"

# Verify pgvector extension
psql "postgresql://benchmark:benchmark@localhost:5432/aed_benchmark" -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### 4. Run Migrations (if needed)

```bash
# Only if database is empty
alembic -c db/alembic.ini upgrade head
```

## Smoke Test Command

### 6-Request Smoke Test (2 cases × 3 approaches)

```bash
# Set environment
export DATABASE_URL="postgresql+psycopg://benchmark:benchmark@localhost:5432/aed_benchmark"
export GEMINI_API_KEY="your_key_here"
export CLERK_SECRET_KEY="your_key_here"
export APP_ENV=development

# Run smoke test (2 cases × 3 approaches = 6 requests + embeddings)
python tests/evaluation/benchmark_runner.py \
  --split dev \
  --repeat 1 \
  --approaches plain_gemini prompt_only full_pipeline \
  --output tests/evaluation/benchmark_results_smoke_test.json \
  --no-enforce-isolation  # Only if using test DB that passes checks
```

**Expected API Usage:**
- 6 generation requests (2 cases × 3 approaches)
- ~6 embedding requests (for full_pipeline RAG retrieval)
- ~12-18 total API calls with retries
- Estimated cost: <$0.01

### Expected Output

```
[PASS] database_isolation: Database isolation verified (local/test/dev database with pgvector)
[PASS] api_keys: API keys present
[PASS] storage_isolation: Storage isolation verified (local or test bucket)
[PASS] environment_mode: Environment mode: development
[PASS] migrations_blocked: Migrations configuration appears safe
Loaded 18 dev cases
Running benchmark with approaches: ['plain_gemini', 'prompt_only', 'full_pipeline']
Repeat runs: 1
Mock mode: False
Output: tests/evaluation/benchmark_results_smoke_test.json
  [dev_01_missing_semicolon] plain_gemini run 1/1: correct/incorrect (XXXms)
  [dev_01_missing_semicolon] prompt_only run 1/1: correct/incorrect (XXXms)
  [dev_01_missing_semicolon] full_pipeline run 1/1: correct/incorrect (XXXms)
  [dev_15_uart_baudrate_mismatch] plain_gemini run 1/1: correct/incorrect (XXXms)
  [dev_15_uart_baudrate_mismatch] prompt_only run 1/1: correct/incorrect (XXXms)
  [dev_15_uart_baudrate_mismatch] full_pipeline run 1/1: correct/incorrect (XXXms)

========================================================================================================================
BENCHMARK RESULTS - TECHNICAL SCORING
========================================================================================================================
Metric                    | Plain Gemini | Prompt Only | Full Pipeline
------------------------------------------------------------------------
Total Cases               | 2            | 2           | 2           
Successful Cases          | 2            | 2           | 2           
API Success Rate          | 100.0%       | 100.0%      | 100.0%       
Root Cause Accuracy       | XX.X%        | XX.X%       | XX.X%        
...
```

## Validation Requirements

Before homepage display:

1. ✅ All 6 requests successful (api_success_rate = 100%)
2. ✅ Results file exists: `benchmark_results_smoke_test.json`
3. ✅ Metadata includes `use_mock: false` and `dev_mode: true`
4. ✅ `successful_cases == 2` for each approach
5. ✅ Raw results contain citation validation with actual retrieved chunks
6. ✅ No ERROR status in any run

## Homepage Display Gate

The homepage will only show real results if:
- File `benchmark_results_dev_real.json` exists
- Contains `use_mock: false`
- `successful_cases > 0` for at least one approach
- `api_success_rate > 0`

Otherwise shows "Benchmark Evaluation Pending" notice.

## Full Test Commands

```bash
# 1. Mock regression test (CI-safe)
python tests/evaluation/benchmark_runner.py --split dev --mock --repeat 1

# 2. Smoke test (6 requests)
python tests/evaluation/benchmark_runner.py --split dev --repeat 1 \
  --approaches plain_gemini prompt_only full_pipeline \
  --output tests/evaluation/benchmark_results_smoke_test.json

# 3. Full dev evaluation (54 requests)
python tests/evaluation/benchmark_runner.py --split dev --repeat 1

# 4. Full dev with repeats (162 requests)
python tests/evaluation/benchmark_runner.py --split dev --repeat 3

# 5. Holdout (requires approval)
python tests/evaluation/benchmark_runner.py --split holdout --repeat 1 --approve-holdout
```

## Safety Checklist

- [ ] Separate Neon project for benchmarking (not production)
- [ ] pgvector extension enabled
- [ ] GEMINI_API_KEY set in environment (not in code)
- [ ] CLERK_SECRET_KEY set in environment
- [ ] DATABASE_URL points to benchmark database
- [ ] Migrations applied to benchmark database
- [ ] Mock results saved to `*_mock.json` (never displayed as real)
- [ ] Real results saved to `*_real.json` or `*_smoke_test.json`
- [ ] Homepage shows "Evaluation Pending" until valid real results exist
# FastAPI Backend

Python API for the AI Embedded Debugging Platform.

Phase 0 Step 2 provides the FastAPI application skeleton, health endpoint, database connectivity, and automated tests. Product features (auth, projects CRUD, AI) are added in later phases.

## Prerequisites

- Python 3.12+ (3.14 may work locally; CI uses 3.12)
- A [Neon](https://neon.tech) PostgreSQL project (free tier is sufficient)
- `.env` file at repository root (copy from `.env.example`)

Docker is **not** required for local development.

## Local Setup

### 1. Create a Neon database

1. Sign up at [https://neon.tech](https://neon.tech)
2. Create a project and database (PostgreSQL 16)
3. Copy the connection string from the Neon dashboard
4. Convert it to the psycopg driver form if needed:

```text
postgresql+psycopg://USER:PASSWORD@ep-xxx.region.aws.neon.tech/DBNAME?sslmode=require
```

Neon requires SSL. Append `?sslmode=require` if it is not already in the URL.

### 2. Configure environment

From the **repository root**:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your Neon connection string.

### 3. Install Python dependencies

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### 4. Apply database migrations

```powershell
alembic -c db/alembic.ini upgrade head
```

## Run the API

From the **repository root** with the virtual environment activated:

```powershell
uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000
```

Verify:

- Health: [http://127.0.0.1:8000/v1/health](http://127.0.0.1:8000/v1/health)
- OpenAPI schema: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Example health response

When the API and Neon PostgreSQL are both reachable:

```json
{
  "status": "ok",
  "service": "ai-embedded-debugger-api",
  "version": "0.1.0",
  "checks": {
    "database": {
      "status": "ok",
      "reachable": true
    }
  }
}
```

When the API is running but PostgreSQL is unreachable, `status` is `"degraded"` and `checks.database.reachable` is `false`. Connection attempts fail fast using `DATABASE_CONNECT_TIMEOUT` (default: 5 seconds).

## Lint, Typecheck, and Tests

### Default test run (no live database required)

Unit tests mock database probes and use a dummy `DATABASE_URL`:

```powershell
ruff check apps/api
ruff format --check apps/api
mypy apps/api
pytest apps/api/tests -v
```

### Optional live database integration test

To verify connectivity against your Neon database:

```powershell
$env:RUN_DATABASE_INTEGRATION_TESTS = "1"
pytest apps/api/tests -v -m integration
```

Requires a valid `DATABASE_URL` in `.env`.

## Project Layout

```
apps/api/
├── app/
│   ├── main.py              # FastAPI application entrypoint
│   ├── core/
│   │   ├── config.py        # Settings from .env / environment
│   │   └── database.py      # SQLAlchemy engine, sessions, probe
│   ├── routers/
│   │   └── health.py        # GET /v1/health
│   ├── db/                  # SQLAlchemy base
│   └── models/              # User, Project ORM models
└── tests/
    ├── conftest.py
    └── test_health.py
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | Neon PostgreSQL connection string (`postgresql+psycopg://...?sslmode=require`) |
| `DATABASE_CONNECT_TIMEOUT` | No | Connection timeout in seconds (default: `5`) |
| `APP_ENV` | No | Environment name (default: `development`) |
| `LOG_LEVEL` | No | Log level (default: `INFO`) |
| `RUN_DATABASE_INTEGRATION_TESTS` | No | Set to `1` to enable live DB integration tests |

Credentials are read from `.env` or the process environment. They are never hard-coded in source.

## API Versioning

All endpoints are versioned under `/v1`. Future breaking changes will introduce `/v2` without removing `/v1` until deprecated.

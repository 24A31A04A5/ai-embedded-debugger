# AI Embedded Debugging Platform

A software-only AI engineering assistant for embedded developers. Helps diagnose firmware problems, analyze compiler and serial logs, and produce actionable fixes with structured, evidence-aware reasoning.

**Product requirements:** [`docs/SRS.md`](docs/SRS.md) is the source of truth.

## Repository Structure

```
apps/
  web/          # Next.js frontend (Phase 1)
  api/          # FastAPI backend (Phase 0 Step 2+)
db/             # Alembic migrations and schema
docs/           # Architecture decisions and product docs
infra/          # CI workflows and deployment config
tests/          # E2E and AI evaluation harness
scripts/        # Developer utility scripts
```

## Prerequisites

- **Node.js** 20+
- **pnpm** 9+
- **Python** 3.12+
- **Neon PostgreSQL** account ([neon.tech](https://neon.tech)) — no Docker required

## Quick Start (Phase 0)

### 1. Clone and configure environment

```bash
cp .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your Neon PostgreSQL connection string. See [`apps/api/README.md`](apps/api/README.md) for detailed setup.

### 2. Install frontend tooling

```bash
pnpm install
pnpm lint
pnpm typecheck
```

### 3. Install Python tooling

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
ruff check apps/api
mypy apps/api
pytest apps/api/tests -v
```

### 4. Run database migrations

```bash
alembic -c db/alembic.ini upgrade head
```

### 5. Run the API

```bash
uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000
```

## Development Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 Step 1 | **Complete** | Repo scaffold, CI, initial schema |
| Phase 0 Step 2 | **Complete** | FastAPI skeleton + health check |
| Phase 1 | Planned | Auth, projects, Next.js app |
| Phase 3 | Planned | AI debugging core |

## Architecture

See [`docs/architecture/ADR-001-monorepo.md`](docs/architecture/ADR-001-monorepo.md) for technology decisions and rationale.

## License

Proprietary — all rights reserved.

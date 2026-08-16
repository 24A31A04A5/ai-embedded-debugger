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
- **Docker** and Docker Compose (for local PostgreSQL and MinIO)

## Quick Start (Phase 0)

### 1. Clone and configure environment

```bash
cp .env.example .env
```

### 2. Start local infrastructure

```bash
docker compose up -d
```

Services:

| Service    | URL                         | Purpose              |
|------------|-----------------------------|----------------------|
| PostgreSQL | `localhost:5432`          | Primary database     |
| MinIO API  | `http://localhost:9000`     | S3-compatible storage|
| MinIO UI   | `http://localhost:9001`     | Storage console      |

### 3. Install frontend tooling

```bash
pnpm install
pnpm lint
pnpm typecheck
```

### 4. Install Python tooling

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
ruff check apps/api
mypy apps/api
```

### 5. Run database migrations

```bash
alembic -c db/alembic.ini upgrade head
```

## Development Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 Step 1 | **Complete** | Repo scaffold, CI, local infra, initial schema |
| Phase 0 Step 2 | Planned | FastAPI skeleton + health check |
| Phase 1 | Planned | Auth, projects, Next.js app |
| Phase 3 | Planned | AI debugging core |

## Architecture

See [`docs/architecture/ADR-001-monorepo.md`](docs/architecture/ADR-001-monorepo.md) for technology decisions and rationale.

## License

Proprietary — all rights reserved.

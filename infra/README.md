# Infrastructure

CI workflows, deployment configuration, and environment templates.

Local development uses **Neon PostgreSQL** via `DATABASE_URL`. Docker is not required for the current workflow. Object storage (MinIO/S3) will be added when file uploads are implemented.

## GitHub Actions

Workflow source copies live in `infra/github/workflows/`. GitHub executes workflows from `.github/workflows/` (kept in sync with `infra/`).

CI still uses a containerized PostgreSQL service for migration validation only; local developers do not need Docker.

For local development, run checks manually:

```bash
pnpm lint && pnpm typecheck
ruff check apps/api && mypy apps/api
pytest apps/api/tests -v
```

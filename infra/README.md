# Infrastructure

CI workflows, deployment configuration, and environment templates.

## GitHub Actions

Workflow source copies live in `infra/github/workflows/`. GitHub executes workflows from `.github/workflows/` (kept in sync with `infra/`).

For local development, run checks manually:

```bash
pnpm lint && pnpm typecheck
ruff check apps/api && mypy apps/api
```

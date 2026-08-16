# Database

PostgreSQL schema and Alembic migrations.

## Migrations

Ensure local infrastructure is running:

```bash
docker compose up -d
```

Apply migrations:

```bash
# From repository root, with Python venv activated and deps installed:
alembic -c db/alembic.ini upgrade head
```

Create a new migration after model changes:

```bash
alembic -c db/alembic.ini revision --autogenerate -m "description"
```

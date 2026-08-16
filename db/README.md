# Database

PostgreSQL schema and Alembic migrations.

Development uses a hosted [Neon](https://neon.tech) PostgreSQL database configured through `DATABASE_URL` in `.env`. Docker is not required.

## Migrations

Ensure `.env` contains your Neon `DATABASE_URL`, then apply migrations from the repository root:

```bash
alembic -c db/alembic.ini upgrade head
```

Create a new migration after model changes:

```bash
alembic -c db/alembic.ini revision --autogenerate -m "description"
```

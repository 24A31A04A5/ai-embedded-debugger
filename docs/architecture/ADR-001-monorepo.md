# ADR-001: Monorepo Architecture

**Status:** Accepted  
**Date:** 2026-03-16  
**Context:** Phase 0 — Repository foundation for the AI Embedded Debugging Platform MVP.

## Decision

Build the product as a **pnpm monorepo** containing:

- `apps/web` — Next.js frontend (to be scaffolded in Phase 1)
- `apps/api` — FastAPI backend (routes deferred to Phase 0 Step 2 / Phase 1)
- `db/` — PostgreSQL schema and Alembic migrations
- Shared infrastructure, CI, documentation, and evaluation harness at the repository root

## Rationale

### Why a monorepo

A single repository keeps the frontend, backend, database migrations, AI evaluation cases, and documentation in sync. For a small startup team, this reduces coordination overhead: one pull request can change an API contract, its migration, and the client that consumes it. It also matches the structure recommended in `docs/SRS.md` (§29) and supports a unified CI pipeline from day one.

Alternative considered: separate frontend and backend repositories. Rejected for MVP because it adds release coordination cost without benefit at current team size.

### Why Next.js for the frontend

Next.js with TypeScript is specified in SRS Table 6 and supports:

- Server-rendered landing page for SEO and product positioning (§13)
- A mature React ecosystem for the project workspace, code viewer, and diagnosis UI
- Straightforward deployment to Vercel
- Type-safe integration with a generated OpenAPI client in later phases

Alternative considered: Vite + React SPA. Rejected because the SRS explicitly recommends Next.js and SSR is valuable for the public landing page.

### Why FastAPI for the backend

FastAPI with Python is specified in SRS Table 6. Python is the practical choice for:

- AI orchestration and prompt management (§8)
- Document ingestion and RAG pipelines (§8.4, Phase 6)
- File text extraction and future protocol log parsing
- OpenAPI-native API design (§14)

The frontend handles presentation; the backend owns authentication verification, authorization, file processing, AI orchestration, persistence, and usage control (§12).

Alternative considered: Next.js API routes only. Rejected because Python's AI/document ecosystem avoids a later rewrite when RAG and protocol analysis are added.

### Why PostgreSQL as the primary database

PostgreSQL is specified in SRS Table 6 and fits the relational data model (Table 8):

- Users, projects, files, sessions, messages, usage records, and feedback are inherently relational
- ACID transactions for authorization and billing-adjacent usage tracking
- Strong indexing for dashboard and session history queries
- Optional `pgvector` extension available later if vector storage strategy changes

Alternative considered: MongoDB. Rejected because project isolation, foreign keys, and audit trails map naturally to relational schema.

### Why object storage is separate from PostgreSQL

Firmware source files, compiler logs, serial output, and future PDF datasheets can be large and binary. PostgreSQL stores **metadata** (path, type, size, checksum, storage key); object storage (S3-compatible, MinIO locally) stores **raw file bytes** (§17).

This separation:

- Keeps the database fast for queries and authorization checks
- Allows cheap, scalable blob storage with presigned upload URLs
- Matches production deployment patterns (R2, S3, etc.)
- Enables independent retention and deletion policies for files vs. relational records

### Why AI providers are accessed through an abstraction layer

SRS §8.3 and NFR-010 require avoiding lock-in to a single LLM vendor. A thin `LLMProvider` interface allows:

- Swapping OpenAI, Anthropic, or open models via configuration
- Mock providers for tests and the evaluation harness (§19)
- Token accounting and cost routing without changing business logic
- Future on-prem or specialized model deployment (§5.2, §28)

We intentionally avoid heavy orchestration frameworks in MVP; a small adapter module is sufficient.

### Why RAG is deferred from MVP

SRS §5.1 defines MVP as C/C++ firmware analysis and compiler/serial log diagnosis. Datasheet PDF RAG is explicitly **post-MVP** (§5.2). The MVP Definition of Done (§27) does not require document retrieval.

Deferring RAG:

- Keeps MVP scope small enough to validate the core debugging workflow quickly (§33)
- Avoids premature vector database and embedding infrastructure cost
- Allows the `rag/` module interfaces to be designed without blocking the primary user journey

RAG is planned for Phase 6 (Week 6–7) with Qdrant and structure-aware document ingestion (§8.4, Table 11).

## Consequences

**Positive:**

- Clear separation of concerns between UI, API, data, and AI layers
- One CI pipeline validates frontend, backend, and migrations together
- Extension points for RAG, protocol analysis, GitHub, and IDE integration without restructuring

**Negative:**

- Monorepo requires both Node.js and Python toolchains in developer environments
- Two deployment targets (Vercel + Railway/Render) to manage in production

**Neutral:**

- Phase 0 ships tooling and schema only; product features begin in subsequent phases

## References

- `docs/SRS.md` — §5.1 (MVP scope), §8 (AI/ML), §12 (architecture), §29 (repository structure), Table 6 (technology stack)

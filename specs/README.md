# Specifications — AI Knowledge Assistant

This folder is the single source of truth for the AI Knowledge Assistant project **before any application code is written**. Every document here contains concrete, opinionated decisions — not generic descriptions — so that implementation can proceed without re-litigating architecture mid-build.

## Reading order

If you are new to the project, read in this order:

1. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — what we're building and why
2. [REQUIREMENTS.md](REQUIREMENTS.md) — functional/non-functional requirements, MVP scope
3. [TECHNOLOGIES.md](TECHNOLOGIES.md) — stack choices and rationale
4. [ARCHITECTURE.md](ARCHITECTURE.md) — layered architecture, module boundaries, replaceable components
5. [DATABASE.md](DATABASE.md) — schema, ERD, indexing strategy
6. [RAG_PIPELINE.md](RAG_PIPELINE.md) — ingestion + retrieval pipeline, chunking/embedding/prompting decisions
7. [API.md](API.md) — REST contract
8. [SECURITY.md](SECURITY.md) — threat model and mitigations, including RAG-specific prompt injection
9. [EVALUATION.md](EVALUATION.md) — how we know the RAG system actually works
10. [TESTING.md](TESTING.md) — test strategy across unit/integration/E2E
11. [DEVOPS.md](DEVOPS.md) — Docker, Compose, CI/CD
12. [ROADMAP.md](ROADMAP.md) — phased, checkbox-level implementation plan

## Status

**Phase 0 — Architecture and specifications.** No application code has been written yet. This is intentional: see [ROADMAP.md](ROADMAP.md) for the phase plan.

## Consistency rules

These documents cross-reference each other and must stay in sync. In particular:

- The database schema in `DATABASE.md` must support every endpoint in `API.md`.
- The embedding model / vector dimensions in `RAG_PIPELINE.md` must match the `document_chunks.embedding` column definition in `DATABASE.md`.
- Every technology named in `ARCHITECTURE.md`, `DATABASE.md`, `RAG_PIPELINE.md`, and `DEVOPS.md` must appear in `TECHNOLOGIES.md` with a rationale.
- `ROADMAP.md` phases must map onto the module boundaries defined in `ARCHITECTURE.md`.

If you change a decision in one document, propagate the change to every document listed above before considering the change complete.

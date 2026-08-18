# AI Knowledge Assistant

A production-oriented Retrieval-Augmented Generation (RAG) platform: upload documents, ask natural-language questions, get answers grounded strictly in your own documents — with citations, streaming responses, and an explicit "I couldn't find this in your documents" fallback when the answer isn't there.

> **Project status: Phase 0 — specification and architecture complete, implementation not yet started.**
> Everything in this README describes the *planned* system, as defined in [`specs/`](specs/). See [specs/ROADMAP.md](specs/ROADMAP.md) for what's actually been built vs. what's planned. Nothing below should be read as "already working" unless explicitly marked.

## Why this project

This is a portfolio project built to demonstrate real RAG engineering, not a "PDF + ChatGPT" wrapper: a layered backend architecture with replaceable AI providers, a documented and rationale-backed retrieval pipeline (chunking, embeddings, vector indexing, prompting), automated evaluation of answer quality (not just "it runs"), and the testing/CI/security/observability practices expected of a production system. Full reasoning is in [specs/PROJECT_OVERVIEW.md](specs/PROJECT_OVERVIEW.md).

## Architecture overview

Layered architecture with the AI/infra-facing pieces behind swappable interfaces (ports & adapters), so the embedding provider, LLM provider, vector store, and document parser can each be replaced without touching business logic.

```
Client (React/TS)
      │  REST + SSE
      ▼
API layer (FastAPI routers)
      │
Service layer (use-case orchestration)
      │
Domain layer (entities + ports: EmbeddingProvider, LLMProvider, VectorStore, DocumentParser)
      │
Infrastructure adapters (OpenAI, pgvector, LangChain text splitting, pypdf)
      │
PostgreSQL + pgvector
```

Full detail, including the exact module layout and request-flow diagrams for ingestion and chat: [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md).

## Planned features (MVP)

- Upload PDF/TXT documents with type/size validation
- Async ingestion: text extraction → cleaning → chunking → embedding → vector storage
- Live document status (`pending` → `processing` → `completed`/`failed`)
- Ask questions in a chat interface, scoped to all or selected documents
- Vector similarity search (pgvector, HNSW index, cosine distance) with a relevance threshold
- Streamed, LLM-generated answers (Server-Sent Events)
- Inline citations back to source document + page
- Explicit "not found in your documents" response instead of hallucinated answers
- Basic JWT authentication with per-user data isolation
- Full local stack via `docker compose up`
- CI (lint, type-check, unit + integration tests, build verification) on every push
- A small automated evaluation harness (retrieval precision/recall, answer faithfulness, citation correctness)

See [specs/REQUIREMENTS.md §4](specs/REQUIREMENTS.md) for the precise MVP / post-MVP / future-ideas boundary.

## Technology stack

| Layer | Stack |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| AI / RAG | OpenAI API (`text-embedding-3-small`, `gpt-4o-mini`), LangChain (text splitting only) |
| Database | PostgreSQL 16 + pgvector (HNSW index, cosine similarity) |
| Frontend | React 18, TypeScript, TailwindCSS, Vite |
| DevOps | Docker, Docker Compose, GitHub Actions |
| Testing | pytest, pytest-asyncio, httpx, vitest, React Testing Library, RAGAS (evaluation) |

Full rationale and alternatives considered for every entry: [specs/TECHNOLOGIES.md](specs/TECHNOLOGIES.md).

## Project structure (planned)

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── core/            # config, security, logging, DI wiring
│   │   ├── domain/           # entities, ports (interfaces), exceptions
│   │   ├── services/          # use-case orchestration
│   │   ├── repositories/       # SQLAlchemy data access
│   │   ├── models/              # ORM models
│   │   ├── schemas/              # Pydantic request/response DTOs
│   │   ├── rag/                   # embedding/LLM/vector-store/chunking/prompting adapters
│   │   ├── documents/              # document parsers
│   │   ├── db/                      # session/engine setup
│   │   └── main.py
│   ├── alembic/
│   ├── tests/{unit,integration,e2e}/
│   └── Dockerfile
├── frontend/
│   ├── src/{api,components,pages,hooks,types}/
│   └── Dockerfile
├── eval/                   # evaluation dataset + harness
├── specs/                  # full specification set (read this first)
├── docker-compose.yml
└── .github/workflows/ci.yml
```

Full layer-by-layer explanation: [specs/ARCHITECTURE.md](specs/ARCHITECTURE.md).

## Local setup (planned — once implementation begins)

```bash
git clone <repo-url>
cd ai-knowledge-assistant
cp .env.example .env        # fill in OPENAI_API_KEY at minimum
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

Backend-only development without Docker (Postgres via Compose, app run locally with `uvicorn app.main:app --reload`) will also be supported for faster iteration.

## Environment variables

| Variable | Purpose | Required |
|---|---|---|
| `DATABASE_URL` | Postgres connection string | Yes |
| `OPENAI_API_KEY` | OpenAI API access | Yes |
| `EMBEDDING_MODEL` | Default `text-embedding-3-small` | No |
| `LLM_MODEL` | Default `gpt-4o-mini` | No |
| `JWT_SECRET_KEY` | JWT signing secret | Yes |
| `JWT_EXPIRE_MINUTES` | Default `60` | No |
| `MAX_UPLOAD_SIZE_MB` | Default `20` | No |
| `ALLOWED_ORIGINS` | CORS allowlist | Yes |
| `UPLOAD_STORAGE_PATH` | Default `/data/uploads` | No |
| `ENABLE_DOCS` | Toggle `/docs` exposure | No |
| `LOG_LEVEL` | Default `INFO` | No |

Full list and defaults: [specs/DEVOPS.md §3](specs/DEVOPS.md). `.env.example` will be committed once Phase 1 begins; never commit a real `.env`.

## Docker setup

Three services: `postgres` (pgvector-enabled Postgres image), `backend` (FastAPI, runs Alembic migrations on startup), `frontend` (static build served via nginx). All three define health checks; `backend` waits on `postgres`'s healthcheck before starting. Full details: [specs/DEVOPS.md](specs/DEVOPS.md).

## API overview

REST API under `/api/v1`, JWT bearer auth, JSON except upload (multipart) and chat streaming (Server-Sent Events).

- **Auth**: `POST /auth/register`, `POST /auth/login`
- **Documents**: `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/status`, `DELETE /documents/{id}`
- **Chat**: `POST /conversations`, `GET /conversations`, `GET /conversations/{id}`, `GET /conversations/{id}/messages`, `POST /conversations/{id}/messages` (streams the answer via SSE)
- **Health**: `GET /health`, `GET /health/ready`

Full request/response schemas, status codes, and error shapes: [specs/API.md](specs/API.md).

## RAG pipeline summary

```
Upload → validate → extract text → clean → chunk (1000 chars, 150 overlap)
  → embed (text-embedding-3-small, 1536-dim) → store in pgvector (HNSW, cosine)

Question → embed → similarity search (Top-K=5, similarity ≥ 0.75)
  → build delimited context prompt → stream LLM answer (gpt-4o-mini) → citations
```

Every parameter above is chosen for a stated reason, not a default — see [specs/RAG_PIPELINE.md](specs/RAG_PIPELINE.md), including the grounding/anti-hallucination strategy and RAG-specific prompt injection defenses (also covered in [specs/SECURITY.md](specs/SECURITY.md)).

## Roadmap

Implementation proceeds in phases, MVP-first:

- **Phase 0** — Architecture & specifications ✅ *(this repo's current state)*
- **Phase 1** — Project setup
- **Phase 2** — Database & document ingestion
- **Phase 3** — Embeddings & vector search
- **Phase 4** — RAG pipeline
- **Phase 5** — Chat API
- **Phase 6** — Authentication
- **Phase 7** — React frontend
- **Phase 8** — Testing & evaluation
- **Phase 9** — Docker & CI/CD *(MVP complete after this phase)*
- **Phase 10** — Security & production hardening (post-MVP)

Full checkbox-level task breakdown per phase: [specs/ROADMAP.md](specs/ROADMAP.md).

## Screenshots

*(To be added once the frontend is implemented — Phase 7.)*

## Future improvements

Beyond the MVP and Phase 10 hardening, the following are documented as intentional future ideas, not current plans: hybrid (lexical + vector) search, reranking, OCR for scanned PDFs, DOCX support, document collections, richer conversational memory, a background job queue (Celery/RQ + Redis), object storage (S3/MinIO), local/self-hosted LLM support, multilingual RAG, expanded automated evaluation, observability dashboards, Kubernetes deployment. Full list: [specs/ROADMAP.md §Future improvements](specs/ROADMAP.md).

## Specifications

Everything above is a summary. The authoritative, detailed specs live in [`specs/`](specs/) — start with [specs/README.md](specs/README.md).

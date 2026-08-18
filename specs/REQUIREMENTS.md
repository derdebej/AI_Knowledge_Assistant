# Requirements — AI Knowledge Assistant

## 1. Functional requirements

### 1.1 Authentication (MVP)

> **Ambiguity resolved:** the original brief lists "multi-user authentication" under *Future Improvements* but also requires a `users` table, per-user data isolation, and API authentication under *Security*. These are contradictory if taken literally. Resolution: the MVP ships **basic** authentication (email + password, JWT bearer tokens, single-tenant-per-user data isolation). What's deferred to post-MVP is *advanced* auth: OAuth/SSO, roles/permissions, org/team accounts, email verification flows. Basic auth is required for the MVP because without it, "data isolation between users" (an explicit security requirement) is meaningless.

- FR-1.1 Users can register with email + password.
- FR-1.2 Users can log in and receive a JWT access token.
- FR-1.3 All document, conversation, and message resources are scoped to the authenticated user.
- FR-1.4 A user cannot read, list, or delete another user's documents or conversations.

### 1.2 Document management

- FR-2.1 Users can upload PDF and TXT files up to 20 MB.
- FR-2.2 Uploaded files are validated for extension, MIME type, and size before processing.
- FR-2.3 Users can list their documents with status (`pending`, `processing`, `completed`, `failed`).
- FR-2.4 Users can view a single document's metadata and processing status.
- FR-2.5 Users can delete a document; deletion cascades to its chunks and embeddings.
- FR-2.6 Document processing (extraction, chunking, embedding) happens asynchronously relative to the upload response — the upload call returns immediately with `status=pending`.
- FR-2.7 Failed processing records a human-readable error and status `failed`; it does not silently disappear.

### 1.3 Chat / RAG

- FR-3.1 Users can create a conversation.
- FR-3.2 A conversation may optionally be scoped to a subset of the user's documents; if unscoped, retrieval searches across all of the user's completed documents.
- FR-3.3 Users can send a message (question) within a conversation.
- FR-3.4 The system retrieves the most relevant chunks via vector similarity search.
- FR-3.5 The system generates an answer grounded in retrieved chunks and streams it to the client token-by-token (SSE).
- FR-3.6 Every assistant answer includes citations: which document(s) and which chunk(s) informed the answer.
- FR-3.7 If no retrieved chunk clears the relevance threshold, the assistant responds that the answer could not be found in the user's documents, and does not fall back to unsupported general knowledge.
- FR-3.8 Users can retrieve the full message history of a conversation.
- FR-3.9 Users can list their conversations.

### 1.4 System

- FR-4.1 A liveness health check endpoint (`/health`) reports process health.
- FR-4.2 A readiness check endpoint (`/health/ready`) verifies DB connectivity (and, transitively, pgvector availability).

## 2. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Query latency (first token) | < 3s p95 for a document set of ≤ 200 chunks, warm connection pool |
| NFR-2 | Upload processing time | < 30s for a 20-page PDF (excluding OpenAI API latency spikes) |
| NFR-3 | Availability of local dev environment | `docker compose up` succeeds with no manual DB setup |
| NFR-4 | Data isolation | Enforced at the query layer (every repository query filters by `user_id`), not just the UI |
| NFR-5 | Secrets | No API key, DB credential, or JWT secret ever committed to the repo or written to logs |
| NFR-6 | Observability | Every request traceable via a request ID present in logs and (optionally) response headers |
| NFR-7 | Test coverage | Core domain logic (chunking, prompt construction, retrieval ranking) covered by unit tests; ingestion + query pipeline covered by integration tests |
| NFR-8 | Portability | Embedding provider, LLM provider, vector store, and parser are each swappable via a defined interface without touching the service layer |

## 3. Constraints

- C-1 Backend: Python 3.12+, FastAPI, PostgreSQL 16+ with pgvector.
- C-2 Frontend: React + TypeScript + TailwindCSS.
- C-3 LLM/embeddings: OpenAI API for the MVP, behind provider interfaces (see [ARCHITECTURE.md](ARCHITECTURE.md)).
- C-4 Must run fully via Docker Compose for local development.
- C-5 No paid infrastructure required to run or evaluate the project locally, beyond an OpenAI API key the user supplies.

## 4. MVP vs. Post-MVP vs. Future Ideas

This project distinguishes three tiers. Detailed task breakdowns live in [ROADMAP.md](ROADMAP.md); this table is the authoritative scope boundary.

### MVP (must ship first — see [ROADMAP.md](ROADMAP.md) Phases 0–9)

- PDF/TXT upload with validation
- Text extraction + cleaning
- Fixed-strategy chunking (recursive character splitter)
- OpenAI embeddings (`text-embedding-3-small`)
- PostgreSQL + pgvector storage with HNSW index
- Cosine-similarity Top-K retrieval with a relevance threshold
- RAG prompt construction with citation extraction
- OpenAI chat completion (`gpt-4o-mini`) with streaming
- Basic JWT authentication and per-user data isolation
- FastAPI REST API (documents, chat, health)
- React chat UI with upload, document list/status, streaming chat, citation display
- Docker Compose (backend, frontend, Postgres+pgvector)
- GitHub Actions CI (lint, type-check, unit + integration tests, build)
- Structured logging with request IDs
- A small (10–20 question) evaluation dataset with a runnable eval script

### Post-MVP (planned, not in first release — see [ROADMAP.md](ROADMAP.md) Phase 10+)

- Cross-encoder or Cohere reranking of retrieved chunks
- Rate limiting middleware (`slowapi` or equivalent)
- Prometheus metrics / dashboards
- Background job queue (Celery/RQ + Redis) instead of in-process async processing
- Object storage (S3-compatible) instead of local disk for uploaded files

### Future ideas (documented, not scheduled)

See [ROADMAP.md §Future Improvements](ROADMAP.md) for the full list: hybrid (lexical + vector) search, OCR for scanned PDFs, DOCX support, document collections, multi-turn conversational memory beyond raw history replay, local/self-hosted LLM support, multilingual RAG, advanced automated evaluation (LLM-as-judge panels), observability dashboards, Kubernetes deployment.

## 5. Assumptions

- A single OpenAI account/API key is sufficient for local dev and demo purposes; no fallback provider is required for the MVP to function (though the interface exists to add one).
- Users upload documents they have rights to; the system does not attempt DRM or copyright detection.
- "Production-oriented" means the code and architecture *reflect* production practices (auth, tests, CI, observability); it does not mean the project is deployed to a live production environment with SLAs.

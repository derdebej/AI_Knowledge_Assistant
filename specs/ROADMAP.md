# Roadmap — AI Knowledge Assistant

Each phase lists objectives, tasks (checkboxes), deliverables, dependencies, and a definition of done. Phases 0–9 constitute the MVP (see [REQUIREMENTS.md](REQUIREMENTS.md) §4). Phase 10 is post-MVP hardening. Future ideas beyond Phase 10 are listed at the end and are explicitly **not scheduled**.

---

## Phase 0 — Architecture and specifications

**Objective**: produce a complete, internally consistent specification set before any application code exists.

- [x] Write `specs/PROJECT_OVERVIEW.md`
- [x] Write `specs/REQUIREMENTS.md`
- [x] Write `specs/ARCHITECTURE.md`
- [x] Write `specs/DATABASE.md` with Mermaid ERD
- [x] Write `specs/RAG_PIPELINE.md`
- [x] Write `specs/API.md`
- [x] Write `specs/SECURITY.md`
- [x] Write `specs/EVALUATION.md`
- [x] Write `specs/TESTING.md`
- [x] Write `specs/DEVOPS.md`
- [x] Write `specs/TECHNOLOGIES.md`
- [x] Write `specs/ROADMAP.md`
- [x] Write root `README.md`
- [x] Cross-check consistency (schema ↔ API ↔ RAG pipeline ↔ roadmap)

**Deliverables**: complete `specs/` folder, root README.
**Dependencies**: none.
**Definition of done**: every document in §17 of the original brief exists, contains concrete decisions (not generic filler), and no document contradicts another.

---

## Phase 1 — Project setup

**Objective**: scaffolding for both backend and frontend, no business logic yet.

- [x] Initialize `backend/` with `pyproject.toml` (dependencies: fastapi, uvicorn, sqlalchemy, alembic, pydantic-settings, asyncpg, passlib, python-jose, python-magic, pypdf, langchain-text-splitters, openai, structlog, ruff, mypy, pytest, pytest-asyncio, httpx) — managed via `uv`
- [x] Create `app/main.py` FastAPI app factory (placeholder route = `GET /api/v1/health`, since it's genuinely needed and trivial — see [API.md](API.md) §4)
- [x] Create `app/core/config.py` (`Settings` reading env vars per [DEVOPS.md](DEVOPS.md) §3)
- [x] Create `.env.example`
- [x] Configure `ruff` + `mypy` config files
- [x] Initialize `frontend/` with Vite + React + TypeScript template
- [x] Configure TailwindCSS (v4, via `@tailwindcss/vite`)
- [x] Configure ESLint + `tsc --noEmit` (swapped in for Vite's default `oxlint` scaffold to match [TECHNOLOGIES.md](TECHNOLOGIES.md))
- [x] Create root `docker-compose.yml` with `postgres` (pgvector image) service only, healthcheck
- [ ] Verify `docker compose up postgres` starts cleanly — **blocked**: Docker is not installed on this machine. `docker-compose.yml` is written and reviewed but unverified; confirm on first Docker-enabled run or before Phase 9.

**Deliverables**: runnable empty FastAPI app, runnable empty React app, Postgres+pgvector container healthy.
**Dependencies**: Phase 0.
**Definition of done**: `uvicorn app.main:app` serves `/docs` (verified) · `npm run dev` serves the placeholder page and proxies `/api` to the backend (verified) · `docker compose up postgres` passes its healthcheck (pending Docker installation).

---

## Phase 2 — Database and document ingestion (non-AI parts)

**Objective**: schema, migrations, file upload, extraction, chunking — everything except embeddings.

- [ ] Create `app/models/` SQLAlchemy models for all tables in [DATABASE.md](DATABASE.md) §3
- [ ] Create Alembic environment; first migration: enable `vector` extension, create all tables, create HNSW index
- [ ] Implement `app/domain/ports.py` (`EmbeddingProvider`, `LLMProvider`, `VectorStore`, `DocumentParser`, `Chunker` interfaces)
- [ ] Implement `DocumentParser` adapters (PDF via `pypdf`, TXT)
- [ ] Implement text cleaning function ([RAG_PIPELINE.md](RAG_PIPELINE.md) §1.3) with unit tests
- [ ] Implement `Chunker` adapter (LangChain `RecursiveCharacterTextSplitter` wrapper) with unit tests
- [ ] Implement `app/repositories/document_repository.py`
- [ ] Implement `DocumentService.upload()` (validation: extension, MIME sniff, size — [SECURITY.md](SECURITY.md) §1)
- [ ] Implement `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/status`, `DELETE /documents/{id}` per [API.md](API.md) §2
- [ ] Implement local disk storage (`UPLOAD_STORAGE_PATH`, sanitized paths)
- [ ] Wire background processing trigger (FastAPI `BackgroundTasks`) that runs extraction + cleaning + chunking and persists chunks (embedding step stubbed/skipped until Phase 3)
- [ ] Integration tests: migrations apply cleanly, repository CRUD + cascade deletes, upload endpoint incl. rejection cases

**Deliverables**: users can upload a PDF/TXT and see it chunked and stored (no embeddings yet); `status` transitions correctly.
**Dependencies**: Phase 1.
**Definition of done**: integration test suite green against a real Postgres+pgvector container; a manually uploaded PDF produces rows in `document_chunks` with correct `chunk_index`/`content`.

---

## Phase 3 — Embeddings and vector search

**Objective**: complete the ingestion pipeline with real embeddings; implement retrieval.

- [ ] Implement `OpenAIEmbeddingProvider` (batched calls, `text-embedding-3-small`)
- [ ] Implement `FakeEmbeddingProvider` for tests ([TESTING.md](TESTING.md) §5)
- [ ] Implement `PgVectorStore` (`upsert`, `similarity_search` with `user_id` + optional `document_id` filtering)
- [ ] Wire embedding step into `IngestionService`; document reaches `status=completed` only after embeddings are stored
- [ ] Implement `RetrievalService.retrieve()`: embed query, similarity search, Top-K=5, threshold ≥0.75 filter ([RAG_PIPELINE.md](RAG_PIPELINE.md) §2.3)
- [ ] Unit tests for Top-K + threshold + scoping logic against `FakeVectorStore`
- [ ] Integration test: seed known chunks/embeddings, verify pgvector similarity ordering and HNSW index usage (`EXPLAIN`)

**Deliverables**: end-to-end ingestion with real embeddings; a retrieval function that returns correctly ranked, correctly filtered chunks.
**Dependencies**: Phase 2.
**Definition of done**: a document uploaded via the API is fully embedded and queryable via `RetrievalService` in an integration test, using real OpenAI calls in at least one smoke test and faked calls elsewhere.

---

## Phase 4 — RAG pipeline (prompting + generation)

**Objective**: turn retrieved chunks into a grounded, cited answer.

- [ ] Implement `app/rag/prompting/` — system prompt template + context-block assembly per [RAG_PIPELINE.md](RAG_PIPELINE.md) §2.6
- [ ] Implement `OpenAILLMProvider` (streaming + non-streaming `generate()`)
- [ ] Implement `FakeLLMProvider` for tests
- [ ] Implement the "not found" short-circuit (zero chunks above threshold → fixed message, no LLM call) — [RAG_PIPELINE.md](RAG_PIPELINE.md) §5
- [ ] Implement citation extraction (chunks shown to the model → `message_citations` records)
- [ ] Unit tests: prompt structure/delimiting, short-circuit path never invokes `LLMProvider`
- [ ] Integration test: seeded chunks → real retrieval → faked LLM → assert prompt content and citation records

**Deliverables**: a callable `ChatService.ask()` producing a grounded answer + citations, independent of the API/streaming layer.
**Dependencies**: Phase 3.
**Definition of done**: given a seeded document and a question with a known answer, `ChatService.ask()` returns an answer referencing the correct chunk(s); given an out-of-corpus question, it returns the fixed refusal.

---

## Phase 5 — Chat API

**Objective**: expose conversations/messages over REST, including streaming.

- [ ] Implement `app/models`/`repositories` for `conversations`, `conversation_documents`, `messages`, `message_citations`
- [ ] Implement `POST /conversations`, `GET /conversations`, `GET /conversations/{id}`, `GET /conversations/{id}/messages` per [API.md](API.md) §3
- [ ] Implement `POST /conversations/{id}/messages` with SSE streaming (`token`, `citations`, `done`, `error` events)
- [ ] Enforce document-ownership check when scoping a conversation to `document_ids`
- [ ] Integration tests: full conversation lifecycle, SSE event sequence assertions, ownership rejection (`400`/`404`) cases

**Deliverables**: complete chat REST API, streaming functional via `curl`/Postman.
**Dependencies**: Phase 4.
**Definition of done**: a scripted `httpx` integration test drives create-conversation → send-message → receive streamed tokens + citations → fetch history, end to end.

---

## Phase 6 — Authentication

**Objective**: basic JWT auth and data isolation, moved here (rather than Phase 1) so it's built once the resources it protects already exist — but *before* the frontend, so the frontend is built against a real auth flow from the start.

- [ ] Implement `app/models`/`repositories/user_repository.py`
- [ ] Implement password hashing (`passlib`/bcrypt), JWT encode/decode (`python-jose`)
- [ ] Implement `POST /auth/register`, `POST /auth/login` per [API.md](API.md) §1
- [ ] Implement the auth dependency (`get_current_user`) and apply it to all document/chat routes
- [ ] Retrofit `user_id` scoping into every repository method from Phases 2–5 (documents, conversations, messages)
- [ ] Integration tests: register/login flow, protected-route rejection without token, cross-user access returns `404`

**Deliverables**: fully authenticated API; every prior endpoint now enforces ownership.
**Dependencies**: Phases 2–5 (retrofits their repositories).
**Definition of done**: an integration test proves user B cannot read/delete user A's document or conversation.

---

## Phase 7 — React frontend

**Objective**: usable UI for the full flow: login, upload, document status, chat, citations.

- [ ] `api/` typed client (fetch wrappers + SSE consumer)
- [ ] `LoginPage` (login/register forms)
- [ ] `DocumentUpload` component (drag-drop, client-side type/size pre-check mirroring backend rules, upload progress)
- [ ] `DocumentList` component (status badges, polling `GET /documents/{id}/status` while `pending`/`processing`)
- [ ] `ChatWindow` component (message list, input box, per-conversation document scoping picker)
- [ ] `useStreamingAnswer` hook consuming the SSE endpoint, rendering tokens incrementally
- [ ] `CitationCard` component (document name, page number, snippet, similarity score)
- [ ] Distinct UI state for the "not found in your documents" response
- [ ] Component tests for the above (`vitest` + RTL)

**Deliverables**: a working browser UI covering the full MVP user story from [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md).
**Dependencies**: Phase 6 (needs the full authenticated API).
**Definition of done**: manual walkthrough in a browser — register, upload a PDF, watch status change, ask a question, see streamed answer with citations, ask an out-of-scope question and see the "not found" state.

---

## Phase 8 — Testing and evaluation completeness

**Objective**: close testing gaps left incidental to earlier phases; stand up the evaluation harness.

- [ ] Audit unit/integration test coverage against [TESTING.md](TESTING.md) §2–3 checklists; fill gaps
- [ ] Implement backend E2E test (`tests/e2e/`, gated behind `RUN_E2E_LLM_TESTS`) per [TESTING.md](TESTING.md) §4
- [ ] Build `eval/dataset.json` (15–20 questions) and `eval/fixtures/` seed documents per [EVALUATION.md](EVALUATION.md) §3, including a deliberate prompt-injection fixture document
- [ ] Implement `eval/run_eval.py` (retrieval precision/recall + RAGAS faithfulness/relevance/context-relevance + not-found accuracy)
- [ ] Run the eval harness, record baseline results, tune the 0.75 relevance threshold if the baseline reveals it's miscalibrated

**Deliverables**: green test suite; a runnable, documented evaluation harness with a recorded baseline result set.
**Dependencies**: Phase 7 (needs the complete pipeline; UI not required for eval itself).
**Definition of done**: `pytest` passes locally and in CI; `python eval/run_eval.py` produces a report with all aggregate metrics above their defined floors, or documented, understood exceptions.

---

## Phase 9 — Docker and CI/CD

**Objective**: one-command local deployment and automated CI, per [DEVOPS.md](DEVOPS.md).

- [ ] Backend `Dockerfile` (multi-stage, non-root)
- [ ] Frontend `Dockerfile` (multi-stage, nginx)
- [ ] Complete `docker-compose.yml` (backend + frontend + postgres, healthchecks, volumes)
- [ ] Alembic-on-startup entrypoint for the backend container
- [ ] `.github/workflows/ci.yml`: lint+typecheck (backend & frontend), backend tests (with Postgres service container), frontend tests, Docker build verification
- [ ] Separate `workflow_dispatch` workflow for evaluation + OpenAI-backed E2E
- [ ] README badge for CI status

**Deliverables**: `docker compose up --build` runs the full stack from a clean checkout; CI green on push.
**Dependencies**: Phase 8.
**Definition of done**: a fresh clone + `.env` fill-in + `docker compose up --build` reaches a working app with no manual steps; CI pipeline passes on the `main` branch.

**→ MVP complete at the end of Phase 9.**

---

## Phase 10 — Security and production hardening (post-MVP)

**Objective**: close the gaps explicitly deferred in [SECURITY.md](SECURITY.md) §10.

- [ ] Rate limiting (`slowapi`) on upload and chat-message endpoints
- [ ] Refresh-token rotation for auth
- [ ] Postgres Row-Level Security as defense-in-depth beneath application-level `user_id` filtering
- [ ] Structured audit logging for auth events (login success/failure, registration)
- [ ] Reranking step (`Reranker` port implementation — Cohere or cross-encoder) per [RAG_PIPELINE.md](RAG_PIPELINE.md) §2.4
- [ ] Prometheus metrics endpoint + example Grafana dashboard (retrieval latency, LLM latency, token usage)

**Deliverables**: hardened auth, retrieval quality improvement (reranking), basic metrics.
**Dependencies**: Phase 9 (MVP complete).
**Definition of done**: each item independently tested and documented; this phase is additive and does not require re-touching the MVP's core architecture.

---

## Future improvements (not scheduled)

Documented for completeness; no phase number assigned, no commitment to build:

- Hybrid search (lexical/BM25 + vector, combined via reciprocal rank fusion)
- OCR pipeline for scanned/image-only PDFs (e.g., via `unstructured` or a dedicated OCR service)
- DOCX and other document format support
- Document collections / folders / tagging
- Richer conversational memory (summarization of long conversation history instead of raw replay)
- Background job queue (Celery/RQ + Redis) replacing in-process `BackgroundTasks` — see [ARCHITECTURE.md](ARCHITECTURE.md) §7
- Object storage (S3-compatible / MinIO) replacing local disk — see [DATABASE.md](DATABASE.md) §7
- Local/self-hosted LLM support (Ollama-backed `LLMProvider`/`EmbeddingProvider` adapters)
- Multilingual RAG (multilingual embedding model, language-aware chunking)
- Advanced automated evaluation (larger golden set, multi-judge panels, human-in-the-loop review UI)
- Observability dashboards (Grafana beyond the Phase 10 basics)
- Kubernetes deployment manifests/Helm chart

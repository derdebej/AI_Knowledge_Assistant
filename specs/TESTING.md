# Testing Strategy — AI Knowledge Assistant

Backend testing uses `pytest` + `pytest-asyncio` + `httpx.AsyncClient`. Frontend testing uses `vitest` + `React Testing Library` for components, deliberately kept lighter than the backend suite since the project's portfolio value is weighted toward the RAG/backend engineering (see [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)).

## 1. Test pyramid for this project

```
        E2E (few, slow, real stack)
      Integration (moderate, real Postgres+pgvector, mocked LLM)
    Unit (many, fast, no I/O)
```

## 2. Unit tests (`backend/tests/unit/`)

No network, no database, no filesystem — pure logic, run in well under a second total. Domain interfaces are satisfied with in-memory fakes, not mocks-of-everything, where a fake keeps the test closer to real behavior (e.g., a `FakeVectorStore` backed by a Python list with brute-force cosine comparison, rather than mocking every SQLAlchemy call).

Coverage targets:
- **Chunking**: `RecursiveCharacterTextSplitter` wrapper — correct chunk count for known input, overlap actually present at boundaries, chunk_index ordering, empty-input edge case, single-paragraph-under-chunk-size case.
- **Text cleaning**: whitespace collapsing, header/footer stripping heuristic, Unicode normalization — table-driven tests with before/after pairs.
- **Document processing (service logic)**: `IngestionService` orchestration using fake `DocumentParser`/`Chunker`/`EmbeddingProvider`/`VectorStore` — verifies the correct call sequence and that a failure at any stage results in `status=failed` with a captured error, not a partial silent success.
- **Embedding service adapter contract**: the OpenAI adapter's batching logic (chunk list → correctly-sized API call batches) tested against a fake HTTP client, not the real OpenAI API.
- **Retrieval / ranking logic**: given a fixed set of fake retrieved candidates with similarity scores, verify Top-K selection, the 0.75 threshold filter, and document-scope metadata filtering behave exactly as specified in [RAG_PIPELINE.md](RAG_PIPELINE.md) §2.3.
- **Prompt construction**: given a question + a list of chunks, assert the assembled prompt contains the delimiting structure from [RAG_PIPELINE.md](RAG_PIPELINE.md) §2.6 (context block present, labeled, question in its own slot) — this is what makes the prompt-injection defense testable rather than just documented.
- **Business logic**: JWT encode/decode round-trip, password hashing/verification, "not found" short-circuit decision (zero chunks above threshold → refusal path, no LLM call attempted — asserted via a fake `LLMProvider` that raises if called).

## 3. Integration tests (`backend/tests/integration/`)

Run against a **real** PostgreSQL + pgvector instance (via Docker Compose's `postgres` service in CI, or a local Postgres for dev) — not mocked, because the whole point of pgvector integration (index behavior, cosine distance operator, cascade deletes, migrations) can't be validated against a fake. The LLM/embedding *provider* is still faked or replaced with a deterministic local stub (see §5) to keep tests free, fast, and non-flaky.

Coverage:
- **Repository layer**: each repository's CRUD + `user_id` filtering, cascade deletes (deleting a document removes its chunks; deleting a user removes their documents/conversations), unique constraints (`document_id, chunk_index`).
- **pgvector queries**: similarity search returns results ordered correctly by cosine distance, HNSW index is used (via `EXPLAIN`), metadata filtering (`document_id IN (...)`) combined with the vector search returns correct scoped results.
- **Alembic migrations**: `alembic upgrade head` runs cleanly against a fresh database as part of the integration test fixture setup — a broken migration fails the suite immediately rather than being discovered later.
- **Document ingestion pipeline (service-level, real DB)**: upload → process (with faked embedding provider returning deterministic vectors) → assert chunks + embeddings persisted correctly, status transitions correctly, failure path leaves no orphaned chunks.
- **RAG pipeline (service-level, real DB, faked LLM)**: seed known chunks with known embeddings → ask a question → assert retrieval returns the expected chunks and the prompt sent to the (faked) `LLMProvider` contains them.
- **API endpoints**: `httpx.AsyncClient` against the FastAPI app with the real test database — auth flow (register/login/protected-route rejection), document CRUD including ownership enforcement (user A cannot fetch/delete user B's document → `404`), conversation/message flow including the SSE streaming endpoint (asserting event sequence: `token*`, `citations`, `done`).

## 4. End-to-end tests (`backend/tests/e2e/`)

Fewest in number, exercise the full real stack including a real (but cheap/small) call to the actual OpenAI API — gated behind an environment flag (`RUN_E2E_LLM_TESTS=1`) and a real API key, so they don't run by default in CI on every push (cost + flakiness), but can be run on demand and are required to pass before a release/tag.

Canonical flow tested:
```
register user → login → upload a small real PDF fixture → poll status until completed
  → create conversation → ask a question with a known answer in the fixture
  → assert streamed response contains expected content and non-empty citations
  → ask a question with no answer in the fixture
  → assert the fixed "not found" response and empty citations
```

This is the test that most directly validates the product's core promise end-to-end, which is why it's kept even though it's the slowest and most expensive category.

## 5. Deterministic LLM/embedding stubs for tests

To keep unit and integration tests fast, free, and non-flaky, a `FakeEmbeddingProvider` (returns a deterministic hash-based pseudo-embedding for a given text — same input always yields the same vector, distinct inputs yield distinct vectors, so similarity ordering in tests is stable and assertable) and a `FakeLLMProvider` (returns a fixed or template-driven string, optionally echoing which chunks were in the prompt so tests can assert on context inclusion) implement the domain ports (`EmbeddingProvider`, `LLMProvider`) and are wired in via the same `core/di.py` mechanism used for the real adapters (see [ARCHITECTURE.md](ARCHITECTURE.md) §6) — test configuration swaps the adapter, nothing else changes. This is the direct payoff of the ports-and-adapters boundary: it exists for testability as much as for provider-swapping.

## 6. Frontend tests

- Component tests (`vitest` + React Testing Library) for `DocumentUpload` (file validation feedback, drag-drop), `DocumentList` (status rendering), `ChatWindow` (message rendering, citation card display), and the streaming hook (`useStreamingAnswer`) against a mocked SSE source.
- No frontend E2E (Playwright/Cypress) in the MVP — noted as a reasonable addition post-MVP, but the backend E2E test already covers the critical user journey at the API level, and frontend E2E tooling/CI time is judged not worth the cost for a portfolio project's first release.

## 7. CI wiring

See [DEVOPS.md](DEVOPS.md) for the full pipeline; in summary, unit + integration tests (with a Postgres+pgvector service container, faked LLM/embedding providers) run on every push and PR. E2E-with-real-OpenAI and the full RAGAS evaluation (see [EVALUATION.md](EVALUATION.md)) run via manual `workflow_dispatch` only.

## 8. Definition of done for testing (per PR)

- New service/domain logic has unit tests covering the happy path and at least one failure/edge case.
- New repository methods or schema changes have an integration test exercising them against real Postgres.
- New API endpoints have at least one integration test per distinct status code they can return.
- No test relies on real network access to OpenAI outside the explicitly-gated E2E suite.

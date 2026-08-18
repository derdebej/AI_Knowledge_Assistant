# Architecture — AI Knowledge Assistant

## 1. Architectural style

**Layered architecture with ports & adapters (hexagonal) for external dependencies.** Full Domain-Driven Design (aggregates, event sourcing, CQRS) would be overengineering for this project's size — see [PROJECT_OVERVIEW.md §Guiding engineering principles](PROJECT_OVERVIEW.md). What we take from hexagonal architecture is narrow and deliberate: the four things the brief explicitly requires to be replaceable (embedding provider, LLM provider, vector store, document parser) are defined as interfaces in the domain layer and implemented in the infrastructure layer. Everything else is a straightforward service/repository layering.

```
Request → API layer → Service layer → Domain interfaces → Infrastructure adapters → External systems
                              ↓
                      Repository layer → PostgreSQL
```

## 2. Layers

### 2.1 API layer (`app/api/`)
FastAPI routers. Responsible for: HTTP concerns only — request parsing, response serialization, status codes, dependency injection (current user, DB session), and translating domain exceptions to HTTP errors. Contains **no business logic**. Routers call services and return Pydantic schemas.

### 2.2 Schemas (`app/schemas/`)
Pydantic v2 models for request/response validation, distinct from ORM models (`app/models/`). Keeps the API contract decoupled from the DB schema so either can evolve independently.

### 2.3 Service layer (`app/services/`)
Application/use-case orchestration: `DocumentService`, `IngestionService`, `ChatService`, `RetrievalService`, `AuthService`. Coordinates repositories + domain interfaces to fulfill a use case (e.g., "process an uploaded document" = parse → clean → chunk → embed → store). This is where business rules that don't belong to a single entity live. Framework-independent: services depend on domain interfaces and repository interfaces, never directly on `openai`, `langchain`, or SQLAlchemy session internals beyond the repository abstraction.

### 2.4 Domain layer (`app/domain/`)
Plain Python — no FastAPI, no SQLAlchemy, no LangChain imports. Contains:
- Entities/value objects that carry business meaning beyond the ORM row (e.g., `Chunk`, `RetrievedChunk` with a similarity score).
- **Ports** (interfaces) that infrastructure must implement:
  - `EmbeddingProvider` — `embed(texts: list[str]) -> list[list[float]]`
  - `LLMProvider` — `generate(prompt, ...) -> AsyncIterator[str]` (streaming) and a non-streaming variant
  - `VectorStore` — `upsert(chunks)`, `similarity_search(query_vector, top_k, filters) -> list[RetrievedChunk]`
  - `DocumentParser` — `extract(file_bytes, content_type) -> ExtractedDocument` (raw text + page metadata)
- Domain exceptions (`DocumentProcessingError`, `NoRelevantContextError`, etc.)

This is the layer that makes every "replaceable component" requirement concrete: swapping OpenAI embeddings for a local model means writing a new class that satisfies `EmbeddingProvider` and changing one line of dependency wiring — no other layer changes.

### 2.5 Infrastructure / adapters (`app/rag/`, `app/documents/`)
Concrete implementations of the domain ports:
- `app/rag/embeddings/openai_embedding_provider.py` implements `EmbeddingProvider` via the OpenAI SDK.
- `app/rag/llm/openai_llm_provider.py` implements `LLMProvider` via OpenAI chat completions (streaming).
- `app/rag/vector_store/pgvector_store.py` implements `VectorStore` via SQLAlchemy + pgvector.
- `app/rag/chunking/recursive_chunker.py` wraps LangChain's `RecursiveCharacterTextSplitter` behind a plain `Chunker` interface — this is the one place LangChain is intentionally used, because it is a well-tested utility, not a framework we build the app around.
- `app/documents/parsers/pdf_parser.py`, `txt_parser.py` implement `DocumentParser` (PDF via `pypdf`, optionally routed through LangChain's `PyPDFLoader` for consistency).
- `app/rag/prompting/` builds the system/user prompts (see [RAG_PIPELINE.md](RAG_PIPELINE.md) for the template and injection-defense structure). Pure string templating, no framework dependency.

### 2.6 Repositories (`app/repositories/`)
SQLAlchemy-backed data access, one repository per aggregate root: `UserRepository`, `DocumentRepository`, `ChunkRepository`, `ConversationRepository`, `MessageRepository`. Every read/write method takes or filters by `user_id` where applicable — this is the enforcement point for data isolation (NFR-4 in [REQUIREMENTS.md](REQUIREMENTS.md)), not just a UI-level filter.

### 2.7 Models (`app/models/`)
SQLAlchemy 2.0 declarative ORM models mapping 1:1 to the tables in [DATABASE.md](DATABASE.md).

### 2.8 Core (`app/core/`)
Cross-cutting concerns: settings (Pydantic `BaseSettings` reading env vars), JWT/password hashing utilities, structured logging setup, request-ID middleware, dependency-injection wiring (which concrete adapter implements which port — the single place this is decided), exception handlers.

### 2.9 `main.py`
FastAPI app factory: mounts routers, registers middleware (CORS, request ID, logging, exception handlers), configures OpenAPI metadata.

## 3. Backend module layout

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── documents.py       # upload, list, get, delete, status
│   │       ├── chat.py            # conversations, messages, streaming
│   │       ├── auth.py            # register, login
│   │       └── health.py          # liveness, readiness
│   ├── core/
│   │   ├── config.py              # Settings (env-driven)
│   │   ├── security.py            # JWT + password hashing
│   │   ├── logging.py             # structlog setup
│   │   ├── middleware.py          # request ID, timing
│   │   └── di.py                  # provider/adapter wiring
│   ├── domain/
│   │   ├── entities.py
│   │   ├── ports.py                # EmbeddingProvider, LLMProvider, VectorStore, DocumentParser, Chunker
│   │   └── exceptions.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── document_service.py
│   │   ├── ingestion_service.py
│   │   ├── retrieval_service.py
│   │   └── chat_service.py
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── document_repository.py
│   │   ├── chunk_repository.py
│   │   ├── conversation_repository.py
│   │   └── message_repository.py
│   ├── models/                    # SQLAlchemy ORM models
│   ├── schemas/                   # Pydantic request/response DTOs
│   ├── rag/
│   │   ├── embeddings/
│   │   ├── llm/
│   │   ├── vector_store/
│   │   ├── chunking/
│   │   └── prompting/
│   ├── documents/
│   │   └── parsers/
│   ├── db/
│   │   ├── session.py
│   │   └── base.py
│   └── main.py
├── alembic/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── Dockerfile
└── pyproject.toml
```

This deviates from the brief's suggested layout in two ways, both deliberate: `chat/` streaming logic lives inside `api/v1/chat.py` + `services/chat_service.py` rather than a separate top-level `chat/` package (SSE response construction is thin enough not to warrant its own module), and a `db/` package was added for session/engine setup since it's shared infrastructure, not a service.

## 4. Frontend module layout

```
frontend/
├── src/
│   ├── api/            # typed fetch/SSE client functions
│   ├── components/      # DocumentUpload, DocumentList, ChatWindow, CitationCard, ...
│   ├── pages/            # DocumentsPage, ChatPage, LoginPage
│   ├── hooks/             # useDocuments, useConversation, useStreamingAnswer
│   ├── types/              # generated/shared TS types mirroring backend schemas
│   ├── App.tsx
│   └── main.tsx
├── Dockerfile
└── package.json
```

## 5. Request flow examples

### 5.1 Document upload → processing

```
POST /api/v1/documents
  → api/v1/documents.py (auth dependency, multipart parsing)
  → DocumentService.upload(user, file)
      → validates size/type
      → DocumentRepository.create(status=pending)
      → schedules background processing (FastAPI BackgroundTasks for MVP; see §7)
  → returns 202 with document id + status=pending

[background]
  → IngestionService.process(document_id)
      → DocumentParser.extract()      (port)
      → text cleaning (pure function)
      → Chunker.split()               (port, LangChain-backed adapter)
      → EmbeddingProvider.embed()     (port)
      → VectorStore.upsert()          (port, pgvector-backed)
      → DocumentRepository.update(status=completed | failed)
```

### 5.2 Chat query

```
POST /api/v1/conversations/{id}/messages
  → api/v1/chat.py
  → ChatService.ask(user, conversation_id, question)
      → MessageRepository.save(role=user)
      → RetrievalService.retrieve(question, user_id, document_scope)
          → EmbeddingProvider.embed([question])   (port)
          → VectorStore.similarity_search(...)     (port)
          → filters by relevance threshold
      → prompt = build_prompt(question, retrieved_chunks)  (rag/prompting)
      → LLMProvider.generate(prompt, stream=True)  (port)
      → streams tokens to client via SSE
      → on completion: MessageRepository.save(role=assistant, citations=[...])
```

## 6. Replaceable components — summary

| Component | Interface (port) | MVP adapter | Alternative adapters (future) |
|---|---|---|---|
| Embeddings | `EmbeddingProvider` | OpenAI `text-embedding-3-small` | Cohere, local `sentence-transformers`, Azure OpenAI |
| LLM | `LLMProvider` | OpenAI `gpt-4o-mini` | Anthropic Claude, local via Ollama, Azure OpenAI |
| Vector store | `VectorStore` | pgvector (PostgreSQL) | Qdrant, Pinecone, Weaviate |
| Document parser | `DocumentParser` | `pypdf` / plain text | Unstructured.io, OCR-backed parser for scans |
| Chunker | `Chunker` | LangChain `RecursiveCharacterTextSplitter` | Semantic/embedding-based chunker |

Swapping any of these means: implement the port, register it in `core/di.py`, done — no changes to `services/`, `api/`, or `domain/`.

## 7. Async processing model (MVP decision)

> **Ambiguity resolved:** the brief lists Celery/RQ + Redis as a *future improvement*, but the ingestion pipeline must be asynchronous relative to the upload HTTP response (FR-2.6). Resolution: the MVP uses FastAPI's built-in `BackgroundTasks` for document processing — sufficient for a single-instance portfolio deployment, keeps the Docker Compose footprint small, and the `IngestionService` is written so that swapping the trigger mechanism (BackgroundTasks → Celery task) doesn't change its internals, only how it's invoked. This is documented as a known scaling limit, not hidden: see [ROADMAP.md §Future Improvements](ROADMAP.md).

## 8. Configuration & environment

All configuration is via environment variables loaded through a Pydantic `Settings` object (`app/core/config.py`), with `.env` for local development (never committed) and `.env.example` documenting every required variable. See [DEVOPS.md](DEVOPS.md) for the full variable list.

## 9. Why not LangGraph (MVP)

LangGraph earns its cost when a pipeline has cycles, multi-agent handoff, or conditional branching that a plain function call can't express cleanly. The MVP pipelines (§5.1, §5.2) are linear DAGs — extract → chunk → embed → store, and embed → search → prompt → generate. A dependency-injected sequence of service calls expresses this with less indirection and is easier to unit test. LangGraph is reconsidered post-MVP if we add multi-hop retrieval (retrieve → assess sufficiency → re-query) or agentic tool use — see [ROADMAP.md](ROADMAP.md) and [TECHNOLOGIES.md](TECHNOLOGIES.md).

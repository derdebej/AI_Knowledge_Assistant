# Project Overview — AI Knowledge Assistant

## What this is

A production-oriented Retrieval-Augmented Generation (RAG) platform. Users upload documents (PDF/TXT), the system extracts and indexes their content as vector embeddings in PostgreSQL/pgvector, and users ask natural-language questions that are answered strictly from the content of their own uploaded documents, with citations back to source passages.

This is explicitly **not** a "PDF + ChatGPT" wrapper demo. It is a portfolio-grade system meant to demonstrate:

- Real RAG architecture (ingestion pipeline, chunking strategy, vector search, grounded generation)
- Software engineering discipline (layered architecture, typed schemas, migrations, tests, CI/CD)
- Production concerns (auth, data isolation, observability, rate limiting, prompt injection defense)
- AI engineering judgment (documented, non-arbitrary choices for chunk size, embedding model, similarity metric, evaluation methodology)

## Why this project exists

The dual purpose is:

1. **Portfolio value** — a project that survives technical scrutiny from a senior engineer or hiring manager: the reader should be able to open any spec and find a specific decision with a specific reason, not a generic best-practices list.
2. **Learning value** — the build order is chosen so that each phase teaches a distinct, marketable skill (vector databases, retrieval pipelines, streaming APIs, evaluation of generative systems, containerized deployment) rather than front-loading UI work.

## Core user story

> As a user, I upload a set of documents. I ask a question in plain language. The assistant answers using only information found in my documents, shows me exactly which passages it used, and tells me honestly when it can't find an answer — instead of guessing from general knowledge.

## Non-goals (explicitly out of scope for this project)

- Multi-tenant SaaS billing / subscription management
- Real-time collaborative editing of documents
- General-purpose chatbot behavior unrelated to uploaded documents
- Support for arbitrary file formats beyond PDF/TXT in the MVP (DOCX, images, scanned OCR are post-MVP — see [ROADMAP.md](ROADMAP.md) §Future Improvements)
- High-availability / multi-region deployment (this is a portfolio project, not a company)

## Guiding engineering principles

1. **Replaceability over cleverness.** Embedding provider, LLM provider, vector store, and document parser are each behind an interface (see [ARCHITECTURE.md](ARCHITECTURE.md)). Swapping OpenAI for a local model should touch one adapter, not the domain layer.
2. **Decisions are documented, not defaulted.** Every non-obvious parameter (chunk size, Top-K, similarity metric, vector index type) has a rationale recorded in [RAG_PIPELINE.md](RAG_PIPELINE.md) or [DATABASE.md](DATABASE.md).
3. **Evidence over fluency.** The system is judged on whether answers are grounded and honestly flag missing information — not on how confident the prose sounds. See [RAG_PIPELINE.md §Grounding Strategy](RAG_PIPELINE.md) and [EVALUATION.md](EVALUATION.md).
4. **MVP first.** Section 15 of the original brief and [REQUIREMENTS.md](REQUIREMENTS.md) define a deliberately small MVP. Reranking, hybrid search, OCR, multi-user collections, and background job queues are named and deferred, not silently dropped — see [ROADMAP.md §Future Improvements](ROADMAP.md).
5. **No framework worship.** LangChain is used only where it removes real boilerplate (text splitting, PDF loading); it is confined to the infrastructure layer so the domain/service layer stays framework-independent and testable in isolation. LangGraph is not used in the MVP because the pipeline is a linear DAG with no cycles or multi-agent control flow — see [TECHNOLOGIES.md](TECHNOLOGIES.md) for the full reasoning.

## Primary personas

| Persona | Need |
|---|---|
| End user | Upload documents, ask questions, trust the answers, see sources |
| Reviewer (hiring manager / senior engineer) | Assess architecture quality, code quality, and AI engineering judgment quickly via specs + README |
| Future maintainer (you, in 6 months) | Understand why a decision was made without re-deriving it from scratch |

## Success criteria for the finished MVP

- A user can upload a PDF or TXT file and see it move from `pending` → `processing` → `completed`.
- A user can ask a question and receive a streamed, cited answer grounded in their documents within a few seconds for a small document set.
- Asking about information absent from the documents produces an explicit "not found in your documents" response rather than a hallucinated answer.
- The full stack runs via `docker compose up` with no manual steps beyond providing an OpenAI API key.
- CI runs lint, type checks, and unit/integration tests on every push.

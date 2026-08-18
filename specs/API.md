# API Design — AI Knowledge Assistant

Base path: `/api/v1`. All request/response bodies are JSON except upload (`multipart/form-data`) and message streaming (SSE, `text/event-stream`). All timestamps are ISO 8601 UTC. All IDs are UUIDv4 strings.

## 1. Authentication

Bearer JWT (`Authorization: Bearer <token>`), obtained via `POST /auth/login`. Every endpoint below except `POST /auth/register`, `POST /auth/login`, and the `/health/*` endpoints requires a valid token. The authenticated user's ID is resolved server-side from the token; it is never accepted as a request parameter, which is what makes the data-isolation guarantee in [DATABASE.md](DATABASE.md) §9 hold.

### `POST /auth/register`
Request:
```json
{ "email": "user@example.com", "password": "min-8-chars", "full_name": "Optional Name" }
```
Response `201`:
```json
{ "id": "uuid", "email": "user@example.com", "full_name": "Optional Name", "created_at": "2026-01-01T00:00:00Z" }
```
Errors: `409` email already registered · `422` validation (password too short, invalid email).

### `POST /auth/login`
Request (OAuth2 password form or JSON — JSON for this API):
```json
{ "email": "user@example.com", "password": "..." }
```
Response `200`:
```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600 }
```
Errors: `401` invalid credentials.

## 2. Documents

### `POST /documents`
Upload a document. `multipart/form-data`, field `file`.
Response `202 Accepted`:
```json
{
  "id": "uuid",
  "original_filename": "report.pdf",
  "content_type": "application/pdf",
  "file_size_bytes": 1048576,
  "status": "pending",
  "created_at": "2026-01-01T00:00:00Z"
}
```
`202` (not `201`) is deliberate: the resource is created, but processing is asynchronous — the body reflects that with `status: pending` and the client is expected to poll or re-fetch, not assume completion.

Errors: `400` unsupported file type · `413` file exceeds 20 MB · `422` missing file · `401` unauthenticated.

### `GET /documents`
Query params: `status` (optional filter), `limit` (default 20, max 100), `offset` (default 0).
Response `200`:
```json
{
  "items": [
    { "id": "uuid", "original_filename": "report.pdf", "status": "completed", "page_count": 12, "created_at": "..." }
  ],
  "total": 1, "limit": 20, "offset": 0
}
```

### `GET /documents/{document_id}`
Response `200`: full document record including `error_message` if `status=failed`.
Errors: `404` not found or not owned by the requester (identical response for both, to avoid leaking existence of other users' documents — see [SECURITY.md](SECURITY.md)).

### `GET /documents/{document_id}/status`
Lightweight polling endpoint, returns only `{ "id": "uuid", "status": "processing", "error_message": null }`. Separated from the full `GET` so clients polling every few seconds during processing send a minimal payload.

### `DELETE /documents/{document_id}`
Response `204`. Cascades to chunks (see [DATABASE.md](DATABASE.md) §3.2–3.3).
Errors: `404` not found/not owned.

## 3. Chat

### `POST /conversations`
Request:
```json
{ "document_ids": ["uuid", "uuid"] }
```
`document_ids` optional/omittable — empty means "search all of my completed documents" (FR-3.2). All IDs must belong to the requesting user (`400` otherwise).
Response `201`:
```json
{ "id": "uuid", "title": null, "document_ids": ["uuid", "uuid"], "created_at": "..." }
```

### `GET /conversations`
Query params: `limit`, `offset`.
Response `200`: paginated list, same shape as document listing, ordered by `updated_at desc`.

### `GET /conversations/{conversation_id}`
Response `200`: conversation metadata + `document_ids`.
Errors: `404` not found/not owned.

### `GET /conversations/{conversation_id}/messages`
Query params: `limit` (default 50), `offset`.
Response `200`:
```json
{
  "items": [
    {
      "id": "uuid", "role": "user", "content": "What was Q3 revenue?", "created_at": "..."
    },
    {
      "id": "uuid", "role": "assistant", "content": "According to [source 1]...", "created_at": "...",
      "citations": [
        { "document_id": "uuid", "document_name": "report.pdf", "page_number": 4, "chunk_id": "uuid", "similarity_score": 0.86, "rank": 1 }
      ]
    }
  ],
  "total": 2
}
```

### `POST /conversations/{conversation_id}/messages`
Sends a question and **streams** the answer. Request:
```json
{ "content": "What was Q3 revenue?" }
```
Response: `200`, `Content-Type: text/event-stream`. Event stream frames:
```
event: token
data: {"content": "According"}

event: token
data: {"content": " to"}

event: citations
data: {"citations": [{"document_id": "uuid", "document_name": "report.pdf", "page_number": 4, "chunk_id": "uuid", "similarity_score": 0.86, "rank": 1}]}

event: done
data: {"message_id": "uuid"}
```
Citations are sent as a single `citations` event once retrieval completes (before or interleaved with `token` events, implementation detail), and a final `done` event carries the persisted assistant message ID for the client to reconcile local state. On the "not found" short-circuit path (§5 of [RAG_PIPELINE.md](RAG_PIPELINE.md)), the stream emits a single `token` event with the fixed message and an empty `citations` array — no LLM call is made.

Errors (sent as an `error` SSE event, since headers are already committed once streaming starts):
```
event: error
data: {"detail": "Question exceeds maximum length"}
```
Pre-stream validation errors (empty question, conversation not found/not owned) are returned as normal JSON error responses with the appropriate status before the stream opens: `404` conversation not found/not owned · `422` empty/too-long question.

## 4. Health

### `GET /health`
Liveness — process is up. No DB call. Response `200`: `{ "status": "ok" }`.

### `GET /health/ready`
Readiness — verifies DB connectivity (`SELECT 1`) and that the `vector` extension is present. Response `200`: `{ "status": "ready", "database": "ok" }`. Response `503` if the DB check fails: `{ "status": "not_ready", "database": "error" }`. Used as the Docker Compose / orchestrator readiness probe (see [DEVOPS.md](DEVOPS.md)).

## 5. Error response shape (all endpoints)

```json
{ "detail": "Human-readable message", "error_code": "DOCUMENT_NOT_FOUND" }
```
FastAPI's default `{"detail": ...}` shape is kept for compatibility with its automatic OpenAPI docs and exception handling, extended with a stable `error_code` machine-readable field for frontend branching (e.g., distinguishing `INVALID_CREDENTIALS` from a generic `401`).

## 6. Status code conventions

| Code | Meaning in this API |
|---|---|
| 200 | Successful read or completed synchronous action |
| 201 | Resource created (auth register, conversation create) |
| 202 | Resource created, processing continues asynchronously (document upload) |
| 204 | Successful delete, no body |
| 400 | Malformed request semantics (e.g., referencing another user's document ID in `document_ids`) |
| 401 | Missing/invalid/expired auth token |
| 404 | Resource not found *or* not owned by the requester (never distinguished, to avoid enumeration) |
| 409 | Conflict (duplicate email at registration) |
| 413 | Upload exceeds size limit |
| 422 | Schema/field-level validation failure (Pydantic) |
| 429 | Rate limit exceeded (post-MVP, see [SECURITY.md](SECURITY.md)) |
| 500 | Unhandled server error (logged with request ID, generic message returned to client) |
| 503 | Readiness check failing |

## 7. Versioning

Path-prefixed (`/api/v1`) from day one, even though the MVP only has one version, so introducing a breaking v2 endpoint later doesn't require a migration of existing clients — cheap to do upfront, expensive to retrofit.

## 8. OpenAPI docs

FastAPI's generated OpenAPI schema is exposed at `/api/v1/openapi.json` with interactive docs at `/docs` (Swagger UI) — disabled in production builds via a settings flag (`ENABLE_DOCS=false`) since exposing full schema/route introspection publicly is unnecessary surface area for a project with no external API consumers (see [SECURITY.md](SECURITY.md)).

# DevOps — AI Knowledge Assistant

## 1. Containerization

### 1.1 Backend `Dockerfile` (multi-stage)

```
Stage 1 (builder): python:3.12-slim + uv/poetry install into a venv (no dev dependencies)
Stage 2 (runtime): python:3.12-slim, copy venv from builder, copy app code,
  run as non-root user, CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Rationale: multi-stage keeps the runtime image free of build toolchains; running as a non-root user is a baseline container-security practice worth demonstrating even at this scale.

### 1.2 Frontend `Dockerfile` (multi-stage)

```
Stage 1 (builder): node:20-slim, npm ci, npm run build (Vite production build)
Stage 2 (runtime): nginx:alpine, copy built static assets, copy a minimal nginx.conf
  that serves the SPA (fallback to index.html) and proxies /api to the backend service
```

### 1.3 Health checks

Both Dockerfiles declare a `HEALTHCHECK`:
- Backend: `curl -f http://localhost:8000/api/v1/health || exit 1`
- Frontend: `curl -f http://localhost/ || exit 1`

## 2. Docker Compose (local development)

`docker-compose.yml` services:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16       # ships pgvector pre-installed
    environment: [POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: pg_isready -U ${POSTGRES_USER}
    ports: ["5432:5432"]

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
    volumes: [uploads:/data/uploads]      # local file storage, see DATABASE.md §7
    ports: ["8000:8000"]
    healthcheck: curl -f http://localhost:8000/api/v1/health

  frontend:
    build: ./frontend
    depends_on: [backend]
    ports: ["5173:80"]

volumes:
  pgdata:
  uploads:
```

On first `docker compose up`, the backend container runs `alembic upgrade head` as an entrypoint step before starting `uvicorn`, so the schema (including `CREATE EXTENSION vector` and the HNSW index — see [DATABASE.md](DATABASE.md)) is always current with no manual step.

## 3. Environment variables

Documented in `.env.example` (committed, no real values) and mirrored in `app/core/config.py`'s `Settings`:

| Variable | Purpose | Required |
|---|---|---|
| `DATABASE_URL` | Postgres connection string | Yes |
| `OPENAI_API_KEY` | OpenAI API access | Yes |
| `EMBEDDING_MODEL` | Default `text-embedding-3-small` | No (has default) |
| `LLM_MODEL` | Default `gpt-4o-mini` | No (has default) |
| `JWT_SECRET_KEY` | JWT signing secret | Yes |
| `JWT_EXPIRE_MINUTES` | Default `60` | No |
| `MAX_UPLOAD_SIZE_MB` | Default `20` | No |
| `ALLOWED_ORIGINS` | CORS allowlist, comma-separated | Yes |
| `UPLOAD_STORAGE_PATH` | Default `/data/uploads` | No |
| `ENABLE_DOCS` | Toggle `/docs` exposure, default `true` locally / `false` recommended in prod | No |
| `LOG_LEVEL` | Default `INFO` | No |

## 4. GitHub Actions CI (`.github/workflows/ci.yml`)

Triggered on push and PR to `main`. Jobs:

```
lint-and-typecheck (backend):
  - ruff check .
  - ruff format --check .
  - mypy app/

lint-and-typecheck (frontend):
  - eslint .
  - tsc --noEmit

backend-tests:
  services: postgres (pgvector/pgvector:pg16, with healthcheck)
  steps:
    - alembic upgrade head (against the service container)
    - pytest tests/unit tests/integration --cov=app
  # E2E-with-real-OpenAI and RAGAS evaluation are NOT run here — see EVALUATION.md §4, TESTING.md §4/§7

frontend-tests:
  - vitest run

build-verification:
  - docker build ./backend
  - docker build ./frontend
  # confirms both images build cleanly; does not push anywhere in the MVP (no registry configured)
```

A separate, manually-triggered workflow (`workflow_dispatch`) runs `eval/run_eval.py` (see [EVALUATION.md](EVALUATION.md)) and the OpenAI-backed E2E suite (see [TESTING.md](TESTING.md) §4), since both cost real API calls and shouldn't gate every push.

## 5. What's deliberately not in the MVP DevOps setup

- **CD / automatic deployment** — no target environment exists for this project; CI stops at build verification. Documented as a natural extension, not built.
- **Container registry push** — would be added alongside an actual deployment target.
- **Kubernetes manifests / Helm charts** — explicitly listed as a future idea in [ROADMAP.md](ROADMAP.md); Compose is the right scale for a single-instance portfolio project.
- **Secrets manager integration** (Vault, AWS Secrets Manager) — env-var-based secrets are documented as the MVP posture in [SECURITY.md](SECURITY.md) §7 with the gap called out explicitly.

## 6. Local developer workflow

```
cp .env.example .env         # fill in OPENAI_API_KEY at minimum
docker compose up --build
# backend:  http://localhost:8000/docs
# frontend: http://localhost:5173
```

Backend-only development without Docker is also supported (Postgres via Compose, app run locally with `uvicorn app.main:app --reload` against `DATABASE_URL=postgresql://localhost:5432/...`) for faster iteration during active development — documented in the root [README.md](../README.md).

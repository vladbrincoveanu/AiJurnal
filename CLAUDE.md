# CLAUDE.md — AIJournal

## Project Overview

AIJournal is a personal memory stack that captures notes, files, and chat transcripts, stores them with semantic embeddings in PostgreSQL + pgvector, and enables natural-language querying via an OpenAI-compatible LLM. It consists of a FastAPI backend, a React/Vite frontend, a Redis-backed background worker, a browser extension, and CLI tooling.

## Repository Structure

```
AiJurnal/
├── backend/                        # Python FastAPI service
│   ├── app/
│   │   ├── main.py                 # FastAPI app, routes, auth middleware
│   │   ├── models.py               # SQLModel schemas (Event, EventCreate, EventRead)
│   │   ├── db.py                   # Async engine, session factory, init_db()
│   │   ├── worker.py               # RQ background worker entry point
│   │   ├── core/
│   │   │   └── config.py           # Pydantic Settings (env-driven config)
│   │   └── services/
│   │       ├── llm.py              # OpenAI wrappers (embedding, summary, chat)
│   │       ├── processing.py       # Async event processing (embedding + summary)
│   │       ├── tasks.py            # Redis Queue job enqueueing
│   │       └── content.py          # URL article fetching via Readability
│   ├── migrations/                 # Alembic migrations
│   │   ├── env.py                  # Alembic environment (async-aware)
│   │   └── versions/
│   │       └── 0001_create_events.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                       # React 18 + Vite + Tailwind
│   ├── src/
│   │   ├── App.tsx                 # Main UI (ingest form + semantic search)
│   │   ├── main.tsx                # Entry point with React Query provider
│   │   └── index.css               # Global styles
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── Dockerfile
├── extension/                      # Browser extension (Chrome/Firefox)
│   ├── manifest.json               # Manifest v2
│   ├── popup.html / popup.js       # Extension popup UI
│   ├── background.js               # Service worker + context menus
│   └── content-script.js           # Page content injection
├── capture/
│   └── bookmarklet.js              # Browser bookmarklet for quick capture
├── docker-compose.yml              # Full stack orchestration
├── Makefile                        # Build automation shortcuts
├── import_files.py                 # CLI file importer
├── .env.example                    # Environment variable template
└── README.md
```

## Tech Stack

| Layer        | Technology                                                         |
|--------------|--------------------------------------------------------------------|
| Backend      | Python 3.11, FastAPI 0.110, Uvicorn, SQLModel, SQLAlchemy 2 async |
| Database     | PostgreSQL 16 with pgvector (ankane/pgvector Docker image)         |
| Migrations   | Alembic 1.13 (async-aware via asyncpg)                             |
| Job Queue    | Redis 7.2 + RQ (Python Redis Queue)                               |
| LLM          | OpenAI SDK 1.30 (any OpenAI-compatible endpoint, inc. LM Studio)  |
| Content      | httpx, beautifulsoup4, readability-lxml                            |
| Frontend     | React 18, Vite 5, TypeScript 5.4, Tailwind CSS 3.4                |
| State Mgmt   | TanStack React Query 5, React hooks                               |
| HTTP Client  | Axios (frontend), httpx (backend)                                  |
| Containers   | Docker, Docker Compose                                             |

## Architecture

```
Browser/CLI/Extension
        │
        ▼
  FastAPI Backend ──▶ PostgreSQL + pgvector
   (port 8000)            (port 5432)
        │
        ▼
   Redis Queue ◀── RQ Worker
   (port 6379)     (background: embeddings + summaries)
        │
        ▼
  OpenAI-compatible LLM
  (local LM Studio or cloud)
```

**Request flow for ingestion:**
1. Client POSTs to `/api/ingest` with an `EventCreate` payload
2. Backend persists the `Event` row immediately (content, metadata, timestamps)
3. Backend enqueues `process_event` job on the Redis `ingest` queue
4. RQ worker picks up the job, computes embedding + summary via LLM, updates the row
5. Event is now searchable via vector similarity

**Request flow for search/chat:**
1. Client POSTs query to `/api/search` or `/api/chat`
2. Backend computes query embedding via LLM
3. pgvector cosine-distance search returns top-k events
4. For `/api/chat`: context is assembled and sent to LLM for a grounded answer

## API Routes

| Method   | Route                     | Auth | Description                                          |
|----------|---------------------------|------|------------------------------------------------------|
| `GET`    | `/health`                 | No   | DB health check                                      |
| `POST`   | `/api/ingest`             | Yes  | Persist event, enqueue background processing          |
| `POST`   | `/api/search`             | Yes  | Vector similarity search (returns `EventRead[]`)      |
| `POST`   | `/api/chat`               | Yes  | Context-aware chat with memory retrieval              |
| `DELETE`  | `/api/events/{event_id}` | Yes  | Delete event by UUID                                  |

**Authentication:** All `/api/*` routes require `APP_API_KEY` via `Authorization: Bearer <key>` or `X-API-Key: <key>` header.

## Data Model

Single table: `events`

| Column       | Type           | Notes                                      |
|--------------|----------------|--------------------------------------------|
| id           | UUID (PK)      | Auto-generated uuid4                        |
| created_at   | DateTime       | Defaults to utcnow                          |
| source_type  | String (enum)  | `chat`, `web`, `file`, `note`               |
| source_app   | String         | Free text: "browser-extension", "cli", etc. |
| title        | String         | Nullable                                    |
| url_or_path  | String         | Nullable, indexed                           |
| content      | Text           | Required                                    |
| summary      | Text           | Nullable, LLM-generated                     |
| metadata     | JSONB          | Nullable, GIN-indexed                       |
| embedding    | Vector(1536)   | Nullable, HNSW-indexed (cosine)             |

**Key indexes:**
- `ix_events_embedding_hnsw` — HNSW vector index (m=16, ef_construction=64, cosine ops)
- `ix_events_metadata_gin` — GIN index for JSONB queries
- `ix_events_url_or_path` — B-tree index

## Development Commands

### Docker (recommended)

```bash
cp .env.example .env        # Configure environment
make up                     # docker compose up --build (all 5 services)
make migrate                # Run Alembic migrations inside backend container
```

### Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload        # http://localhost:8000

# Frontend
cd frontend
npm install                          # or: make frontend-install
npm run dev                          # http://localhost:5173
```

### Useful checks

```bash
docker compose logs -f backend worker    # Monitor API + worker logs
docker compose exec db psql -U ai_journal -d ai_journal -c "\d+ events"  # Verify schema/indexes
```

## Environment Variables

Defined in `.env` (see `.env.example`):

| Variable           | Default                          | Purpose                              |
|--------------------|----------------------------------|--------------------------------------|
| `POSTGRES_USER`    | `ai_journal`                     | DB username                          |
| `POSTGRES_PASSWORD`| `ai_journal`                     | DB password                          |
| `POSTGRES_DB`      | `ai_journal`                     | DB name                              |
| `POSTGRES_HOST`    | `localhost`                      | DB host (overridden to `db` in Docker) |
| `POSTGRES_PORT`    | `5432`                           | DB port                              |
| `REDIS_URL`        | `redis://redis:6379/0`           | Redis connection string              |
| `APP_API_KEY`      | `change-me`                      | Shared API secret                    |
| `OPENAI_API_KEY`   | (empty for local LM Studio)     | OpenAI / compatible API key          |
| `OPENAI_BASE_URL`  | `http://localhost:1234/v1`       | LLM endpoint base URL                |
| `OPENAI_MODEL`     | `gpt-4o-mini`                    | Chat/summary model ID                |
| `EMBEDDING_MODEL`  | `text-embedding-3-small`         | Embedding model ID                   |

Frontend env vars (in `frontend/.env.local`):
- `VITE_API_BASE` — API URL (default: `http://localhost:8000/api`)
- `VITE_APP_API_KEY` — API key for frontend requests

## Code Conventions

### Python (backend)

- **Async-first**: All I/O uses `async`/`await` (asyncpg, httpx, OpenAI SDK)
- **Type hints**: PEP 484 annotations on all functions
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Config**: Centralized in `app/core/config.py` via `pydantic-settings`, accessed through `get_settings()` (cached with `@lru_cache`)
- **Dependency injection**: FastAPI `Depends()` for DB sessions and auth
- **Schemas**: `EventBase` (shared fields), `Event` (table=True), `EventCreate` (input), `EventRead` (output)
- **Logging**: `structlog` throughout — use `structlog.get_logger()`, log with keyword args (e.g., `logger.info("event.created", event_id=id)`)
- **Services layer**: Business logic in `app/services/`, routes in `app/main.py`
- **Background jobs**: Enqueue with `enqueue_event_processing()`, worker runs `asyncio.run()` wrapper around async processing

### TypeScript (frontend)

- **Functional components** with React hooks (`useState`, `useMemo`, `useMutation`)
- **Naming**: `camelCase` for variables/functions, `PascalCase` for components/types
- **Styling**: Tailwind utility classes, dark theme (slate-950 base)
- **API calls**: Axios instance with interceptors for auth headers
- **State**: TanStack React Query mutations for API interactions

### Migrations

- Alembic migrations in `backend/migrations/versions/`
- Naming: `NNNN_description.py` (e.g., `0001_create_events.py`)
- Migration env is async-aware (uses the same async engine as the app)
- Run with: `make migrate` or `docker compose run --rm backend alembic upgrade head`
- Always include both `upgrade()` and `downgrade()` functions

### General

- No test framework is currently configured
- No linter/formatter config files present — follow existing code style
- `from __future__ import annotations` used at the top of all Python files
- Docker volumes mount source code for hot-reload during development
- The pgvector extension is auto-created at DB init and in the first migration

## Key File Quick Reference

| What you need                     | Where to look                          |
|-----------------------------------|----------------------------------------|
| API routes and request handling   | `backend/app/main.py`                  |
| Data models and schemas           | `backend/app/models.py`                |
| Database connection/session       | `backend/app/db.py`                    |
| App configuration                 | `backend/app/core/config.py`           |
| LLM integration (embed/summary)  | `backend/app/services/llm.py`          |
| Background job processing         | `backend/app/services/processing.py`   |
| Job queue setup                   | `backend/app/services/tasks.py`        |
| URL content extraction            | `backend/app/services/content.py`      |
| Worker entry point                | `backend/app/worker.py`                |
| Database migrations               | `backend/migrations/versions/`         |
| Frontend UI                       | `frontend/src/App.tsx`                 |
| Docker orchestration              | `docker-compose.yml`                   |
| Environment template              | `.env.example`                         |
| Build automation                  | `Makefile`                             |

## Common Tasks for AI Assistants

### Adding a new API route
1. Define request/response Pydantic models in `backend/app/main.py` (or a separate schemas file)
2. Add the route function in `backend/app/main.py` with `Depends(verify_api_key)` and `Depends(get_session)`
3. If complex logic is needed, add a service function in `backend/app/services/`

### Adding a new database column
1. Add the field to `EventBase` in `backend/app/models.py`
2. Create a new Alembic migration: `docker compose run --rm backend alembic revision -m "description"`
3. Write `upgrade()` and `downgrade()` in the generated migration file
4. Run: `make migrate`

### Adding a new background job
1. Write the async processing function in `backend/app/services/processing.py`
2. Add a sync wrapper using `asyncio.run()` in `backend/app/services/tasks.py`
3. Enqueue via `_queue().enqueue(job_func, args, job_timeout=600)`

### Modifying the frontend
1. Edit `frontend/src/App.tsx` (currently single-component)
2. Use Tailwind utility classes consistent with the dark slate theme
3. API calls go through the `client` Axios instance (auto-attaches auth headers)

### Changing LLM behavior
1. Embedding: `backend/app/services/llm.py` → `get_embedding()`
2. Summarization prompt: `backend/app/services/llm.py` → `generate_summary()`
3. Chat system prompt: `backend/app/main.py` → `chat_with_memory()` route
4. Model selection: `.env` → `OPENAI_MODEL` and `EMBEDDING_MODEL`

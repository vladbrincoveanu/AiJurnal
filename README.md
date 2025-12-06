# AIJournal

AIJournal is a personal memory stack that collects notes, files, and chat transcripts, stores them with semantic metadata, and lets you query everything with natural language. The backend is a FastAPI service backed by PostgreSQL + pgvector for similarity search, and summarized/contextualized with OpenAI-compatible models. A Vite/React frontend and a lightweight CLI importer sit on top of the API so you can ingest content and chat with your own history.

## Architecture

- **Backend** — FastAPI + SQLModel service (`backend/app`) with async SQLAlchemy sessions, pgvector similarity search, structured logging via structlog, and OpenAI chat/embedding helpers (`app/services/llm.py`).
- **Database** — PostgreSQL 16 w/ `pgvector` (docker image `ankane/pgvector`) stores `events` records (source metadata, summaries, embeddings). Alembic migrations live in `backend/migrations`.
- **LLM providers** — The backend talks to any OpenAI-compatible endpoint. By default `OPENAI_BASE_URL` points to `http://localhost:1234/v1` so you can target a local model or swap in the real API keys.
- **Frontend** — React 18 + React Query + Tailwind (Vite) client (`frontend/`) for browsing/searching memory. Run with Vite dev server and point it at the API.
- **CLI importer** — `import_files.py` walks directories, skips binaries, and POSTs file contents to `/api/ingest` with metadata.

## Getting Started

### 1. Configure environment

```bash
cp .env.example .env
# edit APP_API_KEY, OPENAI_* and Postgres settings as needed
```

Key env vars (`backend/app/core/config.py`):

- `APP_API_KEY` — shared secret required on all `/api/*` routes via the `X-API-Key` header.
- `POSTGRES_*` — database host/user/password/db/port.
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `EMBEDDING_MODEL` — point to your LLM provider.

### 2. Run with Docker

```bash
make up      # or: docker compose up --build
make migrate # runs alembic upgrade head inside the backend container
```

Services:

- `db` (ankane/pgvector) exposes `POSTGRES_PORT` (default 5432)
- `backend` runs `uvicorn app.main:app` on port 8000

Visit `http://localhost:8000/docs` for the FastAPI docs once the stack is up.

### 3. Local development without Docker (optional)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Point the backend to your local Postgres (`pgvector` extension required) by editing `.env`.

## React frontend

```bash
cd frontend
npm install        # or: make frontend-install
npm run dev        # serves http://localhost:5173
```

Set `VITE_API_BASE` (or similar) in a future `.env` file if the frontend expects a non-default API URL. During development, proxy requests to `http://localhost:8000`.

## CLI ingestion helper

```bash
APP_API_KEY=change-me python import_files.py ~/Documents/journal
```

The script (see `import_files.py`) recursively walks text files, strips binaries, and POSTs payloads shaped like:

```json
{
  "source_type": "file",
  "source_app": "cli",
  "title": "meeting-notes.txt",
  "url_or_path": "/Users/me/meeting-notes.txt",
  "content": "...",
  "metadata": {"size": 1234}
}
```

You can also ingest manually with `curl`:

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "X-API-Key: ${APP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"note","source_app":"web","title":"Daily standup","content":"..."}'
```

## API surface

| Method | Route | Description |
| ------ | ----- | ----------- |
| `GET /health` | Basic DB health check. |
| `POST /api/ingest` | Persist an event (`EventCreate` schema). Triggers async summarization + embedding job. |
| `POST /api/search` | Returns the most similar events to a query (vector cosine distance). |
| `POST /api/chat` | Builds a contextual prompt from relevant events then streams a chat-completion answer. |
| `DELETE /api/events/{event_id}` | Deletes an event by UUID. |

`POST /api/search` accepts:

```json
{ "query": "project alpha decisions", "limit": 5 }
```

`POST /api/chat` extends that with optional `history` (array of `{role, content}`) so you can preserve multi-turn interactions.

## Data model

Events (`backend/app/models.py`) capture:

- `source_type` (`chat`, `web`, `file`, `note`)
- `source_app` (free text: “slack”, “browser-extension”, etc.)
- `title`, `url_or_path`, raw `content`
- Generated `summary`
- JSON `metadata`
- `embedding` vector (`Vector(1536)`) for similarity search

Indexes:

- `ix_events_embedding_hnsw` — pgvector HNSW index for fast cosine similarity.
- `ix_events_metadata_gin` — GIN index for querying metadata payloads.

## Development notes

- App auto-initializes the schema at startup (`app.db.init_db`), so a fresh Docker stack seeds tables automatically.
- Background tasks compute embeddings and summaries after ingestion. If you switch models, existing rows can be reprocessed by clearing `summary`/`embedding`.
- Structlog is pre-configured; set `LOG_LEVEL` via standard logging env vars if needed.
- Alembic is already wired (see `backend/alembic.ini`); run migrations through `make migrate`.

## Troubleshooting

- **DB fails health check** — ensure the docker `db` container is healthy (`docker compose ps`) and that `POSTGRES_HOST` is reachable from the backend container (use `db` when running inside Compose).
- **OpenAI auth errors** — confirm `OPENAI_API_KEY`/`OPENAI_BASE_URL` are present in `.env`, and that the model IDs match what your provider exposes.
- **Vector extension missing** — if you run Postgres outside Docker, install the `pgvector` extension and run `CREATE EXTENSION IF NOT EXISTS vector;`.

Happy journaling!

# AIJournal

AIJournal is a personal memory stack that collects notes, files, and chat transcripts, stores them with semantic metadata, and lets you query everything with natural language. The backend is a FastAPI service backed by PostgreSQL + pgvector for similarity search, and summarized/contextualized with OpenAI-compatible models. A Vite/React frontend and a lightweight CLI importer sit on top of the API so you can ingest content and chat with your own history.

## Architecture

- **Backend** — FastAPI + SQLModel service (`backend/app`) with async SQLAlchemy sessions, pgvector similarity search, structured logging via structlog, and OpenAI chat/embedding helpers (`app/services/llm.py`).
- **Database** — PostgreSQL 16 w/ `pgvector` (docker image `ankane/pgvector`) stores `events` records (source metadata, summaries, embeddings). Alembic migrations live in `backend/migrations`.
- **Job queue** — Redis + RQ worker (`app/worker.py`) process ingestion jobs out-of-band so embeddings/summaries don't block requests.
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
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `EMBEDDING_MODEL` — point to your LLM provider. Leave `OPENAI_API_KEY` blank when targeting a local LM Studio server and set `OPENAI_BASE_URL=http://host.docker.internal:1234/v1` so Docker containers can reach a model served on the host machine.
- When running via Docker Compose, the backend/worker services override `POSTGRES_HOST=db` internally even if `.env` uses `localhost`, ensuring database connections succeed inside the network.
- `REDIS_URL` — queue connection string (Docker Compose uses `redis://redis:6379/0`).

### 2. Run with Docker

```bash
make up      # or: docker compose up --build
make migrate # runs alembic upgrade head inside the backend container
```

Services:

- `db` (ankane/pgvector) exposes `POSTGRES_PORT` (default 5432)
- `redis` provides the queue backend
- `backend` runs `uvicorn app.main:app` on port 8000
- `worker` runs `python -m app.worker` to drain the ingestion queue
- `frontend` runs the Vite dev server on port 5173
- The optional browser extension targets Firefox ≥140 / Firefox for Android ≥142 because of the `browser_specific_settings.gecko.data_collection_permissions` requirement.

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

### Expose `/api/ingest` securely

- **Recommended:** run a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/) from your LAN server and map `https://yourdomain.com/api` → `http://localhost:8000/api`.
- **Quick testing:** use [ngrok](https://ngrok.com/) (`ngrok http 8000`) and restrict the tunnel to your IP.
- **Public deploy:** host the Docker Compose stack on a VPS and terminate TLS with Caddy/Traefik/Nginx.

Whichever path you choose, keep the API key secret and rotate it if sharing the URL with third parties.

### Authentication

All `/api/*` routes enforce the shared `APP_API_KEY`. Provide it via either:

- `Authorization: Bearer <APP_API_KEY>`
- or `X-API-Key: <APP_API_KEY>` (legacy compat; still supported)

Bookmarklets, mobile shortcuts, and CLI helpers can send both headers for redundancy.

### Background jobs

`/api/ingest` responds immediately after persisting the event, then enqueues `process_event` on the Redis-backed queue. The dedicated worker (`app/worker.py`) computes embeddings + summaries asynchronously. Monitor worker logs (`docker compose logs -f worker`) to ensure jobs complete and pgvector indexes stay healthy.

## React frontend

```bash
cd frontend
npm install        # or: make frontend-install
npm run dev        # serves http://localhost:5173
```

Set `VITE_API_BASE` (or similar) in a future `.env` file if the frontend expects a non-default API URL. Optionally provide `VITE_APP_API_KEY` so the Vite dev server can forward auth headers automatically. During development, proxy requests to `http://localhost:8000`.

## Browser extension

A Chrome/Edge/Firefox extension lives under `extension/`:

```
extension/
├── manifest.json
├── popup.html
├── popup.css
├── popup.js
└── content-script.js
```

It grabs the current tab's title, URL, and highlighted text, saves API settings locally, and POSTs to `/api/ingest` with the proper headers plus metadata such as `captured_at`, `user_agent`, and `favIconUrl`. If no text is selected, the backend Readability fetch still runs (so you can just click save).

To use it:

1. **Chrome/Edge**: open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and pick the `extension/` directory.
2. **Firefox**: run `web-ext build` from the `extension/` directory or zip its contents manually, then upload/sign via [addons.mozilla.org](https://addons.mozilla.org/en-US/developers/addon/submit/upload-listed). The manifest includes `browser_specific_settings` so AMO can assign an ID.
3. Open the popup, enter your API base (e.g., `https://your-tunnel/api`) and `APP_API_KEY`, then click **Save config**.
4. Select text on any page and hit **Save to AIJournal**; watch `docker compose logs backend worker` for confirmation.
5. Right-click anywhere on a page (or selection) and choose **Save to AIJournal** from the context menu for a true one-click capture; the extension bundles page title, URL, highlighted text, plain text, and a truncated HTML snapshot in the payload.

### Local LM Studio setup

1. Launch [LM Studio](https://lmstudio.ai) and load your tuned OSS 20B model.
2. Start the local server (`Server` tab → `Start Server`) with the OpenAI-compatible API enabled on port `1234` (or another port).
3. Note the model IDs LM Studio exposes (e.g., `oss-20b-chat`, `oss-20b-embed`). Update `.env`:
   ```env
   OPENAI_API_KEY=
   OPENAI_BASE_URL=http://host.docker.internal:1234/v1
   OPENAI_MODEL=oss-20b-chat
   EMBEDDING_MODEL=oss-20b-embed
   ```
4. Restart `docker compose up --build`. The backend/worker containers use `host.docker.internal` to reach LM Studio running on the host OS; no OpenAI key is required.
   - After adding new Python dependencies (e.g., Readability's `lxml-html-clean`), rebuild the Python images explicitly: `docker compose build backend worker && docker compose up`.

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
  -H "Authorization: Bearer ${APP_API_KEY}" \
  -H "X-API-Key: ${APP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"note","source_app":"web","title":"Daily standup","content":"..."}'
```

## Capture layer

### Desktop bookmarklet

`capture/bookmarklet.js` contains a ready-to-edit script. Set `API_BASE` to your API host **without** the `/api` suffix (the script appends `/api/ingest` automatically), replace `API_KEY`, minify (or wrap with `javascript:(function(){ ... })();`), and save as the URL of a new bookmark in your browser. Example one-liner:

```javascript
javascript:(() => {const key='change-me';const base='https://your-api.example.com'.replace(/\/+$/,'');const body={source_type:'web',source_app:'bookmarklet',title:document.title,url_or_path:location.href,content:window.getSelection().toString(),metadata:{captured_at:new Date().toISOString(),user_agent:navigator.userAgent}};fetch(`${base}/api/ingest`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${key}`,'X-API-Key':key},body:JSON.stringify(body)}).then(r=>alert(r.ok?'🧠 Saved':'❌ Error')).catch(()=>alert('❌ Network error'));})();
```

If the selection is empty, the backend now auto-fetches the article (Readability) using the page URL, extracts the title + clean text, and stores it.

### Mobile share sheet

- **iOS Shortcut**
  1. Create a new Shortcut → "Receive Any" from Share Sheet.
  2. Add *Get Contents of URL* → Method `POST`, URL `https://your-api.example.com/api/ingest`.
  3. Body (JSON):
     ```json
     {
       "source_type": "web",
       "source_app": "ios-shortcut",
       "title": "{{Title}}",
       "url_or_path": "{{URL}}",
       "content": "{{Input}}",
       "metadata": { "captured_at": "{{CurrentDate}}" }
     }
     ```
  4. Headers: `Authorization: Bearer ${APP_API_KEY}`, `X-API-Key: ${APP_API_KEY}`, `Content-Type: application/json`.
  5. Finish with a "Show Result" action for success/failure feedback.

- **Android**
  1. Install [HTTP Shortcuts](https://androidappsapk.co/detail-http-shortcuts/) (or similar).
  2. Create a shortcut → Method `POST`, URL `https://your-api.example.com/api/ingest`.
  3. Body identical to above; map `${selection}` / `${url}` variables.
  4. Add headers for the API key.

Now sharing from Safari/Chrome/Twitter/etc. sends the page or selected text straight into AIJournal.

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
- Verify pgvector indexes with `docker compose exec db psql -U ai_journal -d ai_journal -c "\d+ events"`—look for `ix_events_embedding_hnsw` + `ix_events_metadata_gin`.
- Background tasks compute embeddings and summaries after ingestion. If you switch models, existing rows can be reprocessed by clearing `summary`/`embedding`.
- If an ingest request arrives with an empty `content` but a `url_or_path`, the backend fetches + parses the article (Readability) before storing the event.
- Structlog is pre-configured; set `LOG_LEVEL` via standard logging env vars if needed.
- Alembic is already wired (see `backend/alembic.ini`); run migrations through `make migrate`.

## Troubleshooting

- **DB fails health check** — ensure the docker `db` container is healthy (`docker compose ps`) and that `POSTGRES_HOST` is reachable from the backend container (use `db` when running inside Compose).
- **OpenAI auth errors** — confirm `OPENAI_API_KEY`/`OPENAI_BASE_URL` are present in `.env`, and that the model IDs match what your provider exposes.
- **Vector extension missing** — if you run Postgres outside Docker, install the `pgvector` extension and run `CREATE EXTENSION IF NOT EXISTS vector;`.
- **Queue stalled** — confirm Redis is reachable (`redis-cli -u $REDIS_URL ping`) and that `docker compose logs worker` shows jobs being processed.

Happy journaling!

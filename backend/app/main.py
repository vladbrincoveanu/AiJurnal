from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db import get_session, init_db
from app.models import Event, EventCreate, EventRead, SourceType
from app.services.content import fetch_article
from app.services.llm import chat_completion, get_embedding
from app.services.tasks import enqueue_event_processing

logger = structlog.get_logger()
settings = get_settings()


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class ChatRequest(BaseModel):
    query: str
    history: list[dict[str, Any]] = []
    limit: int = 5


def _extract_bearer(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    scheme, _, value = token.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value
    return None


async def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> None:
    expected = settings.api_key
    provided = x_api_key or _extract_bearer(authorization)
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan, title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(select(1))
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover - simple health check
        logger.exception("health_check.failed", error=str(exc))
        raise HTTPException(status_code=500, detail="unhealthy")


@app.post("/api/ingest")
async def ingest_event(
    event_data: EventCreate,
    session: AsyncSession = Depends(get_session),
    _: Any = Depends(verify_api_key),
):
    if (
        (not event_data.content or not event_data.content.strip())
        and event_data.url_or_path
    ):
        article = await fetch_article(event_data.url_or_path)
        if article:
            event_data.content = article.content
            if not event_data.title and article.title:
                event_data.title = article.title

    metadata_values = event_data.metadata_ or {}
    if metadata_values is None:
        metadata_values = {}
    metadata_values = dict(metadata_values)
    metadata_values.setdefault("captured_at", datetime.utcnow().isoformat())
    event_data.metadata_ = metadata_values

    event = Event(**event_data.dict(by_alias=True))
    session.add(event)
    await session.commit()
    await session.refresh(event)
    enqueue_event_processing(str(event.id))
    return {"status": "received", "id": str(event.id)}


@app.post("/api/search", response_model=list[EventRead])
async def search_events(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    _: Any = Depends(verify_api_key),
):
    query_vector = await get_embedding(request.query)
    stmt = (
        select(Event)
        .where(Event.embedding.isnot(None))
        .order_by(Event.embedding.cosine_distance(query_vector))
        .limit(request.limit)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()
    return [EventRead.model_validate(e, from_attributes=True) for e in events]


@app.post("/api/chat")
async def chat_with_memory(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    _: Any = Depends(verify_api_key),
):
    query_vector = await get_embedding(request.query)
    stmt = (
        select(
            Event,
            Event.embedding.cosine_distance(query_vector).label("distance"),
        )
        .where(Event.embedding.isnot(None))
        .order_by(Event.embedding.cosine_distance(query_vector))
        .limit(request.limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    relevant_events: list[Event] = [row[0] for row in rows]
    distances = [float(row[1]) if row[1] is not None else None for row in rows]

    if not relevant_events:
        return {"answer": "I don't have relevant context yet.", "sources": []}

    context_str = "\n\n".join(
        [
            f"Source ({e.source_type}): {e.title or 'Untitled'}\nContent: "
            f"{(e.summary or e.content or '')[:500]}..."
            for e in relevant_events
        ]
    )
    system_prompt = (
        "You are a helpful personal memory assistant. "
        "Answer the user's question based ONLY on the provided context from their saved history. "
        'If the answer is not in the context, say "I do not recall that from your saved history."'
        f"\n\n--- CONTEXT START ---\n{context_str}\n--- CONTEXT END ---"
    )

    answer = await chat_completion(system_prompt, request.query, request.history)

    sources = []
    for event, distance in zip(relevant_events, distances):
        sources.append(
            {
                "id": str(event.id),
                "title": event.title or "Untitled",
                "source_type": event.source_type,
                "similarity_score": distance,
            }
        )

    return {"answer": answer, "sources": sources}


@app.delete("/api/events/{event_id}")
async def delete_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
    _: Any = Depends(verify_api_key),
):
    stmt = delete(Event).where(Event.id == event_id)
    await session.execute(stmt)
    await session.commit()
    return {"status": "deleted", "id": event_id}

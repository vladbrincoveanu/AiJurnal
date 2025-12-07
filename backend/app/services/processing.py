from __future__ import annotations

import structlog

from app.db import async_session
from app.models import Event
from app.services.llm import generate_summary, get_embedding

logger = structlog.get_logger()


async def process_event(event_id: str) -> None:
    async with async_session() as session:
        event = await session.get(Event, event_id)
        if not event:
            logger.warning("process_event.missing", event_id=event_id)
            return

        text = event.content or ""

        if not event.embedding:
            event.embedding = await get_embedding(text)
        if not event.summary:
            event.summary = await generate_summary(text)

        session.add(event)
        await session.commit()
        logger.info("process_event.complete", event_id=str(event_id))

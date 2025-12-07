from __future__ import annotations

import asyncio
from functools import lru_cache

from redis import Redis
from rq import Queue

from app.core.config import get_settings
from app.services.processing import process_event

settings = get_settings()
QUEUE_NAME = "ingest"


@lru_cache
def _queue() -> Queue:
    connection = Redis.from_url(settings.redis_url)
    return Queue(QUEUE_NAME, connection=connection)


def enqueue_event_processing(event_id: str) -> None:
    _queue().enqueue(process_event_job, event_id, job_timeout=600)


def process_event_job(event_id: str) -> None:
    asyncio.run(process_event(event_id))

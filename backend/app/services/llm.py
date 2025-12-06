from __future__ import annotations

import structlog
from functools import lru_cache
from typing import Any, List

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@lru_cache
def _client() -> AsyncOpenAI:
    api_key = settings.openai_api_key or "EMPTY"
    return AsyncOpenAI(api_key=api_key, base_url=settings.openai_base_url)


async def get_embedding(text: str) -> List[float]:
    cleaned = _truncate(text)
    resp = await _client().embeddings.create(
        input=cleaned,
        model=settings.embedding_model,
    )
    return resp.data[0].embedding


async def generate_summary(text: str) -> str:
    cleaned = _truncate(text)
    prompt = (
        "Summarize the following text in 3-5 sentences. "
        "Focus on key facts, decisions, and entities."
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": cleaned},
    ]
    resp = await _client().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""


async def chat_completion(
    system_prompt: str, user_query: str, history: list[dict[str, Any]]
) -> str:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_query})
    resp = await _client().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def _truncate(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]

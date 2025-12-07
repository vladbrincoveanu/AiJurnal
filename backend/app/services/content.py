from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog
from bs4 import BeautifulSoup
from readability import Document

logger = structlog.get_logger()

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
)
MAX_CHARS = 20000


@dataclass
class Article:
    title: str | None
    content: str


async def fetch_article(url: str) -> Article | None:
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("fetch_article.http_error", url=url, error=str(exc))
        return None

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type:
        logger.warning("fetch_article.unsupported_content_type", url=url, content_type=content_type)
        return None

    doc = Document(resp.text)
    article_title = (doc.short_title() or doc.title() or "").strip() or None
    summary_html = doc.summary()
    soup = BeautifulSoup(summary_html, "html.parser")
    text = soup.get_text(separator="\n")
    cleaned = text.strip()

    if not cleaned:
        logger.warning("fetch_article.empty", url=url)
        return None

    truncated = cleaned[:MAX_CHARS]
    return Article(title=article_title, content=truncated)

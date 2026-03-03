"""
RSS feed fetcher.

Uses httpx for async HTTP + feedparser for RSS/Atom parsing.
Deduplicates against the database before returning new items.
"""

import logging
from datetime import datetime, timezone
from typing import List

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NewsItem

logger = logging.getLogger(__name__)
settings = get_settings()

# Request headers to avoid being blocked by feed servers
REQUEST_HEADERS = {
    "User-Agent": (
        "AuditChain-ContentEngine/1.0 "
        "(AI governance news monitoring; https://auditchain.io)"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


async def fetch_feed(
    feed_name: str,
    feed_url: str,
    client: httpx.AsyncClient,
) -> List[dict]:
    """
    Fetch and parse a single RSS/Atom feed.

    Args:
        feed_name: Human-readable name for the feed source.
        feed_url: The URL of the RSS feed.
        client: Shared httpx async client.

    Returns:
        List of raw item dicts with keys: title, url, summary, published_at.
    """
    try:
        logger.info(f"Fetching feed: {feed_name} ({feed_url})")
        response = await client.get(feed_url, headers=REQUEST_HEADERS, timeout=20.0)
        response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.error(f"Failed to fetch feed '{feed_name}': {e}")
        return []

    parsed = feedparser.parse(response.text)

    if parsed.bozo and not parsed.entries:
        logger.warning(f"Feed parse error for '{feed_name}': {parsed.bozo_exception}")
        return []

    items = []
    for entry in parsed.entries[: settings.max_news_items_per_feed]:
        # Normalize published date
        pub_date = _parse_feed_date(entry)

        items.append(
            {
                "feed_name": feed_name,
                "title": _clean_text(entry.get("title", "No title")),
                "url": entry.get("link", ""),
                "summary": _clean_text(
                    entry.get("summary", entry.get("description", ""))
                )[:2000],
                "published_at": pub_date,
            }
        )

    logger.info(f"Fetched {len(items)} items from '{feed_name}'")
    return items


async def fetch_all_feeds(db: AsyncSession) -> List[NewsItem]:
    """
    Fetch all configured RSS feeds and persist new items to the database.

    Already-seen URLs are skipped (deduplication by URL).

    Args:
        db: AsyncSession for DB operations.

    Returns:
        List of newly inserted NewsItem objects.
    """
    new_items: List[NewsItem] = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for feed_name, feed_url in settings.rss_feeds.items():
            raw_items = await fetch_feed(feed_name, feed_url, client)

            for raw in raw_items:
                if not raw["url"]:
                    continue

                # Deduplicate by URL
                stmt = select(NewsItem).where(NewsItem.url == raw["url"])
                result = await db.execute(stmt)
                if result.scalar_one_or_none():
                    continue  # Already seen

                item = NewsItem(**raw)
                db.add(item)
                new_items.append(item)

    await db.flush()

    # Refresh all new items to get their IDs
    for item in new_items:
        await db.refresh(item)

    logger.info(f"RSS scan complete: {len(new_items)} new items across all feeds")
    return new_items


async def get_unanalyzed_items(db: AsyncSession, limit: int = 50) -> List[NewsItem]:
    """
    Return news items that haven't yet been scored for relevance.

    Args:
        db: AsyncSession.
        limit: Maximum number of items to return.

    Returns:
        List of NewsItem records with null relevance_score.
    """
    stmt = (
        select(NewsItem)
        .where(NewsItem.relevance_score.is_(None))
        .order_by(NewsItem.fetched_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_feed_date(entry: feedparser.FeedParserDict) -> datetime | None:
    """Extract and normalize the published date from a feed entry."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        ts = entry.get(field)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _clean_text(text: str) -> str:
    """Strip HTML tags and excessive whitespace from feed text."""
    import re
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

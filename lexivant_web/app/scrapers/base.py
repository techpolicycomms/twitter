"""Base scraper with robots.txt compliance and deduplication."""
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegulationItem, ScrapeRun

logger = logging.getLogger(__name__)

USER_AGENT = "RegWatchBot/1.0 (+https://auditchain.ai/regwatch)"
REQUEST_TIMEOUT = 30
MAX_CONTENT_CHARS = 5000  # truncate raw content for storage


def hash_url(url: str) -> str:
    """SHA-256 hash of a URL for deduplication."""
    return hashlib.sha256(url.strip().encode()).hexdigest()


class BaseSourceScraper(ABC):
    """Abstract base for all regional scrapers."""

    source_key: str
    source_name: str
    region: str
    base_url: str
    rss_url: str | None = None

    def __init__(self) -> None:
        self._robots: RobotFileParser | None = None
        self._robots_loaded = False

    # ------------------------------------------------------------------
    # robots.txt compliance
    # ------------------------------------------------------------------

    def _get_robots_url(self) -> str:
        parsed = urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _can_fetch(self, url: str) -> bool:
        """Check robots.txt synchronously (cached per scraper instance)."""
        if not self._robots_loaded:
            robots_url = self._get_robots_url()
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self._robots = rp
            except Exception as exc:
                logger.warning("Could not read robots.txt for %s: %s", self.base_url, exc)
                self._robots = None
            finally:
                self._robots_loaded = True

        if self._robots is None:
            return True  # assume allowed if robots.txt unavailable
        return self._robots.can_fetch(USER_AGENT, url)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _fetch_html(self, url: str) -> str | None:
        """Fetch a URL and return raw HTML, or None on failure."""
        if not self._can_fetch(url):
            logger.info("robots.txt disallows: %s", url)
            return None
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            logger.warning("HTTP error fetching %s: %s", url, exc)
            return None

    async def _fetch_rss(self, rss_url: str) -> list[feedparser.FeedParserDict]:
        """Fetch and parse an RSS/Atom feed."""
        html = await self._fetch_html(rss_url)
        if not html:
            return []
        feed = feedparser.parse(html)
        return feed.entries

    # ------------------------------------------------------------------
    # Content extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(html: str, selector: str | None = None) -> str:
        """Extract clean text from HTML, optionally scoped to a CSS selector."""
        soup = BeautifulSoup(html, "html.parser")
        if selector:
            node = soup.select_one(selector)
            if node:
                return node.get_text(separator=" ", strip=True)[:MAX_CONTENT_CHARS]
        return soup.get_text(separator=" ", strip=True)[:MAX_CONTENT_CHARS]

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Try to parse various date formats, return UTC-aware datetime."""
        if not date_str:
            return None
        import dateutil.parser as du
        try:
            dt = du.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    @staticmethod
    async def _url_exists(db: AsyncSession, url_hash: str) -> bool:
        result = await db.execute(
            select(RegulationItem.id).where(RegulationItem.url_hash == url_hash).limit(1)
        )
        return result.scalar() is not None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def scrape(self, db: AsyncSession) -> list[RegulationItem]:
        """Run the scraper and persist new items. Returns list of new items."""
        run = ScrapeRun(source_key=self.source_key, started_at=datetime.now(timezone.utc))
        db.add(run)
        await db.flush()

        try:
            raw_items = await self._fetch_items()
            new_items: list[RegulationItem] = []

            for item in raw_items:
                url_hash = hash_url(item["url"])
                if await self._url_exists(db, url_hash):
                    continue

                reg = RegulationItem(
                    source_key=self.source_key,
                    source_name=self.source_name,
                    region=self.region,
                    title=item["title"][:500],
                    url=item["url"],
                    url_hash=url_hash,
                    raw_content=item.get("content", "")[:MAX_CONTENT_CHARS],
                    published_at=item.get("published_at"),
                    scraped_at=datetime.now(timezone.utc),
                )
                db.add(reg)
                new_items.append(reg)

            await db.flush()

            run.items_found = len(raw_items)
            run.items_new = len(new_items)
            run.success = True
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "[%s] scraped %d items, %d new",
                self.source_key,
                len(raw_items),
                len(new_items),
            )
            return new_items

        except Exception as exc:
            await db.rollback()
            run.success = False
            run.error_message = str(exc)[:500]
            run.finished_at = datetime.now(timezone.utc)
            try:
                await db.commit()
            except Exception:
                pass
            logger.error("[%s] scrape failed: %s", self.source_key, exc)
            return []

    @abstractmethod
    async def _fetch_items(self) -> list[dict]:
        """Return list of dicts with keys: title, url, content (opt), published_at (opt)."""
        ...

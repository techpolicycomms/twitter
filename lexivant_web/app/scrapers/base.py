"""
Base scraper with robots.txt compliance, deduplication, and production-grade
retry/resilience patterns adapted from top open-source scraping projects:

- Exponential backoff + jitter (Apify SDK / Scrapling 34.8k★ patterns)
  wait = base * 2^attempt * uniform(0.75, 1.25)  — prevents thundering-herd

- Domain-level concurrency limiting (asyncio.Semaphore per domain)
  One concurrent request per host by default; configurable via settings

- Circuit breaker per domain
  Opens after CIRCUIT_THRESHOLD consecutive failures; resets on success
  Prevents wasted retries against persistently down sources
"""
import asyncio
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegulationItem, ScrapeRun

logger = logging.getLogger(__name__)

USER_AGENT = "LexivantWatchBot/1.0 (+https://lexivant.com/bot)"
REQUEST_TIMEOUT = 30
MAX_CONTENT_CHARS = 5000  # truncate raw content for storage

# ---------------------------------------------------------------------------
# Retry / backoff constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0          # seconds; doubles each attempt
DOMAIN_DELAY_S = 2.0           # min seconds between requests to same domain
CIRCUIT_THRESHOLD = 5          # consecutive failures before circuit opens

# ---------------------------------------------------------------------------
# Per-domain state (module-level so all scraper instances share it)
# ---------------------------------------------------------------------------
_domain_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
    lambda: asyncio.Semaphore(1)
)
_domain_last_req: dict[str, float] = defaultdict(float)
_circuit_failures: dict[str, int] = defaultdict(int)
_circuit_open: set[str] = set()


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _jitter(base: float, attempt: int) -> float:
    """Exponential backoff with ±25 % jitter."""
    return base * (2 ** attempt) * random.uniform(0.75, 1.25)


async def _throttle(domain: str) -> None:
    elapsed = time.monotonic() - _domain_last_req[domain]
    wait = DOMAIN_DELAY_S - elapsed
    if wait > 0:
        await asyncio.sleep(wait)
    _domain_last_req[domain] = time.monotonic()


def reset_circuits() -> None:
    """Call at the start of each scheduled run to allow retrying failed domains."""
    _circuit_open.clear()
    _circuit_failures.clear()


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
        """
        Fetch a URL with:
        - robots.txt compliance check
        - Domain-level concurrency limiting (1 req/domain at a time)
        - Exponential backoff + jitter on 429/5xx and network errors
        - Circuit breaker: skip domain after CIRCUIT_THRESHOLD failures
        """
        if not self._can_fetch(url):
            logger.info("robots.txt disallows: %s", url)
            return None

        domain = _domain(url)
        if domain in _circuit_open:
            logger.warning("[circuit-open] Skipping %s (domain %s)", url, domain)
            return None

        async with _domain_semaphores[domain]:
            for attempt in range(MAX_RETRIES + 1):
                await _throttle(domain)
                try:
                    async with httpx.AsyncClient(
                        headers={"User-Agent": USER_AGENT},
                        timeout=REQUEST_TIMEOUT,
                        follow_redirects=True,
                    ) as client:
                        resp = await client.get(url)

                    if resp.status_code == 429 or resp.status_code >= 500:
                        wait = _jitter(BACKOFF_BASE_S, attempt)
                        logger.warning(
                            "[scraper] %s → %d; retry %d/%d in %.1fs",
                            url, resp.status_code, attempt + 1, MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()
                    _circuit_failures[domain] = 0  # success — reset breaker
                    return resp.text

                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    wait = _jitter(BACKOFF_BASE_S, attempt)
                    logger.warning(
                        "[scraper] Network error %s: %s; retry %d/%d in %.1fs",
                        url, exc, attempt + 1, MAX_RETRIES, wait,
                    )
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(wait)
                except httpx.HTTPStatusError as exc:
                    logger.error("[scraper] HTTP %d for %s", exc.response.status_code, url)
                    break

            # All retries exhausted — update circuit breaker
            _circuit_failures[domain] += 1
            if _circuit_failures[domain] >= CIRCUIT_THRESHOLD:
                _circuit_open.add(domain)
                logger.error(
                    "[circuit-breaker] Opened for %s after %d failures",
                    domain, _circuit_failures[domain],
                )
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

"""EU scrapers: Official Journal + EC AI Office."""
import logging

from app.scrapers.base import BaseSourceScraper

logger = logging.getLogger(__name__)


class EUOfficialJournalScraper(BaseSourceScraper):
    source_key = "EU_OFFICIAL_JOURNAL"
    source_name = "EU Official Journal"
    region = "EU"
    base_url = "https://eur-lex.europa.eu"
    rss_url = "https://eur-lex.europa.eu/RSSCOMPONENT/static/technicaldocchannel/OJ_L_EN.xml"

    AI_KEYWORDS = {
        "artificial intelligence",
        "ai act",
        "algorithm",
        "automated decision",
        "machine learning",
        "data governance",
        "digital regulation",
        "ai governance",
    }

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not link:
                continue

            # Filter by AI-relevance at scrape time (lightweight keyword check)
            combined = (title + " " + entry.get("summary", "")).lower()
            if not any(kw in combined for kw in self.AI_KEYWORDS):
                continue

            items.append(
                {
                    "title": title,
                    "url": link,
                    "content": entry.get("summary", ""),
                    "published_at": self._parse_date(
                        entry.get("published") or entry.get("updated")
                    ),
                }
            )
        return items


class ECAIOfficeScraper(BaseSourceScraper):
    source_key = "EU_AI_OFFICE"
    source_name = "European Commission AI Office"
    region = "EU"
    base_url = "https://digital-strategy.ec.europa.eu"
    rss_url = "https://digital-strategy.ec.europa.eu/en/rss.xml"

    AI_KEYWORDS = {
        "artificial intelligence",
        "ai",
        "algorithm",
        "machine learning",
        "digital",
        "data",
        "automation",
    }

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not link:
                continue

            combined = (title + " " + entry.get("summary", "")).lower()
            if not any(kw in combined for kw in self.AI_KEYWORDS):
                continue

            items.append(
                {
                    "title": title,
                    "url": link,
                    "content": entry.get("summary", ""),
                    "published_at": self._parse_date(
                        entry.get("published") or entry.get("updated")
                    ),
                }
            )
        return items

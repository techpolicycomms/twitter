"""Global scrapers: OECD AI Policy Observatory + ITU AI Activities."""
import logging

from app.scrapers.base import BaseSourceScraper

logger = logging.getLogger(__name__)


class OECDScraper(BaseSourceScraper):
    source_key = "OECD_AI"
    source_name = "OECD AI Policy Observatory"
    region = "Global"
    base_url = "https://oecd.ai"
    rss_url = "https://oecd.ai/en/feed"

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if not link:
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

        if not items:
            # Fallback: scrape main news section
            from bs4 import BeautifulSoup

            html = await self._fetch_html("https://oecd.ai/en/news")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("article a, .news-item a, h3 a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title and len(title) > 10:
                        if not href.startswith("http"):
                            href = f"https://oecd.ai{href}"
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]


class ITUScraper(BaseSourceScraper):
    source_key = "ITU_AI"
    source_name = "ITU AI Activities"
    region = "Global"
    base_url = "https://www.itu.int"

    AI_KEYWORDS = {
        "artificial intelligence",
        "ai",
        "machine learning",
        "digital",
        "automation",
        "algorithm",
    }

    async def _fetch_items(self) -> list[dict]:
        from bs4 import BeautifulSoup

        html = await self._fetch_html(
            "https://www.itu.int/en/ITU-T/AI/Pages/default.aspx"
        )
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []

        for a in soup.select(".content-section a, .itu-news a, article a, h3 a, h4 a"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href or not title or len(title) < 10:
                continue
            if not href.startswith("http"):
                href = f"https://www.itu.int{href}"
            combined = title.lower()
            if any(kw in combined for kw in self.AI_KEYWORDS):
                items.append({"title": title, "url": href, "content": title})

        return items[:30]

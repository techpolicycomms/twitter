"""India scrapers: MeitY + PRS Legislative Research."""
import logging

from bs4 import BeautifulSoup

from app.scrapers.base import BaseSourceScraper

logger = logging.getLogger(__name__)

MEITY_NEWS_URL = "https://www.meity.gov.in/whats-new"


class MeityScraper(BaseSourceScraper):
    source_key = "INDIA_MEITY"
    source_name = "MeitY India"
    region = "India"
    base_url = "https://www.meity.gov.in"

    async def _fetch_items(self) -> list[dict]:
        html = await self._fetch_html(MEITY_NEWS_URL)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []

        # MeitY lists news/press releases in table rows or article links
        for a in soup.select("div.view-content a, table.views-table tbody tr a"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href or not title:
                continue
            if href.startswith("/"):
                href = f"https://www.meity.gov.in{href}"
            if not href.startswith("http"):
                continue

            items.append({"title": title, "url": href, "content": title})

        return items[:30]  # cap at 30 most recent


class PRSScraper(BaseSourceScraper):
    source_key = "INDIA_PRS"
    source_name = "PRS Legislative Research"
    region = "India"
    base_url = "https://prsindia.org"
    rss_url = "https://prsindia.org/rss"

    AI_KEYWORDS = {
        "artificial intelligence",
        "data protection",
        "digital",
        "algorithm",
        "dpdp",
        "personal data",
        "technology",
        "it act",
        "cyber",
    }

    async def _fetch_items(self) -> list[dict]:
        # Try RSS first
        entries = await self._fetch_rss(self.rss_url)
        items = []

        if entries:
            for entry in entries:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if not link:
                    continue
                combined = (title + " " + entry.get("summary", "")).lower()
                if any(kw in combined for kw in self.AI_KEYWORDS):
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
        else:
            # Fallback: scrape bills/legislation page
            html = await self._fetch_html("https://prsindia.org/billtrack")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("td.views-field-title a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href.startswith("/"):
                        href = f"https://prsindia.org{href}"
                    combined = title.lower()
                    if any(kw in combined for kw in self.AI_KEYWORDS):
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]

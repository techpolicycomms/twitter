"""Africa scrapers: Nigeria (NITDA, NDPC), Kenya (ICTA, ODPC),
South Africa (DCDT, InfoReg), African Union, Rwanda (MINICT)."""
import logging

from bs4 import BeautifulSoup

from app.scrapers.base import BaseSourceScraper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Nigeria
# ---------------------------------------------------------------------------


class NITDAScraper(BaseSourceScraper):
    source_key = "NIGERIA_NITDA"
    source_name = "NITDA Nigeria"
    region = "Nigeria"
    base_url = "https://nitda.gov.ng"
    rss_url = "https://nitda.gov.ng/feed/"

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
            # Fallback: scrape news page
            html = await self._fetch_html("https://nitda.gov.ng/news/")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("article a, .entry-title a, h2.post-title a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title:
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]


class NDPCScraper(BaseSourceScraper):
    source_key = "NIGERIA_NDPC"
    source_name = "NDPC Nigeria"
    region = "Nigeria"
    base_url = "https://ndpc.gov.ng"
    rss_url = "https://ndpc.gov.ng/feed/"

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if link and title:
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
            html = await self._fetch_html("https://ndpc.gov.ng/news")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("article a, .entry-title a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title:
                        if not href.startswith("http"):
                            href = f"https://ndpc.gov.ng{href}"
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]


# ---------------------------------------------------------------------------
# Kenya
# ---------------------------------------------------------------------------


class ICTAScraper(BaseSourceScraper):
    source_key = "KENYA_ICTA"
    source_name = "ICT Authority Kenya"
    region = "Kenya"
    base_url = "https://www.ictauthority.go.ke"
    rss_url = "https://www.ictauthority.go.ke/index.php?format=feed&type=rss"

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if link and title:
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
            html = await self._fetch_html("https://www.ictauthority.go.ke/news")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("a.list-title, article h2 a, .news-title a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title:
                        if not href.startswith("http"):
                            href = f"https://www.ictauthority.go.ke{href}"
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]


class ODPCKenyaScraper(BaseSourceScraper):
    source_key = "KENYA_ODPC"
    source_name = "ODPC Kenya"
    region = "Kenya"
    base_url = "https://www.odpc.go.ke"

    async def _fetch_items(self) -> list[dict]:
        html = await self._fetch_html("https://www.odpc.go.ke/news/")
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = []
        for a in soup.select("article a, .entry-title a, h2 a, h3 a"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if href and title and len(title) > 10:
                if not href.startswith("http"):
                    href = f"https://www.odpc.go.ke{href}"
                items.append({"title": title, "url": href, "content": title})

        return items[:30]


# ---------------------------------------------------------------------------
# South Africa
# ---------------------------------------------------------------------------


class DCDTScraper(BaseSourceScraper):
    source_key = "SOUTH_AFRICA_DCDT"
    source_name = "DCDT South Africa"
    region = "South Africa"
    base_url = "https://www.gov.za"
    rss_url = "https://www.gov.za/rss.xml"

    AI_KEYWORDS = {
        "digital",
        "technology",
        "artificial intelligence",
        "data",
        "cyber",
        "communications",
        "dcdt",
        "information",
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

        return items[:30]


class InfoRegScraper(BaseSourceScraper):
    source_key = "SOUTH_AFRICA_INFOREG"
    source_name = "Information Regulator South Africa"
    region = "South Africa"
    base_url = "https://www.inforegulator.org.za"
    rss_url = "https://www.inforegulator.org.za/feed/"

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if link and title:
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
            html = await self._fetch_html("https://www.inforegulator.org.za/news/")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("article a, .entry-title a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title:
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]


# ---------------------------------------------------------------------------
# African Union
# ---------------------------------------------------------------------------


class AUScraper(BaseSourceScraper):
    source_key = "AFRICAN_UNION"
    source_name = "African Union CITC"
    region = "African Union"
    base_url = "https://au.int"
    rss_url = "https://au.int/en/rss.xml"

    AI_KEYWORDS = {
        "artificial intelligence",
        "digital",
        "technology",
        "data",
        "cyber",
        "innovation",
        "ict",
        "ai",
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

        if not items:
            html = await self._fetch_html(
                "https://au.int/en/departments/infrastructure-and-energy/infrastructure"
            )
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select(".views-row a, .field-item a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title and len(title) > 10:
                        if not href.startswith("http"):
                            href = f"https://au.int{href}"
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]


# ---------------------------------------------------------------------------
# Rwanda
# ---------------------------------------------------------------------------


class MINICTScraper(BaseSourceScraper):
    source_key = "RWANDA_MINICT"
    source_name = "MINICT Rwanda"
    region = "Rwanda"
    base_url = "https://www.minict.gov.rw"
    rss_url = "https://www.minict.gov.rw/feed/"

    async def _fetch_items(self) -> list[dict]:
        entries = await self._fetch_rss(self.rss_url)
        items = []
        for entry in entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            if link and title:
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
            html = await self._fetch_html("https://www.minict.gov.rw/news/")
            if html:
                soup = BeautifulSoup(html, "html.parser")
                for a in soup.select("article a, .entry-title a, h2 a"):
                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    if href and title:
                        if not href.startswith("http"):
                            href = f"https://www.minict.gov.rw{href}"
                        items.append({"title": title, "url": href, "content": title})

        return items[:30]

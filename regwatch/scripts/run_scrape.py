#!/usr/bin/env python3
"""Manual scrape runner with optional source filtering."""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from app.analysis.analyzer import analyze_all_pending
from app.database import AsyncSessionLocal, init_db
from app.notifications.alert_manager import process_pending_alerts
from app.scrapers import ALL_SCRAPERS


async def main(source_keys: list[str] | None, analyze: bool, alerts: bool):
    await init_db()

    scrapers_to_run = ALL_SCRAPERS
    if source_keys:
        scrapers_to_run = [s for s in ALL_SCRAPERS if s.source_key in source_keys]
        if not scrapers_to_run:
            print(f"No scrapers found for keys: {source_keys}")
            print(f"Available: {[s.source_key for s in ALL_SCRAPERS]}")
            sys.exit(1)

    total_new = 0
    async with AsyncSessionLocal() as db:
        for ScraperClass in scrapers_to_run:
            print(f"[{ScraperClass.source_key}] Scraping...")
            scraper = ScraperClass()
            new_items = await scraper.scrape(db)
            print(f"[{ScraperClass.source_key}] {len(new_items)} new items")
            total_new += len(new_items)

    print(f"\nTotal new items: {total_new}")

    if analyze and total_new > 0:
        print("\nAnalyzing new items with Claude...")
        async with AsyncSessionLocal() as db:
            count = await analyze_all_pending(db)
        print(f"Analyzed: {count} items")

    if alerts:
        print("\nProcessing HIGH impact alerts...")
        async with AsyncSessionLocal() as db:
            sent = await process_pending_alerts(db)
        print(f"Alerts sent: {sent}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RegWatch scraper")
    parser.add_argument(
        "--source",
        action="append",
        metavar="SOURCE_KEY",
        help="Scrape specific source(s) only (can repeat)",
    )
    parser.add_argument("--no-analyze", action="store_true", help="Skip Claude analysis")
    parser.add_argument("--no-alerts", action="store_true", help="Skip sending alerts")
    args = parser.parse_args()

    asyncio.run(
        main(
            source_keys=args.source,
            analyze=not args.no_analyze,
            alerts=not args.no_alerts,
        )
    )

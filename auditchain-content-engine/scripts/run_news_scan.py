#!/usr/bin/env python3
"""
Standalone script to run the news scanner.
Intended for use with cron at 06:00 UTC.

Usage:
    python scripts/run_news_scan.py
    python scripts/run_news_scan.py --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal, create_all_tables
from app.scanner.analyzer import run_news_scan_and_analyze

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("run_news_scan")


async def main(dry_run: bool = False) -> int:
    """
    Run the news scan pipeline.

    Args:
        dry_run: If True, fetch feeds but don't persist to DB.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    logger.info(f"Starting news scan {'(DRY RUN)' if dry_run else ''}")

    await create_all_tables()

    if dry_run:
        from app.scanner.rss_fetcher import fetch_feed
        import httpx
        from app.config import get_settings

        settings = get_settings()
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for name, url in settings.rss_feeds.items():
                items = await fetch_feed(name, url, client)
                logger.info(f"[DRY RUN] {name}: {len(items)} items found")
        return 0

    try:
        async with AsyncSessionLocal() as db:
            summary = await run_news_scan_and_analyze(db)
            await db.commit()

        logger.info("News scan completed successfully:")
        for k, v in summary.items():
            logger.info(f"  {k}: {v}")
        return 0

    except Exception as e:
        logger.error(f"News scan failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuditChain news scanner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch feeds without persisting to database",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main(dry_run=args.dry_run))
    sys.exit(exit_code)

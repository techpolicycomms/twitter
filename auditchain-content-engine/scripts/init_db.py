#!/usr/bin/env python3
"""
Initialize the database: create tables and import the content calendar.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --calendar content-calendar.csv
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal, create_all_tables

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("init_db")


async def main(calendar_path: str) -> None:
    logger.info("Creating database tables...")
    await create_all_tables()
    logger.info("Tables created")

    csv_path = Path(calendar_path)
    if csv_path.exists():
        from app.content.calendar import import_calendar_to_db

        async with AsyncSessionLocal() as db:
            inserted, skipped = await import_calendar_to_db(csv_path, db)
            await db.commit()

        logger.info(f"Calendar imported: {inserted} new, {skipped} existing")
    else:
        logger.warning(f"Calendar CSV not found at {csv_path} — skipping import")

    logger.info("Database initialization complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--calendar",
        default="content-calendar.csv",
        help="Path to content-calendar.csv",
    )
    args = parser.parse_args()
    asyncio.run(main(args.calendar))

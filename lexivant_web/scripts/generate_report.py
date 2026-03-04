#!/usr/bin/env python3
"""Manual report generation script."""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from app.database import AsyncSessionLocal, init_db
from app.reports.generator import (
    generate_daily_digest,
    generate_monthly_newsletter,
    generate_weekly_linkedin,
)


async def main(report_type: str):
    await init_db()
    async with AsyncSessionLocal() as db:
        if report_type == "digest":
            report = await generate_daily_digest(db)
        elif report_type == "linkedin":
            report = await generate_weekly_linkedin(db)
        elif report_type == "newsletter":
            report = await generate_monthly_newsletter(db)
        else:
            print(f"Unknown report type: {report_type}")
            sys.exit(1)

    if report:
        print(f"\n✅ Report generated: ID={report.id}")
        print(f"   Title: {report.title}")
        print(f"   Items: {report.item_count}")
        if report.content_text:
            print(f"\n--- Content Preview ---\n{report.content_text[:500]}...")
    else:
        print("\nNo report generated (not enough data for the requested period).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RegWatch report generator")
    parser.add_argument(
        "type",
        choices=["digest", "linkedin", "newsletter"],
        help="Report type to generate",
    )
    args = parser.parse_args()
    asyncio.run(main(args.type))

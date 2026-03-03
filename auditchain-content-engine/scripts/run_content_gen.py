#!/usr/bin/env python3
"""
Standalone script to generate content from today's calendar entries.
Intended for use with cron at 07:00 UTC.

Usage:
    python scripts/run_content_gen.py
    python scripts/run_content_gen.py --date 2026-03-05
    python scripts/run_content_gen.py --platform linkedin
    python scripts/run_content_gen.py --topic "EU AI Act update" --platform twitter --pillar "regulatory updates"
"""

import argparse
import asyncio
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal, create_all_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("run_content_gen")


async def run_from_calendar(
    target_date: date | None = None,
    platform_filter: str | None = None,
) -> int:
    """Generate content for pending calendar entries on the given date."""
    from app.content.calendar import get_pending_entries_for_today
    from app.content.generator import generate_from_calendar_entry
    from app.models import Platform

    await create_all_tables()

    async with AsyncSessionLocal() as db:
        entries = await get_pending_entries_for_today(db, target_date)

        if platform_filter:
            try:
                plat = Platform(platform_filter.lower())
                entries = [e for e in entries if e.platform == plat]
            except ValueError:
                logger.error(f"Invalid platform: {platform_filter}")
                return 1

        if not entries:
            logger.info("No pending entries to generate")
            return 0

        logger.info(f"Generating content for {len(entries)} calendar entries")
        generated = 0
        failed = 0

        for entry in entries:
            try:
                content = await generate_from_calendar_entry(entry, db)
                await db.commit()
                logger.info(
                    f"Generated: [{content.platform.value}] {entry.topic[:60]} "
                    f"(id={content.id})"
                )
                generated += 1
            except Exception as e:
                logger.error(f"Failed for entry {entry.id}: {e}", exc_info=True)
                await db.rollback()
                failed += 1

    logger.info(f"Done: {generated} generated, {failed} failed")
    return 0 if failed == 0 else 1


async def run_manual(topic: str, platform: str, pillar: str, context: str = "") -> int:
    """Generate a single piece of content manually."""
    from app.content.generator import generate_manual
    from app.models import ContentPillar, Platform

    await create_all_tables()

    try:
        plat = Platform(platform.lower())
    except ValueError:
        logger.error(f"Invalid platform '{platform}'. Valid: linkedin, twitter, blog")
        return 1

    pillar_map = {
        "ai fairness": ContentPillar.AI_FAIRNESS,
        "regulatory updates": ContentPillar.REGULATORY_UPDATES,
        "blockchain trust": ContentPillar.BLOCKCHAIN_TRUST,
        "case studies": ContentPillar.CASE_STUDIES,
        "behind the scenes": ContentPillar.BEHIND_THE_SCENES,
    }
    pillar_enum = pillar_map.get(pillar.lower())
    if not pillar_enum:
        logger.error(f"Invalid pillar '{pillar}'. Valid: {list(pillar_map.keys())}")
        return 1

    async with AsyncSessionLocal() as db:
        content = await generate_manual(
            topic=topic,
            platform=plat,
            pillar=pillar_enum,
            additional_context=context,
            db=db,
        )
        await db.commit()
        logger.info(f"Generated content id={content.id}")
        logger.info(f"Status: {content.status.value}")
        logger.info(f"Words: {content.word_count}")
        print("\n" + "=" * 60)
        print(content.body)
        if content.hashtags:
            print("\n" + content.hashtags)
        print("=" * 60)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AuditChain content generator")
    subparsers = parser.add_subparsers(dest="command")

    # Calendar subcommand
    cal_parser = subparsers.add_parser("calendar", help="Generate from calendar")
    cal_parser.add_argument("--date", type=str, help="Date (YYYY-MM-DD), defaults to today")
    cal_parser.add_argument("--platform", type=str, help="Filter by platform")

    # Manual subcommand
    man_parser = subparsers.add_parser("manual", help="Generate manually")
    man_parser.add_argument("--topic", required=True, help="Content topic")
    man_parser.add_argument(
        "--platform", required=True, choices=["linkedin", "twitter", "blog"]
    )
    man_parser.add_argument(
        "--pillar",
        required=True,
        choices=["ai fairness", "regulatory updates", "blockchain trust",
                 "case studies", "behind the scenes"],
    )
    man_parser.add_argument("--context", default="", help="Additional context for Claude")

    args = parser.parse_args()

    if args.command == "calendar":
        target = date.fromisoformat(args.date) if args.date else None
        exit_code = asyncio.run(run_from_calendar(target, args.platform))
    elif args.command == "manual":
        exit_code = asyncio.run(
            run_manual(args.topic, args.platform, args.pillar, args.context)
        )
    else:
        # Default: run calendar for today
        exit_code = asyncio.run(run_from_calendar())

    sys.exit(exit_code)

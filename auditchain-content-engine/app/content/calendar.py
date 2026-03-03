"""
Content calendar CSV parser and database importer.

Reads content-calendar.csv and upserts entries into the database.
"""

import csv
import logging
from datetime import date
from pathlib import Path
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentCalendarEntry, ContentPillar, Platform

logger = logging.getLogger(__name__)

# Mapping from CSV strings to enum values
PLATFORM_MAP = {
    "linkedin": Platform.LINKEDIN,
    "twitter": Platform.TWITTER,
    "twitter/x": Platform.TWITTER,
    "blog": Platform.BLOG,
}

PILLAR_MAP = {
    "ai fairness": ContentPillar.AI_FAIRNESS,
    "regulatory updates": ContentPillar.REGULATORY_UPDATES,
    "blockchain trust": ContentPillar.BLOCKCHAIN_TRUST,
    "case studies": ContentPillar.CASE_STUDIES,
    "behind the scenes": ContentPillar.BEHIND_THE_SCENES,
}


def parse_calendar_csv(filepath: str | Path) -> List[dict]:
    """
    Parse a content-calendar.csv file into a list of dicts.

    Expected columns: date, topic, platform, content_pillar

    Args:
        filepath: Path to the CSV file.

    Returns:
        List of dicts with typed values ready for DB insert.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If required columns are missing or values are invalid.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Calendar CSV not found: {filepath}")

    entries = []
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_columns = {"date", "topic", "platform", "content_pillar"}
        if not required_columns.issubset(set(reader.fieldnames or [])):
            missing = required_columns - set(reader.fieldnames or [])
            raise ValueError(f"CSV missing required columns: {missing}")

        for row_num, row in enumerate(reader, start=2):
            try:
                entry = _parse_row(row, row_num)
                if entry:
                    entries.append(entry)
            except ValueError as e:
                logger.warning(f"Row {row_num} skipped: {e}")

    logger.info(f"Parsed {len(entries)} calendar entries from {filepath}")
    return entries


def _parse_row(row: dict, row_num: int) -> dict | None:
    """Parse and validate a single CSV row."""
    # Skip empty rows
    if not any(row.values()):
        return None

    # Parse date
    raw_date = row.get("date", "").strip()
    try:
        entry_date = date.fromisoformat(raw_date)
    except ValueError:
        raise ValueError(f"Invalid date '{raw_date}'")

    # Parse platform
    raw_platform = row.get("platform", "").strip().lower()
    platform = PLATFORM_MAP.get(raw_platform)
    if platform is None:
        raise ValueError(
            f"Unknown platform '{raw_platform}'. Valid: {list(PLATFORM_MAP.keys())}"
        )

    # Parse content pillar
    raw_pillar = row.get("content_pillar", "").strip().lower()
    pillar = PILLAR_MAP.get(raw_pillar)
    if pillar is None:
        raise ValueError(
            f"Unknown pillar '{raw_pillar}'. Valid: {list(PILLAR_MAP.keys())}"
        )

    topic = row.get("topic", "").strip()
    if not topic:
        raise ValueError("Topic is empty")

    return {
        "entry_date": entry_date,
        "topic": topic,
        "platform": platform,
        "content_pillar": pillar,
    }


async def import_calendar_to_db(
    filepath: str | Path,
    db: AsyncSession,
    overwrite_existing: bool = False,
) -> tuple[int, int]:
    """
    Import calendar CSV entries into the database.

    Skips entries that already exist (by unique constraint) unless
    overwrite_existing is True.

    Args:
        filepath: Path to the CSV file.
        db: AsyncSession.
        overwrite_existing: If True, update existing entries.

    Returns:
        Tuple of (inserted, skipped) counts.
    """
    entries = parse_calendar_csv(filepath)
    inserted = 0
    skipped = 0

    for entry_data in entries:
        # Check for existing entry
        stmt = select(ContentCalendarEntry).where(
            ContentCalendarEntry.entry_date == entry_data["entry_date"],
            ContentCalendarEntry.platform == entry_data["platform"],
            ContentCalendarEntry.topic == entry_data["topic"],
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if overwrite_existing:
                existing.content_pillar = entry_data["content_pillar"]
                db.add(existing)
                inserted += 1
            else:
                skipped += 1
        else:
            new_entry = ContentCalendarEntry(**entry_data)
            db.add(new_entry)
            inserted += 1

    await db.flush()
    logger.info(f"Calendar import complete: {inserted} inserted, {skipped} skipped")
    return inserted, skipped


async def get_pending_entries_for_today(
    db: AsyncSession,
    target_date: date | None = None,
) -> List[ContentCalendarEntry]:
    """
    Fetch calendar entries for today that have not yet been generated.

    Args:
        db: AsyncSession.
        target_date: Date to query (defaults to today UTC).

    Returns:
        List of ungenerated ContentCalendarEntry records.
    """
    from datetime import datetime, timezone

    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    stmt = select(ContentCalendarEntry).where(
        ContentCalendarEntry.entry_date == target_date,
        ContentCalendarEntry.is_generated.is_(False),
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()
    logger.info(f"Found {len(entries)} pending entries for {target_date}")
    return list(entries)

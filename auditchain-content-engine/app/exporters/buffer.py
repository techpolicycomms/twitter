"""
Buffer API exporter.

Converts approved GeneratedContent records into Buffer API payloads
and optionally pushes them to Buffer for scheduling.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from app.config import get_settings
from app.models import GeneratedContent, Platform
from app.schemas import BufferExportItem

logger = logging.getLogger(__name__)
settings = get_settings()

BUFFER_API_BASE = "https://api.bufferapp.com/1"


def _get_profile_ids(platform: Platform) -> List[str]:
    """Return Buffer profile IDs for the given platform."""
    if platform == Platform.LINKEDIN:
        ids = settings.buffer_profile_ids_linkedin
    elif platform == Platform.TWITTER:
        ids = settings.buffer_profile_ids_twitter
    else:
        return []
    return [pid.strip() for pid in ids.split(",") if pid.strip()]


def _calculate_scheduled_time(
    content: GeneratedContent,
    slot_index: int = 0,
) -> str:
    """
    Calculate optimal posting time for the given content.

    Uses platform-specific optimal hours. If content.scheduled_for is set,
    that takes priority.

    Args:
        content: The GeneratedContent to schedule.
        slot_index: Which slot to use (0 = earliest available today).

    Returns:
        ISO 8601 UTC datetime string.
    """
    if content.scheduled_for:
        return content.scheduled_for.isoformat()

    now = datetime.now(timezone.utc)

    if content.platform == Platform.LINKEDIN:
        hours = settings.linkedin_hours_list
    elif content.platform == Platform.TWITTER:
        hours = settings.twitter_hours_list
    else:
        hours = [settings.blog_publish_hour]

    # Find the next available slot at or after now
    for offset_days in range(7):  # Look up to 7 days ahead
        target_day = now + timedelta(days=offset_days)
        for hour in sorted(hours):
            candidate = target_day.replace(hour=hour, minute=0, second=0, microsecond=0)
            if candidate > now:
                return candidate.isoformat()

    # Fallback: 24h from now
    return (now + timedelta(hours=24)).isoformat()


def content_to_buffer_payload(
    content: GeneratedContent,
    slot_index: int = 0,
) -> Optional[BufferExportItem]:
    """
    Convert a GeneratedContent record to a Buffer API payload.

    For Twitter threads, creates a single text from the JSON array
    (Buffer handles thread creation via their UI/API).

    Args:
        content: An approved GeneratedContent record.
        slot_index: Scheduling slot offset.

    Returns:
        BufferExportItem or None if no profile IDs are configured.
    """
    profile_ids = _get_profile_ids(content.platform)
    if not profile_ids:
        logger.warning(
            f"No Buffer profile IDs configured for {content.platform.value}"
        )
        return None

    # Build the text body
    if content.platform == Platform.TWITTER:
        # Twitter threads: serialize back from JSON array
        try:
            tweets = json.loads(content.body)
            text = "\n\n".join(tweets) if isinstance(tweets, list) else content.body
        except json.JSONDecodeError:
            text = content.body
    else:
        # LinkedIn / Blog: combine body + hashtags
        parts = [content.body]
        if content.hashtags:
            parts.append(content.hashtags)
        text = "\n\n".join(parts)

    scheduled_at = _calculate_scheduled_time(content, slot_index)

    return BufferExportItem(
        profile_ids=profile_ids,
        text=text,
        scheduled_at=scheduled_at,
        now=False,
        shorten=True,
    )


def export_to_json(
    content_list: List[GeneratedContent],
    output_path: str | None = None,
) -> str:
    """
    Export a list of approved content items to Buffer-compatible JSON.

    Args:
        content_list: List of GeneratedContent records.
        output_path: Optional file path to write to.

    Returns:
        JSON string of the export payload.
    """
    payloads = []
    for i, content in enumerate(content_list):
        item = content_to_buffer_payload(content, slot_index=i)
        if item:
            payloads.append(
                {
                    "content_id": content.id,
                    "platform": content.platform.value,
                    "topic": content.topic,
                    "buffer_payload": item.model_dump(exclude_none=True),
                }
            )

    result = json.dumps(
        {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total": len(payloads),
            "items": payloads,
        },
        ensure_ascii=False,
        indent=2,
    )

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
        logger.info(f"Exported {len(payloads)} items to {output_path}")

    return result


async def push_to_buffer(
    content: GeneratedContent,
    access_token: str | None = None,
) -> Optional[str]:
    """
    Push a single content item to Buffer via the API.

    Args:
        content: Approved GeneratedContent to schedule.
        access_token: Buffer access token (defaults to settings value).

    Returns:
        Buffer update ID if successful, None on failure.
    """
    token = access_token or settings.buffer_access_token
    if not token:
        logger.warning("Buffer access token not configured — skipping push")
        return None

    payload = content_to_buffer_payload(content)
    if not payload:
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BUFFER_API_BASE}/updates/create.json",
                data={
                    "access_token": token,
                    "profile_ids[]": payload.profile_ids,
                    "text": payload.text,
                    "scheduled_at": payload.scheduled_at or "",
                    "shorten": "true" if payload.shorten else "false",
                },
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()

            update_id = data.get("updates", [{}])[0].get("id")
            logger.info(
                f"Content {content.id} pushed to Buffer: update_id={update_id}"
            )
            return update_id

    except httpx.HTTPError as e:
        logger.error(f"Buffer API error for content {content.id}: {e}")
        return None

"""Slack alert notifications via incoming webhook."""
import json
import logging

import httpx

from app.config import settings
from app.models import RegulationItem

logger = logging.getLogger(__name__)

IMPACT_EMOJI = {
    "HIGH": ":red_circle:",
    "MEDIUM": ":large_yellow_circle:",
    "LOW": ":large_green_circle:",
}

REGION_FLAG = {
    "EU": ":eu:",
    "India": ":india:",
    "Nigeria": ":ng:",
    "Kenya": ":kenya:",
    "South Africa": ":south_africa:",
    "African Union": ":africa:",
    "Rwanda": ":rwanda:",
    "Global": ":globe_with_meridians:",
}


def _build_slack_payload(item: RegulationItem) -> dict:
    impact = item.impact_level.value if item.impact_level else "UNKNOWN"
    emoji = IMPACT_EMOJI.get(impact, ":white_circle:")
    flag = REGION_FLAG.get(item.region, ":earth_africa:")

    try:
        action_items = json.loads(item.action_items or "[]")
    except json.JSONDecodeError:
        action_items = []

    action_text = (
        "\n".join(f"• {a}" for a in action_items[:3]) if action_items else "_No action items._"
    )

    return {
        "text": f"{emoji} *HIGH IMPACT REGULATORY ALERT* {emoji}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"[REGWATCH] {impact} Impact — {item.region}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Region:*\n{flag} {item.region}"},
                    {"type": "mrkdwn", "text": f"*Source:*\n{item.source_name}"},
                    {"type": "mrkdwn", "text": f"*Impact:*\n{emoji} {impact}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Relevance Score:*\n{item.relevance_score:.2f}" if item.relevance_score else "*Relevance Score:*\nN/A",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Title:*\n<{item.url}|{item.title}>",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{item.ai_summary or 'No summary available.'}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Action Items for AuditChain:*\n{action_text}",
                },
            },
            {"type": "divider"},
        ],
    }


async def send_slack_alert(item: RegulationItem) -> bool:
    """Send HIGH impact alert to Slack webhook. Returns True on success."""
    if not settings.slack_webhook_url:
        logger.warning("Slack webhook URL not configured, skipping alert")
        return False

    payload = _build_slack_payload(item)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.slack_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            logger.info("Slack alert sent for item %d: %s", item.id, item.title[:60])
            return True
    except Exception as exc:
        logger.error("Failed to send Slack alert for item %d: %s", item.id, exc)
        return False

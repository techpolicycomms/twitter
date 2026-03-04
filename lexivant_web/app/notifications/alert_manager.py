"""Alert manager: orchestrates Slack + email alerts for HIGH impact items."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Alert, AlertStatus, ImpactLevel, RegulationItem
from app.notifications.email import send_high_impact_alert
from app.notifications.slack import send_slack_alert

logger = logging.getLogger(__name__)


async def send_alerts_for_item(db: AsyncSession, item: RegulationItem) -> None:
    """Send Slack + email alerts for a HIGH impact item and record results."""
    if item.alert_sent:
        return

    # Send Slack
    slack_ok = await send_slack_alert(item)
    slack_alert = Alert(
        regulation_item_id=item.id,
        channel="slack",
        status=AlertStatus.SENT if slack_ok else AlertStatus.FAILED,
        sent_at=datetime.now(timezone.utc) if slack_ok else None,
    )
    db.add(slack_alert)

    # Send email to each team recipient
    if settings.team_email_recipients:
        email_ok = await send_high_impact_alert(item, settings.team_email_recipients)
        email_alert = Alert(
            regulation_item_id=item.id,
            channel="email",
            recipient=",".join(settings.team_email_recipients),
            status=AlertStatus.SENT if email_ok else AlertStatus.FAILED,
            sent_at=datetime.now(timezone.utc) if email_ok else None,
        )
        db.add(email_alert)

    item.alert_sent = True
    item.alert_sent_at = datetime.now(timezone.utc)
    await db.flush()


async def process_pending_alerts(db: AsyncSession) -> int:
    """Find HIGH impact, relevant, unalerted items and send alerts. Returns count sent."""
    result = await db.execute(
        select(RegulationItem)
        .where(
            RegulationItem.analyzed == True,  # noqa: E712
            RegulationItem.is_relevant == True,  # noqa: E712
            RegulationItem.impact_level == ImpactLevel.HIGH,
            RegulationItem.alert_sent == False,  # noqa: E712
        )
        .order_by(RegulationItem.scraped_at.desc())
    )
    items = result.scalars().all()

    sent_count = 0
    for item in items:
        try:
            await send_alerts_for_item(db, item)
            sent_count += 1
        except Exception as exc:
            logger.error("Alert failed for item %d: %s", item.id, exc)

    if sent_count:
        await db.commit()
    logger.info("Alert processing complete: %d HIGH impact alerts sent", sent_count)
    return sent_count

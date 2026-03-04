"""Claude-powered analysis pipeline for regulation items."""
import json
import logging
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ImpactLevel, RegulationItem

logger = logging.getLogger(__name__)

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

ANALYSIS_SYSTEM_PROMPT = """You are a regulatory intelligence analyst for AuditChain,
a third-party AI/ML model auditing and certification platform focused on African and
emerging market contexts. Your job is to evaluate regulatory and policy documents for
their relevance and impact on AI auditing, algorithmic accountability, and AI governance.

AuditChain's core services:
- Independent algorithmic audits for fairness, transparency, and robustness
- Blockchain-based certification (NFT certificates) for audited models
- Serving clients in fintech, healthcare, government, and enterprise across Africa and Asia

When analyzing documents, always respond with valid JSON only."""

ANALYSIS_USER_PROMPT = """Analyze the following regulatory document/announcement and return a JSON object.

Source: {source_name} ({region})
Title: {title}
URL: {url}
Content: {content}

Return EXACTLY this JSON structure (no markdown, no extra text):
{{
  "is_relevant": true/false,
  "relevance_score": 0.0-1.0,
  "impact_level": "HIGH" | "MEDIUM" | "LOW",
  "summary": "2-3 sentence summary of what this item is about and why it matters",
  "action_items": [
    "Specific action AuditChain should consider",
    "Another action if applicable"
  ],
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}

Relevance criteria (is_relevant = true if ANY apply):
- Mentions AI auditing, algorithmic accountability, or AI certification requirements
- New or proposed AI/data protection regulations in AuditChain's markets
- Enforcement actions related to AI bias, automated decision-making, or data misuse
- Standards (ISO, IEEE, national) for AI systems
- Government procurement requirements for AI transparency
- Fintech/healthcare AI regulation updates

Impact level:
- HIGH: Mandatory audit requirements, major fines/enforcement, new certification standards, imminent compliance deadlines
- MEDIUM: Proposed regulations under consultation, guidance documents, policy frameworks
- LOW: General digital policy updates, awareness campaigns, international frameworks with no immediate compliance requirement

If is_relevant is false, still provide a brief summary but impact_level should be "LOW" and action_items can be empty."""


async def analyze_item(item: RegulationItem) -> dict:
    """Send a regulation item to Claude for analysis. Returns parsed JSON."""
    prompt = ANALYSIS_USER_PROMPT.format(
        source_name=item.source_name,
        region=item.region,
        title=item.title,
        url=item.url,
        content=(item.raw_content or "")[:3000],
    )

    message = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code blocks if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    result = json.loads(raw)
    result["_input_tokens"] = message.usage.input_tokens
    result["_output_tokens"] = message.usage.output_tokens
    return result


async def analyze_batch(db: AsyncSession, batch_size: int = 10) -> int:
    """Analyze all unanalyzed items in batches. Returns count analyzed."""
    result = await db.execute(
        select(RegulationItem)
        .where(RegulationItem.analyzed == False)  # noqa: E712
        .order_by(RegulationItem.scraped_at.desc())
        .limit(batch_size)
    )
    items = result.scalars().all()

    analyzed_count = 0
    for item in items:
        try:
            analysis = await analyze_item(item)

            item.is_relevant = analysis.get("is_relevant", False)
            item.relevance_score = float(analysis.get("relevance_score", 0.0))
            item.impact_level = ImpactLevel(analysis.get("impact_level", "LOW"))
            item.ai_summary = analysis.get("summary", "")
            item.action_items = json.dumps(analysis.get("action_items", []))
            item.keywords = json.dumps(analysis.get("keywords", []))
            item.analyzed = True
            item.analyzed_at = datetime.now(timezone.utc)

            await db.flush()
            analyzed_count += 1

            logger.info(
                "Analyzed [%s] %s → impact=%s relevant=%s",
                item.region,
                item.title[:60],
                item.impact_level,
                item.is_relevant,
            )
        except json.JSONDecodeError as exc:
            logger.error("JSON parse error for item %d: %s", item.id, exc)
            item.analyzed = True  # mark done to avoid infinite retry
            item.impact_level = ImpactLevel.LOW
            item.analyzed_at = datetime.now(timezone.utc)
            await db.flush()
        except Exception as exc:
            logger.error("Analysis failed for item %d: %s", item.id, exc)

    await db.commit()
    return analyzed_count


async def analyze_all_pending(db: AsyncSession) -> int:
    """Run analyze_batch repeatedly until no unanalyzed items remain."""
    total = 0
    while True:
        count = await analyze_batch(db, batch_size=10)
        total += count
        if count == 0:
            break
    logger.info("Analysis complete. Total items analyzed: %d", total)
    return total

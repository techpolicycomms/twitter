"""
Claude-powered analysis pipeline for regulation items.

Implements two patterns from top-rated repos:

1. instructor (12.7k★) — Pydantic-validated structured outputs with automatic
   retry on validation failure. When Claude returns a malformed or incomplete
   response, instructor feeds the ValidationError back with the next attempt.
   This replaces fragile JSON-parsing + manual tool_use extraction.
   See: https://github.com/instructor-ai/instructor

2. Content-hash deduplication — SHA-256 of raw_content prevents re-analyzing
   identical documents scraped on consecutive days (common for static gov pages).
   Hash is stored on the model and checked before calling Claude.

Fallback: if instructor is not installed, falls back to direct tool_use.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Literal

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ImpactLevel, RegulationItem

logger = logging.getLogger(__name__)

# ── Pydantic response model (used by instructor for validation + retry) ───────

class RegulationAnalysis(BaseModel):
    """Structured analysis output — instructor validates and retries on failure."""

    is_relevant: bool = Field(
        description="True if relevant to AI auditing, algorithmic accountability, or AI governance"
    )
    relevance_score: float = Field(
        ge=0.0, le=1.0,
        description="0.0–1.0 relevance to AuditChain's services",
    )
    impact_level: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description=(
            "HIGH = mandatory requirements / imminent compliance deadline; "
            "MEDIUM = proposed/consultation stage; LOW = general awareness"
        )
    )
    summary: str = Field(
        min_length=20,
        description="2-3 sentence plain-English summary for a policy audience",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Concrete steps AuditChain should consider",
    )
    keywords: list[str] = Field(
        default_factory=list,
        min_length=0,
        description="5-10 policy/legal keyword tags",
    )

    @field_validator("relevance_score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 3)

    @field_validator("keywords", "action_items")
    @classmethod
    def strip_items(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s.strip()]


# ── Client setup ─────────────────────────────────────────────────────────────

_raw_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

def _get_instructor_client():
    """Return instructor-patched client if available, else None."""
    try:
        import instructor
        return instructor.from_anthropic(_raw_client)
    except ImportError:
        return None


# ── Tool schema for fallback (raw tool_use without instructor) ────────────────

_ANALYSIS_TOOL = {
    "name": "record_analysis",
    "description": "Record the structured analysis. Call exactly once with all fields populated.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_relevant": {"type": "boolean"},
            "relevance_score": {"type": "number"},
            "impact_level": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            "summary": {"type": "string"},
            "action_items": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["is_relevant", "relevance_score", "impact_level", "summary", "action_items", "keywords"],
    },
}

ANALYSIS_SYSTEM_PROMPT = """You are a regulatory intelligence analyst for AuditChain,
a third-party AI/ML model auditing and certification platform focused on African and
emerging market contexts. Your job is to evaluate regulatory and policy documents for
their relevance and impact on AI auditing, algorithmic accountability, and AI governance.

AuditChain's core services:
- Independent algorithmic audits for fairness, transparency, and robustness
- Blockchain-based certification (NFT certificates) for audited models
- Serving clients in fintech, healthcare, government, and enterprise across Africa and Asia"""

ANALYSIS_USER_PROMPT = """Analyze the following regulatory document/announcement.

Source: {source_name} ({region})
Title: {title}
URL: {url}
Content: {content}

Relevance criteria (is_relevant = true if ANY apply):
- Mentions AI auditing, algorithmic accountability, or AI certification requirements
- New or proposed AI/data protection regulations in AuditChain's markets
- Enforcement actions related to AI bias, automated decision-making, or data misuse
- Standards (ISO, IEEE, national) for AI systems
- Government procurement requirements for AI transparency
- Fintech/healthcare AI regulation updates

Impact level:
- HIGH: Mandatory audit requirements, major fines/enforcement, new certification standards, imminent deadlines
- MEDIUM: Proposed regulations under consultation, guidance documents, policy frameworks
- LOW: General digital policy updates, awareness campaigns, no immediate compliance requirement

If is_relevant is false, still provide a brief summary but impact_level should be "LOW"."""


def _content_hash(text: str) -> str:
    """SHA-256 of raw content for deduplication."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def analyze_item(item: RegulationItem) -> dict:
    """
    Analyse a regulation item using instructor (Pydantic validation + auto-retry)
    or fall back to raw tool_use if instructor is not installed.

    instructor pattern (from github.com/instructor-ai/instructor, 12.7k★):
    - Pass response_model=RegulationAnalysis → Claude output is validated against Pydantic schema
    - On ValidationError, instructor feeds the error back to Claude with max_retries=3
    - No manual JSON parsing, no markdown-stripping, no tool_use extraction boilerplate
    """
    prompt = ANALYSIS_USER_PROMPT.format(
        source_name=item.source_name,
        region=item.region,
        title=item.title,
        url=item.url,
        content=(item.raw_content or "")[:3000],
    )

    instructor_client = _get_instructor_client()

    if instructor_client is not None:
        # ── instructor path: Pydantic-validated with automatic retry ──────────
        analysis, completion = await instructor_client.messages.create_with_completion(
            model=settings.anthropic_model,
            max_tokens=1024,
            max_retries=3,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            response_model=RegulationAnalysis,
        )
        return {
            "is_relevant": analysis.is_relevant,
            "relevance_score": analysis.relevance_score,
            "impact_level": analysis.impact_level,
            "summary": analysis.summary,
            "action_items": analysis.action_items,
            "keywords": analysis.keywords,
            "_input_tokens": completion.usage.input_tokens,
            "_output_tokens": completion.usage.output_tokens,
        }

    # ── Fallback: raw tool_use (no instructor) ────────────────────────────────
    message = await _raw_client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=ANALYSIS_SYSTEM_PROMPT,
        tools=[_ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "record_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "record_analysis":
            result = dict(block.input)
            result["_input_tokens"] = message.usage.input_tokens
            result["_output_tokens"] = message.usage.output_tokens
            return result

    raise ValueError("Claude did not return record_analysis tool call")


async def analyze_batch(db: AsyncSession, batch_size: int = 10) -> int:
    """
    Analyse unanalyzed items in batches. Skips items whose content hash matches
    an already-analyzed item — prevents redundant Claude calls for static pages
    re-scraped on consecutive days (content-hash deduplication pattern).
    """
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
            # Content-hash dedup: skip if identical content already analysed
            content_hash = _content_hash(item.raw_content or "")
            existing = await db.execute(
                select(RegulationItem)
                .where(
                    RegulationItem.analyzed == True,  # noqa: E712
                    RegulationItem.content_hash == content_hash,
                    RegulationItem.id != item.id,
                )
                .limit(1)
            )
            duplicate = existing.scalar_one_or_none()
            if duplicate is not None:
                # Copy analysis from the duplicate — zero additional Claude calls
                item.is_relevant = duplicate.is_relevant
                item.relevance_score = duplicate.relevance_score
                item.impact_level = duplicate.impact_level
                item.ai_summary = duplicate.ai_summary
                item.action_items = duplicate.action_items
                item.keywords = duplicate.keywords
                item.content_hash = content_hash
                item.analyzed = True
                item.analyzed_at = datetime.now(timezone.utc)
                await db.flush()
                logger.info(
                    "Content-hash dedup: item %d reused analysis from item %d",
                    item.id, duplicate.id,
                )
                analyzed_count += 1
                continue

            analysis = await analyze_item(item)

            item.is_relevant = analysis.get("is_relevant", False)
            item.relevance_score = float(analysis.get("relevance_score", 0.0))
            item.impact_level = ImpactLevel(analysis.get("impact_level", "LOW"))
            item.ai_summary = analysis.get("summary", "")
            item.action_items = json.dumps(analysis.get("action_items", []))
            item.keywords = json.dumps(analysis.get("keywords", []))
            item.content_hash = content_hash
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

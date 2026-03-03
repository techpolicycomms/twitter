"""
News relevance analyzer.

Uses Claude to score each news item for relevance to AuditChain's mission,
identify rapid-response opportunities, and suggest content angles.
"""

import json
import logging
import re
from typing import List

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NewsItem, Platform
from app.scanner.rss_fetcher import get_unanalyzed_items

logger = logging.getLogger(__name__)
settings = get_settings()

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

ANALYSIS_PROMPT_TEMPLATE = """
You are the editorial intelligence for AuditChain, an AI auditing company focused on:
- Fairness and bias analysis in AI/ML models
- Explainability (SHAP, LIME)
- Robustness testing
- Blockchain-backed audit certificates
- AI governance and regulation globally
- AI deployment in Global South contexts (Africa, India, Southeast Asia)

Analyze the following news items and score each for relevance to AuditChain's content strategy.

NEWS ITEMS:
{items_json}

For each item, return a JSON array in this exact format:
[
  {{
    "id": <item_id>,
    "relevance_score": <float 0.0-1.0>,
    "relevance_reason": "<1-2 sentence explanation of why this is or isn't relevant>",
    "suggested_angle": "<If relevant (score > 0.5): a specific content angle AuditChain could take. Empty string if not relevant.>",
    "is_rapid_response": <true if this is breaking/time-sensitive news that warrants immediate response, false otherwise>
  }},
  ...
]

Scoring guide:
- 0.9–1.0: Directly relevant (AI regulation, bias studies, audit frameworks, blockchain + AI)
- 0.7–0.89: Clearly relevant (AI governance, ML fairness, AI in regulated industries)
- 0.5–0.69: Tangentially relevant (general AI news with fairness/governance angle)
- 0.0–0.49: Not relevant (consumer AI products, AI art, unrelated tech news)

Prioritize Global South relevance — news from Africa, India, Southeast Asia about AI
governance or fairness should score higher than equivalent Western news.

Return ONLY the JSON array. No explanation or preamble.
""".strip()


async def analyze_news_items(
    news_items: List[NewsItem],
    db: AsyncSession,
) -> List[NewsItem]:
    """
    Score a batch of news items for relevance using Claude.

    Sends items in batches of 10 to manage token usage.
    Updates relevance_score, relevance_reason, suggested_angle, and is_rapid_response.

    Args:
        news_items: List of NewsItem objects to analyze.
        db: AsyncSession for persisting updates.

    Returns:
        Updated list of NewsItem objects.
    """
    if not news_items:
        return []

    logger.info(f"Analyzing {len(news_items)} news items for relevance")

    batch_size = 10
    analyzed = []

    for i in range(0, len(news_items), batch_size):
        batch = news_items[i : i + batch_size]
        batch_results = await _analyze_batch(batch)

        # Apply results to the ORM objects
        results_by_id = {r["id"]: r for r in batch_results}
        for item in batch:
            if item.id in results_by_id:
                result = results_by_id[item.id]
                item.relevance_score = result.get("relevance_score", 0.0)
                item.relevance_reason = result.get("relevance_reason", "")
                item.suggested_angle = result.get("suggested_angle", "")
                item.is_rapid_response = result.get("is_rapid_response", False)
                db.add(item)
                analyzed.append(item)
            else:
                logger.warning(f"No analysis result for news item id={item.id}")

    await db.flush()
    logger.info(f"Analysis complete: {len(analyzed)} items scored")
    return analyzed


async def _analyze_batch(batch: List[NewsItem]) -> list:
    """
    Call Claude to analyze a single batch of news items.

    Returns a list of result dicts with id, relevance_score, etc.
    """
    items_data = [
        {
            "id": item.id,
            "title": item.title,
            "summary": (item.summary or "")[:500],
            "feed_name": item.feed_name,
        }
        for item in batch
    ]

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        items_json=json.dumps(items_data, ensure_ascii=False, indent=2)
    )

    try:
        message = _client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_response = message.content[0].text.strip()
        logger.debug(f"Relevance analysis raw response: {raw_response[:200]}...")

        # Extract JSON array from response
        json_match = re.search(r"\[.*\]", raw_response, re.DOTALL)
        if not json_match:
            logger.error("No JSON array found in relevance analysis response")
            return []

        results = json.loads(json_match.group())
        if not isinstance(results, list):
            logger.error("Relevance analysis returned non-list JSON")
            return []

        return results

    except (json.JSONDecodeError, anthropic.APIError, IndexError) as e:
        logger.error(f"News analysis failed: {e}")
        return []


async def run_news_scan_and_analyze(db: AsyncSession) -> dict:
    """
    Full news scanning pipeline:
    1. Fetch all RSS feeds
    2. Persist new items
    3. Analyze unscored items for relevance
    4. Trigger rapid-response generation for high-score items

    Args:
        db: AsyncSession.

    Returns:
        Summary dict with counts.
    """
    from app.scanner.rss_fetcher import fetch_all_feeds

    logger.info("Starting news scan pipeline")

    # Step 1 & 2: Fetch and persist
    new_items = await fetch_all_feeds(db)
    await db.commit()

    # Step 3: Analyze unscored items (includes items from previous runs)
    unanalyzed = await get_unanalyzed_items(db, limit=50)
    if unanalyzed:
        await analyze_news_items(unanalyzed, db)
        await db.commit()

    # Step 4: Find rapid-response candidates
    from sqlalchemy import select
    rapid_stmt = select(NewsItem).where(
        NewsItem.is_rapid_response.is_(True),
        NewsItem.is_processed.is_(False),
        NewsItem.relevance_score >= settings.rapid_response_threshold,
    )
    rapid_result = await db.execute(rapid_stmt)
    rapid_items = rapid_result.scalars().all()

    # Generate rapid-response posts for high-priority items
    from app.content.generator import generate_rapid_response

    rapid_generated = 0
    for item in rapid_items:
        try:
            # Generate for LinkedIn (primary channel for rapid response)
            await generate_rapid_response(item, Platform.LINKEDIN, db)
            rapid_generated += 1
        except Exception as e:
            logger.error(f"Rapid response generation failed for item {item.id}: {e}")

    await db.commit()

    summary = {
        "new_items_fetched": len(new_items),
        "items_analyzed": len(unanalyzed),
        "rapid_responses_generated": rapid_generated,
    }
    logger.info(f"News scan complete: {summary}")
    return summary

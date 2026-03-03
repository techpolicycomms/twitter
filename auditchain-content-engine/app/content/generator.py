"""
Core content generation engine using the Anthropic API.

Generates LinkedIn posts, Twitter threads, and blog articles using Claude.
Streams output for visibility, then persists results to the database.
"""

import json
import logging
import re
from typing import Optional

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.content.prompts import (
    get_prompt_for_platform,
    get_rapid_response_prompt,
)
from app.models import (
    ContentCalendarEntry,
    ContentPillar,
    ContentStatus,
    GeneratedContent,
    NewsItem,
    Platform,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Instantiate the Anthropic client once (thread-safe)
_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ── Core generation ────────────────────────────────────────────────────────


def _generate_with_streaming(prompt: str) -> tuple[str, int, int]:
    """
    Call Claude with streaming enabled.

    Returns a tuple of (full_text, input_tokens, output_tokens).
    Streams to stdout in debug mode for visibility.
    """
    full_text = ""
    input_tokens = 0
    output_tokens = 0

    logger.debug("Starting Claude generation (streaming)...")

    with _client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text_chunk in stream.text_stream:
            full_text += text_chunk
            if settings.debug:
                print(text_chunk, end="", flush=True)

        # Retrieve final message for token counts
        final_message = stream.get_final_message()
        input_tokens = final_message.usage.input_tokens
        output_tokens = final_message.usage.output_tokens

    if settings.debug:
        print()  # newline after streaming output

    logger.info(
        f"Generation complete. Tokens — input: {input_tokens}, output: {output_tokens}"
    )
    return full_text.strip(), input_tokens, output_tokens


def _extract_twitter_thread(raw_text: str) -> tuple[str, int]:
    """
    Parse a Twitter thread from Claude's JSON output.

    Returns (json_body, tweet_count). Falls back to splitting on newlines
    if JSON parsing fails.
    """
    # Try to extract JSON array from the response
    json_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if json_match:
        try:
            tweets = json.loads(json_match.group())
            if isinstance(tweets, list) and all(isinstance(t, str) for t in tweets):
                # Enforce 280-char limit on each tweet
                trimmed = [t[:280] for t in tweets]
                return json.dumps(trimmed, ensure_ascii=False), len(trimmed)
        except json.JSONDecodeError:
            pass

    # Fallback: split on blank lines or numbered lines
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    tweets = [line for line in lines if len(line) > 10][:6]
    return json.dumps(tweets, ensure_ascii=False), len(tweets)


def _extract_hashtags(text: str) -> tuple[str, str]:
    """
    Separate hashtags from the main body of a LinkedIn post.

    Returns (body_without_hashtags, hashtag_string).
    """
    hashtag_pattern = r"((?:#\w+\s*){2,})\s*$"
    match = re.search(hashtag_pattern, text, re.MULTILINE)
    if match:
        hashtags = match.group(1).strip()
        body = text[: match.start()].strip()
        return body, hashtags
    return text, ""


def _count_words(text: str) -> int:
    """Count words in a text string."""
    return len(text.split())


# ── Public API ──────────────────────────────────────────────────────────────


async def generate_from_calendar_entry(
    entry: ContentCalendarEntry,
    db: AsyncSession,
) -> GeneratedContent:
    """
    Generate content for a calendar entry and save it to the database.

    Args:
        entry: The ContentCalendarEntry to generate content for.
        db: AsyncSession for persisting the result.

    Returns:
        The persisted GeneratedContent record.
    """
    logger.info(
        f"Generating {entry.platform.value} content for: '{entry.topic}'"
    )

    prompt = get_prompt_for_platform(
        platform=entry.platform,
        topic=entry.topic,
        pillar=entry.content_pillar,
    )

    raw_text, input_tokens, output_tokens = _generate_with_streaming(prompt)

    # Post-process based on platform
    body, hashtags, word_count, tweet_count = _postprocess(entry.platform, raw_text)

    content = GeneratedContent(
        calendar_entry_id=entry.id,
        platform=entry.platform,
        content_pillar=entry.content_pillar,
        topic=entry.topic,
        body=body,
        hashtags=hashtags or None,
        word_count=word_count,
        tweet_count=tweet_count,
        source_type="calendar",
        status=ContentStatus.PENDING_REVIEW,
        model_used=settings.anthropic_model,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
    )

    db.add(content)

    # Mark the calendar entry as generated
    entry.is_generated = True
    db.add(entry)

    await db.flush()
    await db.refresh(content)

    logger.info(f"Content saved: id={content.id}, platform={content.platform.value}")
    return content


async def generate_manual(
    topic: str,
    platform: Platform,
    pillar: ContentPillar,
    additional_context: str = "",
    db: Optional[AsyncSession] = None,
) -> GeneratedContent:
    """
    Manually trigger content generation outside the calendar flow.

    Args:
        topic: The content topic.
        platform: Target platform.
        pillar: Content pillar category.
        additional_context: Optional extra context for Claude.
        db: AsyncSession (required to persist; if None, returns unsaved object).

    Returns:
        The GeneratedContent record (saved if db provided).
    """
    logger.info(f"Manual generation: {platform.value} — '{topic}'")

    prompt = get_prompt_for_platform(
        platform=platform,
        topic=topic,
        pillar=pillar,
        context=additional_context,
    )

    raw_text, input_tokens, output_tokens = _generate_with_streaming(prompt)
    body, hashtags, word_count, tweet_count = _postprocess(platform, raw_text)

    content = GeneratedContent(
        platform=platform,
        content_pillar=pillar,
        topic=topic,
        body=body,
        hashtags=hashtags or None,
        word_count=word_count,
        tweet_count=tweet_count,
        source_type="manual",
        status=ContentStatus.PENDING_REVIEW,
        model_used=settings.anthropic_model,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
    )

    if db:
        db.add(content)
        await db.flush()
        await db.refresh(content)

    return content


async def generate_rapid_response(
    news_item: NewsItem,
    platform: Platform,
    db: AsyncSession,
) -> GeneratedContent:
    """
    Generate a rapid-response post triggered by high-relevance news.

    Args:
        news_item: The NewsItem that triggered this response.
        platform: Platform to generate content for.
        db: AsyncSession for persisting the result.

    Returns:
        The saved GeneratedContent record.
    """
    logger.info(
        f"Rapid response for: '{news_item.title}' on {platform.value}"
    )

    # Determine the best pillar for this news item
    pillar = _infer_pillar_from_news(news_item)

    prompt = get_rapid_response_prompt(
        news_title=news_item.title,
        news_summary=news_item.summary or "",
        suggested_angle=news_item.suggested_angle or "",
        platform=platform,
        pillar=pillar,
    )

    raw_text, input_tokens, output_tokens = _generate_with_streaming(prompt)
    body, hashtags, word_count, tweet_count = _postprocess(platform, raw_text)

    content = GeneratedContent(
        news_item_id=news_item.id,
        platform=platform,
        content_pillar=pillar,
        topic=f"[RAPID RESPONSE] {news_item.title}",
        body=body,
        hashtags=hashtags or None,
        word_count=word_count,
        tweet_count=tweet_count,
        source_type="rapid_response",
        status=ContentStatus.PENDING_REVIEW,
        model_used=settings.anthropic_model,
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
    )

    db.add(content)
    news_item.is_processed = True
    db.add(news_item)

    await db.flush()
    await db.refresh(content)

    logger.info(f"Rapid response saved: id={content.id}")
    return content


# ── Helpers ────────────────────────────────────────────────────────────────


def _postprocess(
    platform: Platform, raw_text: str
) -> tuple[str, str, Optional[int], Optional[int]]:
    """
    Platform-specific post-processing of Claude's raw output.

    Returns (body, hashtags, word_count, tweet_count).
    """
    if platform == Platform.TWITTER:
        body, tweet_count = _extract_twitter_thread(raw_text)
        return body, "", None, tweet_count

    elif platform == Platform.LINKEDIN:
        body, hashtags = _extract_hashtags(raw_text)
        return body, hashtags, _count_words(body), None

    elif platform == Platform.BLOG:
        return raw_text, "", _count_words(raw_text), None

    return raw_text, "", None, None


def _infer_pillar_from_news(news_item: NewsItem) -> ContentPillar:
    """
    Heuristically assign a content pillar based on news item metadata.
    Falls back to REGULATORY_UPDATES for policy news.
    """
    text = f"{news_item.title} {news_item.summary or ''}".lower()

    if any(kw in text for kw in ["regulation", "policy", "law", "act", "governance", "compliance"]):
        return ContentPillar.REGULATORY_UPDATES
    elif any(kw in text for kw in ["bias", "fairness", "discrimination", "disparity"]):
        return ContentPillar.AI_FAIRNESS
    elif any(kw in text for kw in ["blockchain", "certificate", "audit", "verify"]):
        return ContentPillar.BLOCKCHAIN_TRUST
    elif any(kw in text for kw in ["case", "example", "company", "bank", "hospital"]):
        return ContentPillar.CASE_STUDIES
    else:
        return ContentPillar.REGULATORY_UPDATES

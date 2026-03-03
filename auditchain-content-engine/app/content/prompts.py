"""
Prompt templates for each platform and content pillar.

Brand voice guidelines baked into every prompt:
- Authoritative but accessible
- Global South perspective (Africa, India, Southeast Asia lens)
- Technical but not jargon-heavy — define terms on first use
- Pragmatic, solutions-oriented
- Never condescending toward non-Western contexts
"""

from app.models import ContentPillar, Platform

BRAND_VOICE_PREAMBLE = """
You are the content writer for AuditChain, a third-party AI auditing company that certifies AI/ML models for fairness, explainability, and robustness using blockchain-backed certificates.

Brand voice guidelines:
- Authoritative and credible — we are technical experts, not cheerleaders
- Accessible — explain technical concepts clearly; define jargon on first use
- Global South perspective — acknowledge that AI challenges in Africa, India, Southeast Asia have unique context; avoid centering only Western regulatory frameworks
- Practical — focus on real implications for practitioners, not just theory
- Confident but humble — acknowledge complexity and uncertainty where it exists
- No hyperbole, no buzzword stacking, no "AI will change everything" clichés
""".strip()

PILLAR_CONTEXT = {
    ContentPillar.AI_FAIRNESS: """
Content pillar: AI Fairness
Focus: Concrete fairness metrics (demographic parity, equalized odds, disparate impact),
real-world implications of unfair models, and practical mitigation strategies.
Emphasize how bias manifests differently across different demographic contexts globally.
""".strip(),

    ContentPillar.REGULATORY_UPDATES: """
Content pillar: Regulatory Updates
Focus: Translating complex regulatory developments (EU AI Act, OECD AI Principles,
India's AI governance framework, African Union AI policy) into practical implications.
Help practitioners understand what they need to DO, not just what the rules say.
""".strip(),

    ContentPillar.BLOCKCHAIN_TRUST: """
Content pillar: Blockchain Trust
Focus: Why blockchain-based audit certificates matter for AI governance —
immutability, public verifiability, tamper-proof audit trails.
Be honest about limitations; don't oversell blockchain as a silver bullet.
""".strip(),

    ContentPillar.CASE_STUDIES: """
Content pillar: Case Studies
Focus: Real-world examples of AI auditing in practice — what went wrong,
what auditors found, how organizations responded.
Use anonymized or composite examples where confidentiality requires.
Make the learnings concrete and transferable.
""".strip(),

    ContentPillar.BEHIND_THE_SCENES: """
Content pillar: Behind the Scenes
Focus: Demystifying the audit process — how SHAP works, what an audit pipeline
looks like from inside, the decisions auditors make.
Builds trust by showing our work. Technical depth is welcome here.
""".strip(),
}


def get_linkedin_prompt(topic: str, pillar: ContentPillar, context: str = "") -> str:
    """Generate a LinkedIn thought leadership post prompt."""
    return f"""{BRAND_VOICE_PREAMBLE}

{PILLAR_CONTEXT[pillar]}

Task: Write a LinkedIn thought leadership post about the following topic.

Topic: {topic}
{f"Additional context: {context}" if context else ""}

Requirements:
- Length: 200–300 words exactly
- Format: No headers or bullet points — flowing paragraphs work best on LinkedIn
- Opening hook: Start with a counterintuitive observation, a specific statistic,
  or a question that challenges conventional wisdom. Do NOT start with "I" or "We".
- Structure: Hook → insight → implication → call to action
- Include a "key takeaway" line near the end
- End with 4–6 relevant hashtags on a new line
  (include #AIAudit #AuditChain plus topic-specific ones)
- Tone: Practitioner-to-practitioner; assume the reader is technically literate
  but not necessarily an ML researcher

Output only the post text. No preamble or explanation."""


def get_twitter_prompt(topic: str, pillar: ContentPillar, context: str = "") -> str:
    """Generate a Twitter/X thread prompt."""
    return f"""{BRAND_VOICE_PREAMBLE}

{PILLAR_CONTEXT[pillar]}

Task: Write a Twitter/X thread about the following topic.

Topic: {topic}
{f"Additional context: {context}" if context else ""}

Requirements:
- 4–6 tweets in the thread
- Tweet 1 (hook): The most compelling, shareable single insight.
  Must stand alone as a quote-tweet. End with "🧵 Thread:"
- Tweets 2–N: Build the argument or narrative progressively.
  Each tweet should work as a standalone point but flow naturally from the previous.
- Last tweet: Summarize with a clear actionable takeaway + tag @AuditChain
- Each tweet: MAX 280 characters (count carefully — be precise)
- Include 1–2 relevant emojis per tweet where natural, not forced
- Relevant hashtags in the final tweet only

Format your output as a JSON array of strings, one string per tweet.
Example: ["Tweet 1 text", "Tweet 2 text", "Tweet 3 text"]

Output only the JSON array. No other text."""


def get_blog_prompt(topic: str, pillar: ContentPillar, context: str = "") -> str:
    """Generate an SEO-optimized blog article prompt."""
    return f"""{BRAND_VOICE_PREAMBLE}

{PILLAR_CONTEXT[pillar]}

Task: Write an SEO-optimized blog article for the AuditChain website.

Topic: {topic}
{f"Additional context: {context}" if context else ""}

Requirements:
- Length: 800–1200 words
- SEO: Include the main keyword naturally in the first paragraph, H2 headings,
  and conclusion. Write for humans first, search engines second.
- Structure:
  * H1 title (compelling, includes primary keyword)
  * Introduction (100–150 words): state the problem, why it matters, what the article covers
  * 3–4 H2 sections with substantive content
  * Practical implications section (what should practitioners DO?)
  * Conclusion with a clear call to action (link to audit submission or newsletter)
- Include a "Key Takeaways" bullet list near the end (4–6 points)
- Tone: Expert but approachable. Define technical terms on first use.
- Global perspective: At least one section or example should reference
  AI deployment contexts outside the US/EU

Format: Markdown
Output only the article. No preamble or explanation."""


def get_rapid_response_prompt(
    news_title: str,
    news_summary: str,
    suggested_angle: str,
    platform: Platform,
    pillar: ContentPillar,
) -> str:
    """Generate a rapid-response post for breaking news."""
    base = f"""{BRAND_VOICE_PREAMBLE}

{PILLAR_CONTEXT[pillar]}

BREAKING NEWS CONTEXT:
Headline: {news_title}
Summary: {news_summary}
Suggested angle: {suggested_angle}

Task: Write a rapid-response {platform.value} post commenting on this news
from AuditChain's perspective as an AI auditing company.

Be timely and relevant. Acknowledge the news explicitly.
Add AuditChain's distinctive perspective — what does this mean for AI auditing practitioners?
"""

    if platform == Platform.LINKEDIN:
        return base + """
Requirements:
- 150–250 words (shorter than usual — speed matters for rapid response)
- Start with a reference to the news
- Share AuditChain's distinctive take
- End with practical implication + hashtags
Output only the post."""

    elif platform == Platform.TWITTER:
        return base + """
Requirements:
- 3–4 tweet thread responding to the news
- Tweet 1: Acknowledge the news + our hot take
- Subsequent tweets: Context, implications, AuditChain perspective
- Each tweet MAX 280 characters
Format as JSON array of strings.
Output only the JSON array."""

    else:
        return base + """
Requirements:
- 400–600 words (rapid analysis piece, not a full article)
- Format in Markdown
Output only the article."""


def get_prompt_for_platform(
    platform: Platform,
    topic: str,
    pillar: ContentPillar,
    context: str = "",
) -> str:
    """Route to the correct prompt template based on platform."""
    if platform == Platform.LINKEDIN:
        return get_linkedin_prompt(topic, pillar, context)
    elif platform == Platform.TWITTER:
        return get_twitter_prompt(topic, pillar, context)
    elif platform == Platform.BLOG:
        return get_blog_prompt(topic, pillar, context)
    else:
        raise ValueError(f"Unknown platform: {platform}")

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

import fresh_newsletter_agent as fresh
import newsletter_agent as agent

_ORIGINAL_CLEAN_TEXT = agent.clean_text
_ORIGINAL_REMOVE_RSS_NOISE = agent.remove_rss_noise

SMART_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u2026": "...",
    }
)

BOILERPLATE_PATTERNS = (
    r"^this is today's edition of the download\b.*",
    r"\bstay on top of what's going on in ai this summer\b.*",
    r"\bhere at mit technology review, we understand exactly how relentless\b.*",
    r"^our weekday newsletter\b.*",
)

ENHANCED_FEEDS = {
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "Google AI Blog": "https://blog.google/technology/ai/rss/",
    "Google Cloud AI": "https://cloud.google.com/blog/products/rss",
    "GitHub AI & ML": "https://github.blog/ai-and-ml/feed/",
    "Microsoft Developer Blog": "https://devblogs.microsoft.com/feed/",
    "The New Stack": "https://thenewstack.io/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
}

ENHANCED_FEED_ENV_OVERRIDES = {
    "OpenAI News": "OPENAI_NEWS_RSS_URL",
    "Anthropic News": "ANTHROPIC_NEWS_RSS_URL",
    "Google AI Blog": "GOOGLE_AI_BLOG_RSS_URL",
    "Google Cloud AI": "GOOGLE_CLOUD_AI_RSS_URL",
    "GitHub AI & ML": "GITHUB_AI_RSS_URL",
    "Microsoft Developer Blog": "MICROSOFT_DEV_BLOG_RSS_URL",
    "The New Stack": "THE_NEW_STACK_RSS_URL",
    "VentureBeat AI": "VENTUREBEAT_AI_RSS_URL",
}

ENHANCED_SOURCE_BONUSES = {
    "OpenAI News": 5,
    "Anthropic News": 5,
    "Google AI Blog": 5,
    "Google Cloud AI": 4,
    "GitHub AI & ML": 4,
    "Microsoft Developer Blog": 3,
    "The New Stack": 3,
    "VentureBeat AI": 3,
}

CORE_RELEVANCE_PHRASES = (
    "ai",
    "artificial intelligence",
    "agent",
    "agents",
    "agentic",
    "automation",
    "autonomous",
    "chatbot",
    "claude",
    "claude code",
    "copilot",
    "deep learning",
    "developer tool",
    "developer tools",
    "foundation model",
    "frontier model",
    "generative",
    "gemini",
    "inference",
    "language model",
    "large language model",
    "llm",
    "machine learning",
    "mcp",
    "model context protocol",
    "multimodal",
    "openai",
    "product management",
    "product manager",
    "product managers",
    "product strategy",
    "prompt",
    "qwen",
    "reasoning",
    "roadmap",
    "synthetic data",
    "user research",
    "vertex ai",
)

LOW_SIGNAL_TITLE_PREFIXES = (
    "ask hn:",
    "show hn:",
    "tell hn:",
    "launch hn:",
    "the download:",
    "who is hiring",
    "who wants to be hired",
)

LOW_SIGNAL_PHRASES = (
    "comments",
    "discussion",
    "upvote",
    "poll:",
    "thread",
)

CATEGORY_RULES = (
    (
        "Research",
        (
            "benchmark",
            "deepmind",
            "paper",
            "research",
            "study",
            "turing test",
        ),
    ),
    (
        "Code & Tools",
        (
            "api",
            "claude code",
            "copilot",
            "developer",
            "github",
            "mcp",
            "sdk",
            "toolkit",
            "vertex ai",
        ),
    ),
    (
        "Product Updates",
        (
            "announces",
            "introducing",
            "launch",
            "model",
            "product",
            "qwen",
            "release",
            "update",
        ),
    ),
    (
        "Risk & Governance",
        (
            "compliance",
            "governance",
            "policy",
            "regulation",
            "risk",
            "safety",
            "security",
            "vulnerability",
        ),
    ),
    (
        "Events",
        (
            "conference",
            "event",
            "summit",
            "webinar",
            "workshop",
        ),
    ),
    (
        "Product Thinking",
        (
            "customer",
            "growth",
            "pricing",
            "product management",
            "product manager",
            "roadmap",
            "user research",
        ),
    ),
)


@dataclass(frozen=True)
class EnhancedNewsletterStory:
    source: str
    title: str
    link: str
    published: str
    summary: str
    category: str


def normalize_punctuation(value: str | None) -> str:
    if not value:
        return ""
    return str(value).translate(SMART_PUNCTUATION_TRANSLATION)


def clean_text(value: str | None, max_chars: int = 700) -> str:
    return _ORIGINAL_CLEAN_TEXT(normalize_punctuation(value), max_chars=max_chars)


def remove_boilerplate(text: str) -> str:
    cleaned = text
    for pattern in BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return re.sub(r"\s+", " ", cleaned).strip()


def remove_rss_noise(value: str) -> str:
    text = _ORIGINAL_REMOVE_RSS_NOISE(normalize_punctuation(value))
    return remove_boilerplate(text)


def configure_quality_sources() -> None:
    agent.clean_text = clean_text
    agent.remove_rss_noise = remove_rss_noise
    agent.DEFAULT_FEEDS.update(ENHANCED_FEEDS)
    agent.FEED_ENV_OVERRIDES.update(ENHANCED_FEED_ENV_OVERRIDES)
    agent.SOURCE_BONUSES.update(ENHANCED_SOURCE_BONUSES)


def story_text(story: agent.StoryCandidate) -> str:
    return f"{story.title} {story.excerpt}".lower()


def has_core_relevance(story: agent.StoryCandidate) -> bool:
    text = story_text(story)
    return any(agent.text_contains_phrase(text, phrase) for phrase in CORE_RELEVANCE_PHRASES)


def has_low_signal_title(story: agent.StoryCandidate) -> bool:
    title = story.title.strip().lower()
    return any(title.startswith(prefix) for prefix in LOW_SIGNAL_TITLE_PREFIXES)


def has_low_signal_text(story: agent.StoryCandidate) -> bool:
    text = story_text(story)
    return any(agent.text_contains_phrase(text, phrase) for phrase in LOW_SIGNAL_PHRASES)


def quality_score(story: agent.StoryCandidate) -> int:
    score = agent.story_relevance_score(story)
    if has_core_relevance(story):
        score += 6
    if story.excerpt:
        score += 2
    if story.source in ENHANCED_SOURCE_BONUSES:
        score += 2
    if has_low_signal_title(story):
        score -= 8
    if story.source == "Hacker News" and not story.excerpt:
        score -= 6
    if story.source == "Hacker News" and has_low_signal_text(story):
        score -= 4
    return score


def is_quality_story(
    story: agent.StoryCandidate,
    min_relevance_score: int,
    hacker_news_min_relevance_score: int,
    require_core_relevance: bool,
) -> bool:
    if require_core_relevance and not has_core_relevance(story):
        return False
    if has_low_signal_title(story):
        return False

    minimum_score = min_relevance_score
    if story.source == "Hacker News":
        minimum_score = max(minimum_score, hacker_news_min_relevance_score)
    return quality_score(story) >= minimum_score


def filter_quality_stories(candidates: list[agent.StoryCandidate]) -> list[agent.StoryCandidate]:
    min_relevance_score = agent.int_env("MIN_RELEVANCE_SCORE", 10)
    hacker_news_min_relevance_score = agent.int_env("HACKER_NEWS_MIN_RELEVANCE_SCORE", 14)
    require_core_relevance = fresh.bool_env("REQUIRE_CORE_RELEVANCE", True)

    filtered = [
        story
        for story in candidates
        if is_quality_story(
            story=story,
            min_relevance_score=min_relevance_score,
            hacker_news_min_relevance_score=hacker_news_min_relevance_score,
            require_core_relevance=require_core_relevance,
        )
    ]
    return sorted(filtered, key=lambda story: (-quality_score(story), story.id))


def clean_display_title(title: str) -> str:
    raw_title = clean_text(title, max_chars=220)
    if " | " in raw_title:
        left, right = raw_title.rsplit(" | ", 1)
        if 1 <= len(right.split()) <= 5:
            raw_title = left
    cleaned = remove_rss_noise(raw_title)
    return cleaned.strip() or title


def infer_category(story: agent.NewsletterStory) -> str:
    text = f"{story.source} {story.title} {story.summary} {story.link}".lower()
    if "youtube.com" in text or "youtu.be" in text:
        return "Video"
    if "spotify.com" in text or "podcast" in text:
        return "Podcast"
    for category, phrases in CATEGORY_RULES:
        if any(agent.text_contains_phrase(text, phrase) for phrase in phrases):
            return category
    return "Highlights"


def starts_with_vowel_sound(value: str) -> bool:
    return bool(value) and value[0].lower() in {"a", "e", "i", "o", "u"}


def sentence_from_title(title: str) -> str:
    lower_title = title[:1].lower() + title[1:]
    article = "an" if starts_with_vowel_sound(lower_title) else "a"
    return f"This story explains {article} {lower_title}."


def practical_impact_sentence(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    if any(word in text for word in ("spell", "misspell", "accuracy", "hallucination", "reliability")):
        return "For product teams, it is a reminder that AI features need quality checks before users trust the output."
    if any(word in text for word in ("download", "newsletter", "roundup")):
        return "For readers, the useful point is to focus on the specific AI or product update rather than the newsletter promotion around it."
    return agent.DEFAULT_SUMMARY_FALLBACK


def polish_summary(story: agent.NewsletterStory, title: str) -> str:
    summary = remove_rss_noise(story.summary)
    lowered = summary.lower()
    if not summary or any(
        phrase in lowered
        for phrase in (
            "embarrassing itself",
            "this is today's edition of the download",
            "stay on top of what's going on in ai this summer",
            "the key takeaway is what this could change",
        )
    ):
        return f"{sentence_from_title(title)} {practical_impact_sentence(title, summary)}"
    return summary


def enhance_newsletter_stories(stories: list[agent.NewsletterStory]) -> list[EnhancedNewsletterStory]:
    enhanced_stories: list[EnhancedNewsletterStory] = []
    for story in stories:
        title = clean_display_title(story.title)
        enhanced_stories.append(
            EnhancedNewsletterStory(
                source=story.source,
                title=title,
                link=story.link,
                published=story.published,
                summary=polish_summary(story, title),
                category=infer_category(story),
            )
        )
    return enhanced_stories


def run(dry_run: bool = False, preview_file: Path | None = None) -> None:
    agent.load_environment()
    configure_quality_sources()
    max_per_feed = agent.int_env("MAX_ITEMS_PER_FEED", 10)
    max_age_hours = agent.int_env("MAX_STORY_AGE_HOURS", 24)
    include_undated = fresh.bool_env("INCLUDE_UNDATED_STORIES", False)
    history_path = fresh.history_file_path()
    history = fresh.prune_sent_history(
        fresh.load_sent_history(history_path),
        agent.int_env("SENT_HISTORY_DAYS", 45),
    )

    candidates = fresh.fetch_fresh_stories(
        max_per_feed=max_per_feed,
        max_age_hours=max_age_hours,
        include_undated=include_undated,
    )
    unsent_candidates = fresh.filter_unsent_stories(candidates, history)
    quality_candidates = fresh.reassign_story_ids(filter_quality_stories(unsent_candidates))
    if not quality_candidates:
        raise RuntimeError(
            "No fresh, relevant, unsent stories were found. The newsletter was not sent to avoid low-quality filler."
        )

    stories = enhance_newsletter_stories(fresh.pick_fresh_top_stories(quality_candidates))
    html_body = agent.render_newsletter(stories)

    if dry_run:
        preview_path = preview_file or agent.BASE_DIR / "newsletter_preview.html"
        preview_path.write_text(html_body, encoding="utf-8")
        print(f"Dry run complete. Preview written to {preview_path}")
        return

    results = agent.send_newsletter(stories, html_body)
    updated_history = fresh.record_sent_stories(history, stories)
    fresh.save_sent_history(
        history_path,
        fresh.prune_sent_history(updated_history, agent.int_env("SENT_HISTORY_DAYS", 45)),
    )
    print(f"Sent newsletter to {len(results)} subscriber(s) with {len(stories)} quality fresh story/stories.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Curate and send a quality-checked fresh newsletter.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the newsletter HTML without sending email.",
    )
    parser.add_argument(
        "--preview-file",
        type=Path,
        help="Where to write the HTML preview when using --dry-run.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(dry_run=args.dry_run, preview_file=args.preview_file)

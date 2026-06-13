from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

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
    "Microsoft Tech Community AI": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=AIMachineLearningBlog",
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
    "Microsoft Tech Community AI": "MICROSOFT_TECH_COMMUNITY_AI_RSS_URL",
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
    "Microsoft Tech Community AI": 4,
    "Global AI Weekly": 4,
    "The New Stack": 3,
    "VentureBeat AI": 3,
}

GLOBAL_AI_WEEKLY_URL = "https://globalai.community/weekly/"
GLOBAL_AI_WEEKLY_ALLOWED_DOMAINS = (
    "anthropic.com",
    "arxiv.org",
    "blog.google",
    "developers.googleblog.com",
    "devblogs.microsoft.com",
    "github.blog",
    "qwen.ai",
    "techcommunity.microsoft.com",
)

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
    "subscription",
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
    "take our ",
    "who is hiring",
    "who wants to be hired",
)

LOW_SIGNAL_TITLE_PHRASES = (
    "vibe coded",
    " quiz",
    "wallpaper",
    "wallpapers",
    "roundup",
    "weekly recap",
)

LOW_SIGNAL_PHRASES = (
    "comments",
    "discussion",
    "upvote",
    "poll:",
    "thread",
)

GENERIC_TEMPLATE_PHRASES = (
    "the key takeaway",
    "the main takeaway",
    "what this could change",
    "for product teams",
    "for product and business teams",
    "for builders",
    "for readers",
    "for leaders",
    "it is a reminder to look closely",
    "look closely at cost, trade-offs",
    "where the technology creates real value",
    "the important question is whether",
    "the useful signal is",
    "this story explains",
    "this brief highlights",
    "this matters because",
    "creates a clearer, faster, or cheaper way",
    "teams, customers, products, or the tools people choose next",
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
            "subscription",
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


@dataclass(frozen=True)
class GlobalAIWeeklyItem:
    title: str
    link: str
    description: str


class WeeklyIndexParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.issue_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        absolute_url = urljoin(self.base_url, href)
        if re.search(r"/weekly/\d+/?$", absolute_url) and absolute_url not in self.issue_links:
            self.issue_links.append(absolute_url)


class WeeklyIssueParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.items: list[GlobalAIWeeklyItem] = []
        self.in_heading = False
        self.in_heading_link = False
        self.heading_href = ""
        self.heading_text_parts: list[str] = []
        self.pending_title = ""
        self.pending_link = ""
        self.in_description = False
        self.description_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self._flush_pending_item()
            self.in_heading = True
            self.heading_href = ""
            self.heading_text_parts = []
            return
        if self.in_heading and tag == "a":
            href = dict(attrs).get("href") or ""
            self.heading_href = urljoin(self.base_url, href)
            self.in_heading_link = True
            return
        if self.pending_title and tag == "p":
            self.in_description = True
            self.description_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_heading_link:
            self.in_heading_link = False
            return
        if tag == "h2" and self.in_heading:
            self.in_heading = False
            self.pending_title = clean_text(" ".join(self.heading_text_parts), max_chars=220)
            self.pending_link = self.heading_href
            return
        if tag == "p" and self.in_description:
            self.in_description = False
            self._flush_pending_item()

    def handle_data(self, data: str) -> None:
        if self.in_heading_link:
            self.heading_text_parts.append(data)
        elif self.in_description:
            self.description_parts.append(data)

    def _flush_pending_item(self) -> None:
        if not self.pending_title or not self.pending_link:
            self._clear_pending_item()
            return
        description = remove_rss_noise(" ".join(self.description_parts))
        if description and is_allowed_global_ai_domain(self.pending_link):
            self.items.append(
                GlobalAIWeeklyItem(
                    title=self.pending_title,
                    link=self.pending_link,
                    description=description,
                )
            )
        self._clear_pending_item()

    def _clear_pending_item(self) -> None:
        self.pending_title = ""
        self.pending_link = ""
        self.description_parts = []
        self.in_description = False


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


def configured_allowed_global_ai_domains() -> tuple[str, ...]:
    configured = os.getenv("GLOBAL_AI_WEEKLY_ALLOWED_DOMAINS")
    if not configured:
        return GLOBAL_AI_WEEKLY_ALLOWED_DOMAINS
    return tuple(domain.strip().lower() for domain in configured.split(",") if domain.strip())


def is_allowed_global_ai_domain(url: str) -> bool:
    hostname = urlparse(url).netloc.lower().removeprefix("www.")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in configured_allowed_global_ai_domains()
    )


def fetch_url_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "tap-brief-newsletter-agent/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def latest_global_ai_weekly_issue_url(index_url: str) -> str | None:
    parser = WeeklyIndexParser(index_url)
    parser.feed(fetch_url_text(index_url))
    return parser.issue_links[0] if parser.issue_links else None


def parse_global_ai_issue_items(issue_url: str, html_text: str) -> list[GlobalAIWeeklyItem]:
    parser = WeeklyIssueParser(issue_url)
    parser.feed(html_text)
    parser.close()
    parser._flush_pending_item()
    return parser.items


def fetch_global_ai_weekly_candidates(start_id: int) -> list[agent.StoryCandidate]:
    if os.getenv("INCLUDE_GLOBAL_AI_WEEKLY", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        return []

    index_url = os.getenv("GLOBAL_AI_WEEKLY_URL", GLOBAL_AI_WEEKLY_URL)
    try:
        issue_url = latest_global_ai_weekly_issue_url(index_url)
        if not issue_url:
            return []
        issue_html = fetch_url_text(issue_url)
        items = parse_global_ai_issue_items(issue_url, issue_html)
    except Exception as exc:  # pragma: no cover - network/source failure path
        print(f"Warning: could not fetch Global AI Weekly: {exc}")
        return []

    candidates: list[agent.StoryCandidate] = []
    for item in items:
        if not item.description:
            continue
        candidates.append(
            agent.StoryCandidate(
                id=start_id + len(candidates),
                source="Global AI Weekly",
                title=item.title,
                link=item.link,
                published="",
                excerpt=item.description[:500],
            )
        )
    return candidates


def dedupe_candidates(candidates: list[agent.StoryCandidate]) -> list[agent.StoryCandidate]:
    seen: set[str] = set()
    deduped: list[agent.StoryCandidate] = []
    for story in candidates:
        fingerprint = fresh.story_fingerprint(story)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped.append(story)
    return deduped


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
    return any(title.startswith(prefix) for prefix in LOW_SIGNAL_TITLE_PREFIXES) or any(
        phrase in title for phrase in LOW_SIGNAL_TITLE_PHRASES
    )


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
        score -= 12
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


def clarify_display_title(title: str) -> str:
    lower_title = title.lower()
    if "groq" in lower_title and "raising" in lower_title and "not-acqui-hire" in lower_title:
        return "Groq reportedly raising $650M as AI chip competition heats up"
    if "google ai studio" in lower_title and ("quiz" in lower_title or "vibe coded" in lower_title):
        return "Google shows an AI Studio-built I/O 2026 quiz"
    return title


def clean_display_title(title: str) -> str:
    raw_title = clean_text(title, max_chars=220)
    if " | " in raw_title:
        left, right = raw_title.rsplit(" | ", 1)
        if 1 <= len(right.split()) <= 5:
            raw_title = left
    cleaned = remove_rss_noise(raw_title).strip() or title
    return clarify_display_title(cleaned)


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


def normalized_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_punctuation(value).lower())


def summary_echoes_title(summary: str, title: str) -> bool:
    summary_words = normalized_words(summary)
    title_words = normalized_words(title)
    if not summary_words or not title_words:
        return False

    normalized_summary = " ".join(summary_words)
    normalized_title = " ".join(title_words)
    if normalized_summary.startswith(normalized_title):
        return True

    overlap = len(set(summary_words[: min(len(summary_words), len(title_words) + 3)]) & set(title_words))
    return overlap >= max(5, int(len(set(title_words)) * 0.75))


def has_generic_template_phrase(summary: str) -> bool:
    lowered = normalize_punctuation(summary).lower()
    return any(phrase in lowered for phrase in GENERIC_TEMPLATE_PHRASES)


def is_weak_summary(summary: str, title: str) -> bool:
    cleaned_summary = remove_rss_noise(summary)
    if len(agent.split_sentences(cleaned_summary)) < 2:
        return True
    return has_generic_template_phrase(cleaned_summary) or summary_echoes_title(cleaned_summary, title)


def polish_summary(story: agent.NewsletterStory, title: str) -> str:
    summary = remove_rss_noise(story.summary)
    if is_weak_summary(summary, title):
        return ""
    return summary


def enhance_newsletter_stories(stories: list[agent.NewsletterStory]) -> list[EnhancedNewsletterStory]:
    enhanced_stories: list[EnhancedNewsletterStory] = []
    for story in stories:
        title = clean_display_title(story.title)
        summary = polish_summary(story, title)
        if not summary:
            print(f"Warning: skipped low-quality summary for {story.source}: {title}")
            continue
        enhanced_stories.append(
            EnhancedNewsletterStory(
                source=story.source,
                title=title,
                link=story.link,
                published=story.published,
                summary=summary,
                category=infer_category(story),
            )
        )
    if not enhanced_stories:
        raise RuntimeError("All selected stories had weak summaries, so the newsletter was not sent.")
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

    rss_candidates = fresh.fetch_fresh_stories(
        max_per_feed=max_per_feed,
        max_age_hours=max_age_hours,
        include_undated=include_undated,
    )
    global_ai_candidates = fetch_global_ai_weekly_candidates(start_id=len(rss_candidates) + 1)
    candidates = dedupe_candidates(global_ai_candidates + rss_candidates)
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

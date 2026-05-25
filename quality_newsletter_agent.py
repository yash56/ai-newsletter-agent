from __future__ import annotations

import argparse
import os
from pathlib import Path

import fresh_newsletter_agent as fresh
import newsletter_agent as agent

CORE_RELEVANCE_PHRASES = (
    "ai",
    "artificial intelligence",
    "agent",
    "agents",
    "agentic",
    "automation",
    "autonomous",
    "chatbot",
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
    "multimodal",
    "openai",
    "product management",
    "product manager",
    "product managers",
    "product strategy",
    "prompt",
    "reasoning",
    "roadmap",
    "user research",
)

LOW_SIGNAL_TITLE_PREFIXES = (
    "ask hn:",
    "show hn:",
    "tell hn:",
    "launch hn:",
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


def run(dry_run: bool = False, preview_file: Path | None = None) -> None:
    agent.load_environment()
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

    stories = fresh.pick_fresh_top_stories(quality_candidates)
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

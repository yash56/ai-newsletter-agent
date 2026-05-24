from __future__ import annotations

import argparse
import calendar
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser

import newsletter_agent as agent


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def story_fingerprint(story_or_link: agent.StoryCandidate | agent.NewsletterStory | str) -> str:
    if isinstance(story_or_link, str):
        link = story_or_link
    else:
        link = story_or_link.link
    normalized = link.strip().lower().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return normalized or link.strip().lower()


def history_file_path() -> Path:
    return Path(os.getenv("SENT_HISTORY_FILE", str(agent.BASE_DIR / "sent_history.json")))


def load_sent_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sent_links": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Warning: sent history file is malformed, starting fresh: {path}")
        return {"sent_links": {}}

    sent_links = data.get("sent_links") if isinstance(data, dict) else None
    if isinstance(sent_links, dict):
        return {"sent_links": {str(key): str(value) for key, value in sent_links.items()}}
    return {"sent_links": {}}


def prune_sent_history(history: dict[str, Any], retention_days: int) -> dict[str, Any]:
    sent_links = history.get("sent_links", {})
    if retention_days <= 0:
        return {"sent_links": {}}

    cutoff = date.today() - timedelta(days=retention_days)
    pruned: dict[str, str] = {}
    for fingerprint, sent_on in sent_links.items():
        try:
            sent_date = date.fromisoformat(str(sent_on))
        except ValueError:
            continue
        if sent_date >= cutoff:
            pruned[str(fingerprint)] = sent_date.isoformat()
    return {"sent_links": pruned}


def save_sent_history(path: Path, history: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")


def record_sent_stories(history: dict[str, Any], stories: list[agent.NewsletterStory]) -> dict[str, Any]:
    sent_links = dict(history.get("sent_links", {}))
    today = date.today().isoformat()
    for story in stories:
        sent_links[story_fingerprint(story)] = today
    return {"sent_links": sent_links}


def filter_unsent_stories(
    candidates: list[agent.StoryCandidate],
    history: dict[str, Any],
) -> list[agent.StoryCandidate]:
    sent_links = set(history.get("sent_links", {}).keys())
    return [story for story in candidates if story_fingerprint(story) not in sent_links]


def entry_datetime(entry: Any) -> datetime | None:
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed_time:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=timezone.utc)


def within_freshness_window(entry: Any, cutoff: datetime | None, include_undated: bool) -> bool:
    if cutoff is None:
        return True
    published_at = entry_datetime(entry)
    if published_at is None:
        return include_undated
    return published_at >= cutoff


def reassign_story_ids(candidates: list[agent.StoryCandidate]) -> list[agent.StoryCandidate]:
    return [
        agent.StoryCandidate(
            id=index,
            source=story.source,
            title=story.title,
            link=story.link,
            published=story.published,
            excerpt=story.excerpt,
        )
        for index, story in enumerate(candidates, start=1)
    ]


def fetch_fresh_stories(
    max_per_feed: int = 10,
    max_age_hours: int = 24,
    include_undated: bool = False,
) -> list[agent.StoryCandidate]:
    stories: list[agent.StoryCandidate] = []
    seen: set[str] = set()
    cutoff = None
    if max_age_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for source, feed_url in agent.configured_feeds().items():
        parsed = feedparser.parse(feed_url)
        if getattr(parsed, "bozo", False):
            print(f"Warning: feedparser reported an issue for {source}: {parsed.bozo_exception}")

        for entry in parsed.entries[:max_per_feed]:
            if not within_freshness_window(entry, cutoff, include_undated):
                continue

            title = agent.clean_text(entry.get("title"), max_chars=220)
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            fingerprint = story_fingerprint(link) or re.sub(r"\s+", " ", title.lower()).strip()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            excerpt = agent.remove_rss_noise(
                entry.get("summary") or entry.get("description") or entry.get("subtitle") or ""
            )[:500]
            stories.append(
                agent.StoryCandidate(
                    id=len(stories) + 1,
                    source=source,
                    title=title,
                    link=link,
                    published=agent.clean_text(entry.get("published") or entry.get("updated"), 120),
                    excerpt=excerpt,
                )
            )

    return stories


def max_selectable_story_count(
    candidates: list[agent.StoryCandidate],
    max_stories_per_source: int,
    target_count: int,
) -> int:
    source_counts = Counter(story.source for story in candidates)
    available = sum(min(count, max_stories_per_source) for count in source_counts.values())
    return min(target_count, available)


def select_fresh_story_ids(
    client: Any,
    model: str,
    candidates: list[agent.StoryCandidate],
    max_candidates: int,
    max_stories_per_source: int,
    max_output_tokens: int,
    target_count: int,
) -> list[int]:
    candidate_payload = [
        {
            "id": story.id,
            "source": story.source,
            "title": story.title,
            "published": story.published,
            "excerpt": story.excerpt,
        }
        for story in candidates[:max_candidates]
    ]
    example = ", ".join(str(story["id"]) for story in candidate_payload[:target_count])
    prompt = (
        f"Choose exactly {target_count} distinct story IDs from this JSON list. Select no more than "
        f"{max_stories_per_source} stories from any one source. All candidates are fresh and have "
        "not been sent before, so prioritize the most useful and timely stories about technology, "
        "AI, agentic AI, and Product Management. Avoid empty comment links, vague discussions, "
        "clickbait, and stories with no clear tech, AI, or product angle.\n\n"
        "Return only the story IDs as a comma-separated list, like:\n"
        f"{example}\n\n"
        f"{json.dumps(candidate_payload, ensure_ascii=False)}"
    )
    response_text = agent.generate_text(
        client=client,
        model=model,
        prompt=prompt,
        max_output_tokens=max_output_tokens,
        context="selecting fresh story IDs",
    )
    selected_ids = agent.parse_story_ids_from_text(
        response_text=response_text,
        candidates=candidates[:max_candidates],
        max_stories_per_source=max_stories_per_source,
        target_count=target_count,
    )
    if selected_ids:
        return selected_ids

    preview = agent.clean_text(response_text, max_chars=200)
    raise agent.GeminiFormatError(
        f"Gemini returned an invalid fresh story ID selection. Response preview: {preview!r}"
    )


def validate_fresh_selection(
    selected_ids: list[int],
    candidates: list[agent.StoryCandidate],
    max_stories_per_source: int,
    target_count: int,
) -> list[agent.StoryCandidate]:
    candidates_by_id = {story.id: story for story in candidates}
    selected_candidates: list[agent.StoryCandidate] = []
    source_counts: Counter[str] = Counter()

    for story_id in selected_ids:
        if story_id not in candidates_by_id:
            raise RuntimeError(f"Selected unknown story id {story_id}.")
        candidate = candidates_by_id[story_id]
        source_counts[candidate.source] += 1
        if source_counts[candidate.source] > max_stories_per_source:
            raise RuntimeError(
                f"Selected more than {max_stories_per_source} stories from {candidate.source}."
            )
        selected_candidates.append(candidate)

    if len(selected_candidates) != target_count:
        raise RuntimeError(
            f"Selected {len(selected_candidates)} stories after validation; expected {target_count}."
        )
    return selected_candidates


def pick_fresh_top_stories(candidates: list[agent.StoryCandidate]) -> list[agent.NewsletterStory]:
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    max_candidates = agent.int_env("MAX_CANDIDATES_FOR_AI", 40)
    max_output_tokens = agent.int_env("GEMINI_MAX_OUTPUT_TOKENS", 9600)
    summary_output_tokens = agent.int_env("GEMINI_SUMMARY_OUTPUT_TOKENS", min(max_output_tokens, 768))
    max_stories_per_source = agent.int_env("MAX_STORIES_PER_SOURCE", 2)
    requested_count = agent.int_env("NEWSLETTER_STORY_COUNT", 8)
    min_stories = agent.int_env("MIN_STORIES_TO_SEND", 3)
    target_count = max_selectable_story_count(candidates, max_stories_per_source, requested_count)

    if target_count < min_stories:
        raise RuntimeError(
            f"Only found {target_count} fresh, unsent selectable stories; minimum is {min_stories}. "
            "Try increasing MAX_STORY_AGE_HOURS, MAX_ITEMS_PER_FEED, or lowering MIN_STORIES_TO_SEND."
        )

    client = agent.build_gemini_client()
    selection_output_tokens = min(max_output_tokens, 128)
    skip_gemini_summaries = False

    try:
        selected_ids = select_fresh_story_ids(
            client=client,
            model=model,
            candidates=candidates,
            max_candidates=max_candidates,
            max_stories_per_source=max_stories_per_source,
            max_output_tokens=selection_output_tokens,
            target_count=target_count,
        )
    except agent.GeminiRequestError as exc:
        skip_gemini_summaries = True
        print(
            "Warning: Gemini selection request failed. Falling back to deterministic ranking and "
            f"local summaries. Details: {exc}"
        )
        selected_ids = agent.fallback_select_story_ids(
            candidates=candidates,
            max_candidates=max_candidates,
            max_stories_per_source=max_stories_per_source,
            target_count=target_count,
        )
    except Exception as exc:
        print(
            "Warning: Gemini selection returned unusable output. Falling back to deterministic "
            f"ranking. Details: {exc}"
        )
        selected_ids = agent.fallback_select_story_ids(
            candidates=candidates,
            max_candidates=max_candidates,
            max_stories_per_source=max_stories_per_source,
            target_count=target_count,
        )

    selected_candidates = validate_fresh_selection(
        selected_ids=selected_ids,
        candidates=candidates,
        max_stories_per_source=max_stories_per_source,
        target_count=target_count,
    )

    newsletter_stories: list[agent.NewsletterStory] = []
    use_gemini_summaries = not skip_gemini_summaries
    for candidate in selected_candidates:
        if use_gemini_summaries:
            try:
                summary = agent.summarize_story(
                    client=client,
                    model=model,
                    story=candidate,
                    max_output_tokens=summary_output_tokens,
                )
            except agent.GeminiRequestError as exc:
                use_gemini_summaries = False
                print(
                    "Warning: Gemini summaries became unavailable. Using fallback summaries for "
                    f"the remaining stories. Details: {exc}"
                )
                summary = agent.fallback_summary(candidate)
            except agent.GeminiFormatError as exc:
                print(f"Warning: {exc} Using fallback summary instead.")
                summary = agent.fallback_summary(candidate)
        else:
            summary = agent.fallback_summary(candidate)

        newsletter_stories.append(
            agent.NewsletterStory(
                source=candidate.source,
                title=candidate.title,
                link=candidate.link,
                published=candidate.published,
                summary=summary,
            )
        )

    return newsletter_stories


def run(dry_run: bool = False, preview_file: Path | None = None) -> None:
    agent.load_environment()
    max_per_feed = agent.int_env("MAX_ITEMS_PER_FEED", 10)
    max_age_hours = agent.int_env("MAX_STORY_AGE_HOURS", 24)
    include_undated = bool_env("INCLUDE_UNDATED_STORIES", False)
    history_path = history_file_path()
    history = prune_sent_history(load_sent_history(history_path), agent.int_env("SENT_HISTORY_DAYS", 45))

    candidates = fetch_fresh_stories(
        max_per_feed=max_per_feed,
        max_age_hours=max_age_hours,
        include_undated=include_undated,
    )
    unsent_candidates = reassign_story_ids(filter_unsent_stories(candidates, history))
    if not unsent_candidates:
        raise RuntimeError(
            "No fresh, unsent stories were found. The newsletter was not sent to avoid repeats."
        )

    stories = pick_fresh_top_stories(unsent_candidates)
    html_body = agent.render_newsletter(stories)

    if dry_run:
        preview_path = preview_file or agent.BASE_DIR / "newsletter_preview.html"
        preview_path.write_text(html_body, encoding="utf-8")
        print(f"Dry run complete. Preview written to {preview_path}")
        return

    results = agent.send_newsletter(stories, html_body)
    updated_history = record_sent_stories(history, stories)
    save_sent_history(history_path, prune_sent_history(updated_history, agent.int_env("SENT_HISTORY_DAYS", 45)))
    print(f"Sent newsletter to {len(results)} subscriber(s) with {len(stories)} fresh story/stories.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Curate and send a fresh AI newsletter.")
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

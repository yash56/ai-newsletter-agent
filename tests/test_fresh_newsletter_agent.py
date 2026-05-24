from datetime import date, timedelta

import unittest

from fresh_newsletter_agent import (
    filter_unsent_stories,
    max_selectable_story_count,
    prune_sent_history,
    record_sent_stories,
    story_fingerprint,
)
from newsletter_agent import NewsletterStory, StoryCandidate


def make_candidate(story_id: int, source: str = "TechCrunch") -> StoryCandidate:
    return StoryCandidate(
        id=story_id,
        source=source,
        title=f"AI story {story_id}",
        link=f"https://example.com/story-{story_id}?utm_source=rss",
        published="2026-05-24",
        excerpt="A useful AI product update was announced.",
    )


class FreshNewsletterAgentTests(unittest.TestCase):
    def test_story_fingerprint_ignores_tracking_query_params(self) -> None:
        self.assertEqual(
            story_fingerprint("https://example.com/news?id=1&utm_source=rss"),
            "https://example.com/news",
        )

    def test_filter_unsent_stories_removes_links_already_sent(self) -> None:
        sent_story = make_candidate(1)
        new_story = make_candidate(2)
        history = {"sent_links": {story_fingerprint(sent_story): date.today().isoformat()}}

        self.assertEqual(filter_unsent_stories([sent_story, new_story], history), [new_story])

    def test_record_sent_stories_adds_newsletter_links_to_history(self) -> None:
        story = NewsletterStory(
            source="TechCrunch",
            title="Fresh AI story",
            link="https://example.com/fresh-ai-story?utm_campaign=email",
            published="2026-05-24",
            summary="A company shipped a useful AI product update. Product teams should watch how users respond.",
        )

        history = record_sent_stories({"sent_links": {}}, [story])

        self.assertIn("https://example.com/fresh-ai-story", history["sent_links"])

    def test_prune_sent_history_keeps_recent_links_only(self) -> None:
        old_date = (date.today() - timedelta(days=60)).isoformat()
        recent_date = (date.today() - timedelta(days=2)).isoformat()
        history = {"sent_links": {"old": old_date, "recent": recent_date}}

        pruned = prune_sent_history(history, retention_days=45)

        self.assertEqual(pruned["sent_links"], {"recent": recent_date})

    def test_max_selectable_story_count_respects_source_cap(self) -> None:
        candidates = [
            make_candidate(1, "TechCrunch"),
            make_candidate(2, "TechCrunch"),
            make_candidate(3, "TechCrunch"),
            make_candidate(4, "Hacker News"),
            make_candidate(5, "MIT Technology Review"),
        ]

        self.assertEqual(
            max_selectable_story_count(candidates, max_stories_per_source=2, target_count=8),
            4,
        )


if __name__ == "__main__":
    unittest.main()

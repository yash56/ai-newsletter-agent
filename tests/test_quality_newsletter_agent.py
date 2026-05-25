import os
import unittest
from unittest.mock import patch

from newsletter_agent import StoryCandidate
from quality_newsletter_agent import filter_quality_stories, has_core_relevance, quality_score


def make_candidate(
    story_id: int,
    source: str,
    title: str,
    excerpt: str = "",
) -> StoryCandidate:
    return StoryCandidate(
        id=story_id,
        source=source,
        title=title,
        link=f"https://example.com/story-{story_id}",
        published="2026-05-25",
        excerpt=excerpt,
    )


class QualityNewsletterAgentTests(unittest.TestCase):
    def test_core_relevance_matches_ai_and_product_terms(self) -> None:
        story = make_candidate(
            1,
            "TechCrunch",
            "Google launches new AI tools for product teams",
            "The release helps product managers test workflows faster.",
        )

        self.assertTrue(has_core_relevance(story))

    def test_filter_quality_stories_rejects_generic_non_ai_news(self) -> None:
        generic_story = make_candidate(
            1,
            "Hacker News",
            "Sleep research led to a new sleep apnea drug",
            "Researchers shared medical trial results.",
        )
        ai_story = make_candidate(
            2,
            "MIT Technology Review",
            "A new agentic AI benchmark tests long-running work",
            "The benchmark measures how AI agents plan, recover, and use tools.",
        )

        with patch.dict(os.environ, {"REQUIRE_CORE_RELEVANCE": "true"}, clear=False):
            filtered = filter_quality_stories([generic_story, ai_story])

        self.assertEqual(filtered, [ai_story])

    def test_filter_quality_stories_rejects_generic_business_model_news(self) -> None:
        story = make_candidate(
            1,
            "TechCrunch",
            "A startup changes its business model after layoffs",
            "The company is trying a new pricing plan for enterprise customers.",
        )

        with patch.dict(os.environ, {"REQUIRE_CORE_RELEVANCE": "true"}, clear=False):
            self.assertEqual(filter_quality_stories([story]), [])

    def test_filter_quality_stories_rejects_low_signal_hacker_news_prefixes(self) -> None:
        story = make_candidate(
            1,
            "Hacker News",
            "Ask HN: What task manager should I use?",
            "A discussion thread about productivity tools.",
        )

        self.assertEqual(filter_quality_stories([story]), [])

    def test_quality_score_rewards_specific_ai_context(self) -> None:
        weak_story = make_candidate(
            1,
            "TechCrunch",
            "A startup launches a new community app",
            "The company wants to grow with creators.",
        )
        strong_story = make_candidate(
            2,
            "TechCrunch",
            "A startup launches an AI agent for product research",
            "The tool summarizes user interviews and turns them into roadmap signals.",
        )

        self.assertGreater(quality_score(strong_story), quality_score(weak_story))


if __name__ == "__main__":
    unittest.main()

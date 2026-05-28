import os
import unittest
from unittest.mock import patch

import newsletter_agent as agent
from newsletter_agent import NewsletterStory, StoryCandidate
from quality_newsletter_agent import (
    configure_quality_sources,
    enhance_newsletter_stories,
    filter_quality_stories,
    has_core_relevance,
    quality_score,
    remove_rss_noise,
)


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

    def test_filter_quality_stories_rejects_the_download_roundup(self) -> None:
        story = make_candidate(
            1,
            "MIT Technology Review",
            "The Download: keeping up with AI, and the future of IVF",
            "This is today's edition of The Download, our weekday newsletter.",
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

    def test_configure_quality_sources_adds_official_ai_feeds(self) -> None:
        configure_quality_sources()

        self.assertIn("OpenAI News", agent.configured_feeds())
        self.assertIn("Anthropic News", agent.configured_feeds())
        self.assertIn("GitHub AI & ML", agent.configured_feeds())

    def test_enhance_newsletter_stories_adds_category_and_cleans_title(self) -> None:
        story = NewsletterStory(
            source="Lenny's Newsletter",
            title="Spec-driven development: The AI engineering workflow at Notion | Ryan Nystrom",
            link="https://example.com/story",
            published="2026-05-25",
            summary="Notion uses Claude Code and AI agents to automate engineering workflows. This matters because product teams can move faster when specs and implementation stay connected.",
        )

        enhanced = enhance_newsletter_stories([story])

        self.assertEqual(enhanced[0].title, "Spec-driven development: The AI engineering workflow at Notion")
        self.assertEqual(enhanced[0].category, "Code & Tools")

    def test_enhance_newsletter_stories_preserves_apostrophes_and_rewrites_weak_summary(self) -> None:
        story = NewsletterStory(
            source="TechCrunch",
            title="Why Google’s AI can’t spell Google (or anything else)",
            link="https://example.com/google-ai-spelling",
            published="2026-05-28",
            summary="Google is embarrassing itself, again. The key takeaway is what this could change for teams, customers, products, or the tools people choose next.",
        )

        enhanced = enhance_newsletter_stories([story])

        self.assertEqual(enhanced[0].title, "Why Google's AI can't spell Google (or anything else)")
        self.assertTrue(enhanced[0].summary.startswith("This story explains why Google's AI can't spell"))
        self.assertNotIn("embarrassing itself", enhanced[0].summary)

    def test_remove_rss_noise_drops_mit_newsletter_boilerplate(self) -> None:
        text = (
            "This is today’s edition of The Download, our weekday newsletter that provides a daily dose "
            "of what’s going on in the world of technology. Stay on top of what’s going on in AI this summer."
        )

        self.assertEqual(remove_rss_noise(text), "")


if __name__ == "__main__":
    unittest.main()

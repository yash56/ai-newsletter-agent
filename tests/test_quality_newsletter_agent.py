import os
import unittest
from unittest.mock import patch

import newsletter_agent as agent
from newsletter_agent import NewsletterStory, StoryCandidate
from quality_newsletter_agent import (
    clean_display_title,
    configure_quality_sources,
    enhance_newsletter_stories,
    filter_quality_stories,
    has_core_relevance,
    polish_summary,
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

    def test_filter_quality_stories_rejects_google_ai_quiz_demo(self) -> None:
        story = make_candidate(
            1,
            "Google AI Blog",
            "Take our I/O 2026 quiz, vibe coded in Google AI Studio.",
            "Try a fun quiz made with Gemini and Google AI Studio.",
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
            summary="Notion uses Claude Code and AI agents to automate engineering workflows. The workflow connects written specs to implementation so engineering teams can ship changes with less manual coordination.",
        )

        enhanced = enhance_newsletter_stories([story])

        self.assertEqual(enhanced[0].title, "Spec-driven development: The AI engineering workflow at Notion")
        self.assertEqual(enhanced[0].category, "Code & Tools")

    def test_clean_display_title_simplifies_groq_funding_headline(self) -> None:
        title = "After Nvidia's $20B not-acqui-hire, AI chip startup Groq reportedly raising $650M"

        self.assertEqual(
            clean_display_title(title),
            "Groq reportedly raising $650M as AI chip competition heats up",
        )

    def test_polish_summary_rejects_headline_echo_and_template_copy(self) -> None:
        story = NewsletterStory(
            source="The New Stack",
            title="OpenAI, Anthropic, Google, Amazon, and xAI all fail on type of attack, study finds",
            link="https://example.com/ai-safety-study",
            published="2026-06-01",
            summary=(
                "OpenAI, Anthropic, Google, Amazon, and xAI all fail on type of attack, study finds. "
                "For product teams, the important question is whether this creates a clearer, faster, "
                "or cheaper way to build useful AI features."
            ),
        )

        self.assertEqual(polish_summary(story, story.title), "")

    def test_enhance_newsletter_stories_skips_bad_summary_and_keeps_good_one(self) -> None:
        bad_story = NewsletterStory(
            source="The New Stack",
            title="OpenAI, Anthropic, Google, Amazon, and xAI all fail on type of attack, study finds",
            link="https://example.com/bad-ai-safety-study",
            published="2026-06-01",
            summary=(
                "OpenAI, Anthropic, Google, Amazon, and xAI all fail on type of attack, study finds. "
                "For product teams, the important question is whether this creates a clearer, faster, "
                "or cheaper way to build useful AI features."
            ),
        )
        good_story = NewsletterStory(
            source="The New Stack",
            title="Cisco study finds multi-turn attacks expose gaps in frontier AI safety tests",
            link="https://example.com/good-ai-safety-study",
            published="2026-06-01",
            summary=(
                "Cisco tested 15 frontier AI models and found that all of them were vulnerable to multi-turn attacks, where an attacker gradually pressures the model across several messages. "
                "The study says one-shot safety tests can miss these risks, so companies should test models in longer conversations before using them in production."
            ),
        )

        enhanced = enhance_newsletter_stories([bad_story, good_story])

        self.assertEqual(len(enhanced), 1)
        self.assertEqual(enhanced[0].link, "https://example.com/good-ai-safety-study")
        self.assertIn("Cisco tested 15 frontier AI models", enhanced[0].summary)

    def test_remove_rss_noise_drops_mit_newsletter_boilerplate(self) -> None:
        text = (
            "This is today\u2019s edition of The Download, our weekday newsletter that provides a daily dose "
            "of what\u2019s going on in the world of technology. Stay on top of what\u2019s going on in AI this summer."
        )

        self.assertEqual(remove_rss_noise(text), "")


if __name__ == "__main__":
    unittest.main()

import unittest
from collections import Counter

from newsletter_agent import (
    NewsletterStory,
    StoryCandidate,
    clean_summary_text,
    fallback_select_story_ids,
    fallback_summary,
    parse_story_ids_from_text,
    remove_rss_noise,
    render_text_email,
    split_sentences,
)


def make_story(story_id: int, source: str, title: str, excerpt: str) -> StoryCandidate:
    return StoryCandidate(
        id=story_id,
        source=source,
        title=title,
        link=f"https://example.com/{story_id}",
        published="2026-05-22",
        excerpt=excerpt,
    )


class NewsletterAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = [
            make_story(
                1,
                "TechCrunch",
                "OpenAI launches a new AI agent toolkit",
                "Teams can build multi-step assistants faster.",
            ),
            make_story(
                2,
                "TechCrunch",
                "Figma rolls out AI features for product teams",
                "The update focuses on faster prototyping and collaboration.",
            ),
            make_story(
                3,
                "TechCrunch",
                "Startup raises funding for social shopping",
                "The product is aimed at creators and commerce brands.",
            ),
            make_story(
                4,
                "Hacker News",
                "Anthropic shares new LLM benchmark results",
                "Developers are comparing reliability and cost.",
            ),
            make_story(
                5,
                "Hacker News",
                "Product managers discuss AI workflow adoption",
                "The thread focuses on rollout lessons and team habits.",
            ),
            make_story(
                6,
                "MIT Technology Review",
                "New AI policy proposal targets frontier models",
                "The proposal could change compliance expectations for labs.",
            ),
            make_story(
                7,
                "MIT Technology Review",
                "Researchers improve agent planning in complex tasks",
                "The work shows better long-horizon tool use.",
            ),
            make_story(
                8,
                "Lenny's Newsletter",
                "How product leaders can ship AI features with confidence",
                "The piece covers positioning, evaluation, and customer trust.",
            ),
            make_story(
                9,
                "The Batch by DeepLearning.AI",
                "A new multimodal model cuts inference costs",
                "Builders may get cheaper deployment options.",
            ),
            make_story(
                10,
                "The Batch by DeepLearning.AI",
                "NVIDIA highlights faster chips for AI training",
                "Infrastructure teams are watching performance gains closely.",
            ),
        ]

    def test_parse_story_ids_from_text_enforces_source_limit(self) -> None:
        ids = parse_story_ids_from_text(
            "1, 2, 3, 4, 5, 6, 7, 8, 9, 99",
            self.candidates,
            max_stories_per_source=2,
        )
        self.assertEqual(ids, [1, 2, 4, 5, 6, 7, 8, 9])

    def test_fallback_select_story_ids_returns_eight_stories(self) -> None:
        ids = fallback_select_story_ids(
            candidates=self.candidates,
            max_candidates=10,
            max_stories_per_source=2,
        )
        self.assertEqual(len(ids), 8)

        counts = Counter(story.source for story in self.candidates if story.id in ids)
        self.assertTrue(all(count <= 2 for count in counts.values()))

    def test_clean_summary_text_keeps_first_two_sentences(self) -> None:
        summary = clean_summary_text("First sentence. Second sentence. Third sentence.")
        self.assertEqual(summary, "First sentence. Second sentence.")

    def test_remove_rss_noise_strips_promotional_prefixes(self) -> None:
        cleaned = remove_rss_noise(
            "Watch now | Ryan shows how to automate standups and ship PRs from one comment."
        )
        self.assertNotIn("Watch now", cleaned)
        self.assertEqual(cleaned, "Ryan shows how to automate standups and ship PRs from one comment")

    def test_fallback_summary_returns_simple_two_sentence_copy(self) -> None:
        story = make_story(
            11,
            "Lenny's Newsletter",
            "Spec-driven development at Notion",
            "Watch now | Ryan Nystrom shows how Notion uses specs to guide AI coding work.",
        )
        summary = fallback_summary(story)
        self.assertGreaterEqual(len(split_sentences(summary)), 2)
        self.assertNotIn("reports:", summary)
        self.assertNotIn("Watch now", summary)

    def test_text_email_uses_new_default_title_and_description(self) -> None:
        text_email = render_text_email(
            [
                NewsletterStory(
                    source="TechCrunch",
                    title="AI product update",
                    link="https://example.com/ai-product-update",
                    published="2026-05-22",
                    summary="A company launched a clearer AI product workflow. This helps teams understand what changed and why it matters.",
                )
            ]
        )
        self.assertIn("Daily TAP Brief", text_email)
        self.assertIn("Tech · AI · Product", text_email)


if __name__ == "__main__":
    unittest.main()

# ai-newsletter-agent

A Python newsletter agent that reads trusted RSS feeds and curated AI source pages, asks Gemini to pick and summarize fresh Tech, AI, and Product stories, renders a clean HTML email with Jinja2, and sends it to subscribers through Resend.

## What it does

- Reads RSS feeds with `feedparser` from TechCrunch, Hacker News, MIT Technology Review, Lenny's Newsletter, The Batch by DeepLearning.AI, OpenAI, Anthropic, Google AI, Google Cloud, GitHub AI & ML, Microsoft Developer Blog, Microsoft Tech Community AI, The New Stack, and VentureBeat AI.
- Reads the latest Global AI Weekly issue from `globalai.community/weekly/` and extracts curated links from trusted domains such as Microsoft Tech Community, Anthropic, Google, GitHub, devblogs.microsoft.com, arXiv, and Qwen.
- Uses the Gemini API to pick up to 8 relevant fresh stories and write a two-sentence plain-English summary for each.
- Filters stories to the last 24 hours by default, then skips links that were already sent.
- Applies a quality gate before Gemini selection, so weakly related or vague posts are less likely to appear.
- Rejects unclear summaries that repeat the headline or include generic fallback phrases instead of real article details.
- Favors official AI lab updates, developer-tool news, research, agentic AI, and practical Product Management stories.
- Adds simple category labels such as Research, Code & Tools, Product Updates, Risk & Governance, Events, and Product Thinking.
- Limits the newsletter to at most two stories from any one source.
- Renders an HTML email from `templates/newsletter.html.j2`.
- Sends one email per subscriber using the Resend Python SDK.
- Reads API keys and runtime settings from environment variables.

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create your environment file:

   ```bash
   cp .env.example .env
   ```

   Then fill in:

   - `GEMINI_API_KEY`
   - `RESEND_API_KEY`
   - `RESEND_FROM_EMAIL`

4. Create your subscriber list:

   ```bash
   cp subscribers.csv.example subscribers.csv
   ```

   Use this format:

   ```csv
   email,name
   reader@example.com,Example Reader
   ```

## Run a Preview

Generate the quality-checked newsletter HTML without sending email:

```bash
python quality_newsletter_agent.py --dry-run
```

This writes `newsletter_preview.html`.

## Send the Newsletter

```bash
python quality_newsletter_agent.py
```

The agent sends the rendered newsletter to every valid email in `subscribers.csv`.

## Daily GitHub Actions Send

The workflow in `.github/workflows/send-newsletter.yml` runs every day at 8:00 AM Indian Standard Time. GitHub schedules are written in UTC, so the cron expression is `30 2 * * *`.

Add these repository secrets under GitHub repo settings, then `Secrets and variables`, then `Actions`:

- `GEMINI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`
- `NEWSLETTER_SUBSCRIBERS_CSV`

Set `NEWSLETTER_SUBSCRIBERS_CSV` to the full CSV content, including the header:

```csv
email,name
reader@example.com,Example Reader
```

You can also run the workflow manually from the GitHub Actions tab with `workflow_dispatch`.

## Freshness and Repeat Protection

The daily workflow uses `quality_newsletter_agent.py`, which applies three protections before Gemini picks the stories:

- `MAX_STORY_AGE_HOURS=24` keeps normal RSS sources focused on stories from the last 24 hours.
- `sent_history.json` records article link fingerprints after a successful send, so the next run skips links that were already emailed.
- A quality gate removes weakly relevant posts before Gemini selection.

Global AI Weekly is treated as a curated weekly source rather than a normal daily RSS feed. Its extracted article links still go through relevance, duplicate, and summary-quality checks before they can appear.

In GitHub Actions, `sent_history.json` is restored and saved through `actions/cache@v5`. The file contains article links and dates only. It does not contain API keys, subscriber emails, or message content.

If there are fewer than 8 fresh, relevant, unsent stories, the newsletter sends fewer stories instead of filling the email with old or weak posts. By default it needs at least `MIN_STORIES_TO_SEND=3` selectable stories.

## Usage Controls

The app keeps Gemini usage bounded by default:

- Uses `gemini-3.5-flash` unless `GEMINI_MODEL` is changed.
- Sends at most `MAX_CANDIDATES_FOR_AI=40` candidates to Gemini.
- Caps top-level Gemini output with `GEMINI_MAX_OUTPUT_TOKENS=9600`.
- Uses `GEMINI_SUMMARY_OUTPUT_TOKENS=768` by default for per-story summaries.
- Retries Gemini requests 3 times with a short backoff before falling back.
- Runs once per day from GitHub Actions unless you manually trigger it.

`gemini-3.5-flash` may use more quota than lower-cost Flash Lite models. These app settings reduce usage, but they do not hard-cap spending on the Google side. To restrict credit usage, keep billing disabled for the Gemini API project if you only want the free tier, or set project-level quotas or budgets in Google Cloud for the project attached to your API key.

## Reliability Notes

The delivery path is designed to stay useful even when the model is flaky:

- Gemini story selection falls back to deterministic keyword-based ranking if the model response is malformed or empty.
- Gemini summaries can fall back to excerpt-based summaries when a story-level response is malformed or unavailable.
- The quality runner rejects summaries that repeat the headline or use generic boilerplate, so weak fallback copy is skipped instead of being sent.
- If Gemini becomes unavailable mid-run, the remaining stories use fallback summaries first, then the quality runner filters out anything that is still unclear.

## Content Controls

The newsletter keeps a balanced mix of sources and clearer summaries by default:

- `MAX_STORIES_PER_SOURCE`: defaults to `2`
- `MIN_RELEVANCE_SCORE`: defaults to `10`
- `HACKER_NEWS_MIN_RELEVANCE_SCORE`: defaults to `14`
- `REQUIRE_CORE_RELEVANCE`: defaults to `true`
- `INCLUDE_GLOBAL_AI_WEEKLY`: defaults to `true`
- `GLOBAL_AI_WEEKLY_ALLOWED_DOMAINS`: controls which domains are accepted from Global AI Weekly
- `NEWSLETTER_TITLE`: defaults to `The TAP Brief`
- `NEWSLETTER_SUBJECT`: defaults to `The TAP Brief: Tech, AI, Product`
- `NEWSLETTER_DESCRIPTION`: defaults to `Tech · AI · Product - Explained simply every morning!`
- `NEWSLETTER_FOOTER_TEXT`: defaults to a short subscriber thank-you and reply-for-issues note

The quality gate favors stories with a clear AI, agentic AI, technology, developer-tool, research, or Product Management angle. It rejects low-signal Hacker News patterns like `Ask HN` and raises the relevance threshold for Hacker News because those items often have thinner RSS context.

The upgraded source mix is inspired by stronger AI briefs: more official lab/product updates, more developer tooling, more research, and fewer generic discussion links. The template now adds a short intro and category badges so readers can quickly scan what each item is about.

Each Gemini summary is prompted to use two complete, short, simple sentences: the first explains the latest news clearly, and the second explains why it matters in practical terms. The agent rejects incomplete summaries, headline echoes, generic fallback commentary, common RSS noise like watch/listen/read prompts, and confusing Hacker News placeholders such as `Comments` before rendering the email.

## Environment Variables

Required:

- `GEMINI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`

Optional:

- `GEMINI_MODEL`: defaults to `gemini-3.5-flash`
- `GEMINI_MAX_OUTPUT_TOKENS`: defaults to `9600`
- `GEMINI_SUMMARY_OUTPUT_TOKENS`: defaults to `768`
- `GEMINI_RETRY_ATTEMPTS`: defaults to `3`
- `GEMINI_RETRY_DELAY_SECONDS`: defaults to `2`
- `NEWSLETTER_TITLE`: defaults to `The TAP Brief`
- `NEWSLETTER_SUBJECT`: defaults to `The TAP Brief: Tech, AI, Product`
- `NEWSLETTER_DESCRIPTION`: defaults to `Tech · AI · Product - Explained simply every morning!`
- `NEWSLETTER_FOOTER_TEXT`: defaults to a subscriber thank-you message
- `SUBSCRIBERS_CSV`: defaults to `subscribers.csv`
- `MAX_ITEMS_PER_FEED`: defaults to `10`
- `MAX_CANDIDATES_FOR_AI`: defaults to `40`
- `MAX_STORIES_PER_SOURCE`: defaults to `2`
- `NEWSLETTER_STORY_COUNT`: defaults to `8`
- `MAX_STORY_AGE_HOURS`: defaults to `24`
- `MIN_STORIES_TO_SEND`: defaults to `3`
- `MIN_RELEVANCE_SCORE`: defaults to `10`
- `HACKER_NEWS_MIN_RELEVANCE_SCORE`: defaults to `14`
- `REQUIRE_CORE_RELEVANCE`: defaults to `true`
- `SENT_HISTORY_FILE`: defaults to `sent_history.json`
- `SENT_HISTORY_DAYS`: defaults to `45`
- `INCLUDE_UNDATED_STORIES`: defaults to `false`
- `INCLUDE_GLOBAL_AI_WEEKLY`: defaults to `true`
- `GLOBAL_AI_WEEKLY_URL`: defaults to `https://globalai.community/weekly/`
- `GLOBAL_AI_WEEKLY_ALLOWED_DOMAINS`: defaults to trusted AI source domains used by Global AI Weekly

Feed URLs can be overridden with:

- `TECHCRUNCH_RSS_URL`
- `HACKER_NEWS_RSS_URL`
- `MIT_TECH_REVIEW_RSS_URL`
- `LENNYS_NEWSLETTER_RSS_URL`
- `THE_BATCH_RSS_URL`
- `OPENAI_NEWS_RSS_URL`
- `ANTHROPIC_NEWS_RSS_URL`
- `GOOGLE_AI_BLOG_RSS_URL`
- `GOOGLE_CLOUD_AI_RSS_URL`
- `GITHUB_AI_RSS_URL`
- `MICROSOFT_DEV_BLOG_RSS_URL`
- `MICROSOFT_TECH_COMMUNITY_AI_RSS_URL`
- `THE_NEW_STACK_RSS_URL`
- `VENTUREBEAT_AI_RSS_URL`

## Notes

Resend requires a verified sending domain for production sending. The script sends individual emails instead of one shared recipient list, so subscribers do not see each other's addresses.

`feedparser` may occasionally warn about malformed markup in a feed, especially for The Batch. The script keeps going as long as it can still read usable entries from the feed.

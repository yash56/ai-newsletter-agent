# ai-newsletter-agent

A Python newsletter agent that reads trusted RSS feeds, asks Gemini to pick and summarize fresh Tech, AI, and Product stories, renders a clean HTML email with Jinja2, and sends it to subscribers through Resend.

## What it does

- Reads RSS feeds with `feedparser` from TechCrunch, Hacker News, MIT Technology Review, Lenny's Newsletter, and The Batch by DeepLearning.AI.
- Uses the Gemini API to pick up to 8 relevant fresh stories and write a two-sentence plain-English summary for each.
- Filters stories to the last 24 hours by default, then skips links that were already sent.
- Limits the newsletter to at most two stories from any one source.
- Renders an HTML email from `templates/newsletter.html.j2`.
- Sends one email per subscriber using the Resend Python SDK.
- Reads API keys and runtime settings from environment variables.
- Falls back to deterministic story ranking and excerpt-based summaries if Gemini returns malformed or empty output.

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

## Run a preview

Generate the fresh newsletter HTML without sending email:

```bash
python fresh_newsletter_agent.py --dry-run
```

This writes `newsletter_preview.html`.

## Send the newsletter

```bash
python fresh_newsletter_agent.py
```

The agent sends the rendered newsletter to every valid email in `subscribers.csv`.

## Daily GitHub Actions send

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

## Freshness and repeat protection

The daily workflow uses `fresh_newsletter_agent.py`, which applies two protections before Gemini picks the stories:

- `MAX_STORY_AGE_HOURS=24` keeps the newsletter focused on stories from the last 24 hours.
- `sent_history.json` records article link fingerprints after a successful send, so the next run skips links that were already emailed.

In GitHub Actions, `sent_history.json` is restored and saved through `actions/cache@v5`. The file contains article links and dates only. It does not contain API keys, subscriber emails, or message content.

If there are fewer than 8 fresh, unsent stories, the newsletter sends fewer stories instead of filling the email with old repeats. By default it needs at least `MIN_STORIES_TO_SEND=3` selectable stories.

## Usage controls

The app keeps Gemini usage bounded by default:

- Uses `gemini-3.5-flash` unless `GEMINI_MODEL` is changed.
- Sends at most `MAX_CANDIDATES_FOR_AI=40` RSS candidates to Gemini.
- Caps top-level Gemini output with `GEMINI_MAX_OUTPUT_TOKENS=9600`.
- Uses `GEMINI_SUMMARY_OUTPUT_TOKENS=768` by default for per-story summaries.
- Retries Gemini requests 3 times with a short backoff before falling back.
- Runs once per day from GitHub Actions unless you manually trigger it.

`gemini-3.5-flash` may use more quota than lower-cost Flash Lite models. These app settings reduce usage, but they do not hard-cap spending on the Google side. To restrict credit usage, keep billing disabled for the Gemini API project if you only want the free tier, or set project-level quotas or budgets in Google Cloud for the project attached to your API key.

## Reliability notes

The delivery path is designed to stay useful even when the model is flaky:

- Gemini story selection falls back to deterministic keyword-based ranking if the model response is malformed or empty.
- Gemini summaries fall back to excerpt-based two-sentence summaries when a story-level response is malformed or unavailable.
- If Gemini becomes unavailable mid-run, the remaining stories use fallback summaries instead of failing the whole newsletter.

## Content controls

The newsletter keeps a balanced mix of sources and clearer summaries by default:

- `MAX_STORIES_PER_SOURCE`: defaults to `2`
- `NEWSLETTER_TITLE`: defaults to `The TAP Brief`
- `NEWSLETTER_SUBJECT`: defaults to `The TAP Brief: Tech, AI, Product`
- `NEWSLETTER_DESCRIPTION`: defaults to `Tech · AI · Product - Explained simply every morning!`
- `NEWSLETTER_FOOTER_TEXT`: defaults to a short subscriber thank-you and reply-for-issues note

Each Gemini summary is prompted to use two complete, short, simple sentences: the first explains the latest news clearly, and the second explains why it matters in practical terms. The agent rejects incomplete summaries, removes common RSS noise like watch/listen/read prompts, and strips confusing Hacker News placeholders such as `Comments` before rendering the email.

## Environment variables

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
- `SENT_HISTORY_FILE`: defaults to `sent_history.json`
- `SENT_HISTORY_DAYS`: defaults to `45`
- `INCLUDE_UNDATED_STORIES`: defaults to `false`

Feed URLs can be overridden with:

- `TECHCRUNCH_RSS_URL`
- `HACKER_NEWS_RSS_URL`
- `MIT_TECH_REVIEW_RSS_URL`
- `LENNYS_NEWSLETTER_RSS_URL`
- `THE_BATCH_RSS_URL`

## Notes

Resend requires a verified sending domain for production sending. The script sends individual emails instead of one shared recipient list, so subscribers do not see each other's addresses.

`feedparser` may occasionally warn about malformed markup in a feed, especially for The Batch. The script keeps going as long as it can still read usable entries from the feed.

# ai-newsletter-agent

A Python newsletter agent that reads trusted RSS feeds, asks Gemini to pick and summarize the top AI, agentic AI, and Product Management stories, renders a clean HTML email with Jinja2, and sends it to subscribers through Resend.

## What it does

- Reads RSS feeds with `feedparser` from TechCrunch, Hacker News, MIT Technology Review, Lenny's Newsletter, and The Batch by DeepLearning.AI.
- Uses the Gemini API to pick exactly 8 relevant stories and write a two-sentence plain-English summary for each.
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

## Run a preview

Generate the newsletter HTML without sending email:

```bash
python newsletter_agent.py --dry-run
```

This writes `newsletter_preview.html`.

## Send the newsletter

```bash
python newsletter_agent.py
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

## Usage controls

The app keeps Gemini usage bounded by default:

- Uses `gemini-3.5-flash` unless `GEMINI_MODEL` is changed.
- Sends at most `MAX_CANDIDATES_FOR_AI=40` RSS candidates to Gemini.
- Caps Gemini output with `GEMINI_MAX_OUTPUT_TOKENS=9600`.
- Splits Gemini work into one small story-selection call and one small summary call per selected story to avoid truncated JSON.
- Runs once per day from GitHub Actions unless you manually trigger it.

`gemini-3.5-flash` may use more quota than lower-cost Flash Lite models. These app settings reduce usage, but they do not hard-cap spending on the Google side. To restrict credit usage, keep billing disabled for the Gemini API project if you only want the free tier, or set project-level quotas/budgets in Google Cloud for the project attached to your API key.

## Content controls

The newsletter keeps a balanced mix of sources and clearer summaries by default:

- `MAX_STORIES_PER_SOURCE`: defaults to `2`
- `NEWSLETTER_FOOTER_TEXT`: defaults to a short subscriber thank-you and reply-for-issues note

Each summary is prompted to explain what happened in the first sentence and why it matters in the second sentence.

## Environment variables

Required:

- `GEMINI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`

Optional:

- `GEMINI_MODEL`: defaults to `gemini-3.5-flash`
- `GEMINI_MAX_OUTPUT_TOKENS`: defaults to `9600`
- `GEMINI_SUMMARY_OUTPUT_TOKENS`: defaults to `GEMINI_MAX_OUTPUT_TOKENS`
- `NEWSLETTER_TITLE`: defaults to `AI, Agents, and Product Brief`
- `NEWSLETTER_SUBJECT`: defaults to `Today's AI, Agents, and Product Brief`
- `NEWSLETTER_FOOTER_TEXT`: defaults to a subscriber thank-you message
- `SUBSCRIBERS_CSV`: defaults to `subscribers.csv`
- `MAX_ITEMS_PER_FEED`: defaults to `10`
- `MAX_CANDIDATES_FOR_AI`: defaults to `40`
- `MAX_STORIES_PER_SOURCE`: defaults to `2`

Feed URLs can be overridden with:

- `TECHCRUNCH_RSS_URL`
- `HACKER_NEWS_RSS_URL`
- `MIT_TECH_REVIEW_RSS_URL`
- `LENNYS_NEWSLETTER_RSS_URL`
- `THE_BATCH_RSS_URL`

## Notes

Resend requires a verified sending domain for production sending. The script sends individual emails instead of one shared recipient list, so subscribers do not see each other's addresses.

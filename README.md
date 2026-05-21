# ai-newsletter-agent

A Python newsletter agent that reads trusted RSS feeds, asks OpenAI to pick and summarize the top AI, agentic AI, and Product Management stories, renders a clean HTML email with Jinja2, and sends it to subscribers through Resend.

## What it does

- Reads RSS feeds with `feedparser` from TechCrunch, Hacker News, MIT Technology Review, Lenny's Newsletter, and The Batch by DeepLearning.AI.
- Uses the OpenAI API to pick exactly 8 relevant stories and write a two-sentence plain-English summary for each.
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

   - `OPENAI_API_KEY`
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

## Environment variables

Required:

- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`

Optional:

- `OPENAI_MODEL`: defaults to `gpt-4o-mini`
- `NEWSLETTER_TITLE`: defaults to `AI, Agents, and Product Brief`
- `NEWSLETTER_SUBJECT`: defaults to `Today's AI, Agents, and Product Brief`
- `SUBSCRIBERS_CSV`: defaults to `subscribers.csv`
- `MAX_ITEMS_PER_FEED`: defaults to `15`

Feed URLs can be overridden with:

- `TECHCRUNCH_RSS_URL`
- `HACKER_NEWS_RSS_URL`
- `MIT_TECH_REVIEW_RSS_URL`
- `LENNYS_NEWSLETTER_RSS_URL`
- `THE_BATCH_RSS_URL`

## Notes

Resend requires a verified sending domain for production sending. The script sends individual emails instead of one shared recipient list, so subscribers do not see each other's addresses.

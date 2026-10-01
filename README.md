# 🌸 The Marketing Edit

A daily marketing briefing for India, with global context. Every morning at about 6:00 AM IST it:
1. Collects the last day's news from about 30 marketing, advertising, startup and business sources.
2. Uses AI to pick the most important stories in 10 sections.
3. Reads each full article and its picture, then writes a short article plus a "why it matters" note.
4. Publishes a pink dashboard with images, a big-picture summary, a tip of the day, and an archive of past days.
5. Optionally sends the same briefing by email and/or Telegram.

Everything runs free on GitHub, using a free Gemini key.

## Files
| File | What it does |
|---|---|
| `config.py` | **Your settings.** Title, sections, news sources and article counts. This is the only file you'll normally edit. |
| `main.py` | The engine. No need to touch it. |
| `template.html` | The dashboard design (pink theme). |
| `requirements.txt` | Python libraries the tool needs. |
| `.github/workflows/daily.yml` | The daily schedule. |

## Setup

1. **Gemini key:** at aistudio.google.com, go to API keys, then Create API key, then **Create project** "Marketing Briefing", then create the key and copy it.
2. **Repo:** on GitHub, create a new **Public** repository named `marketing-briefing`, with "Add a README" ticked.
3. **Upload:** click Add file, then Upload files, and add `main.py`, `config.py`, `template.html`, `requirements.txt` and `README.md`. Commit.
4. **Workflow:** click Add file, then Create new file, and name it `.github/workflows/daily.yml`. Paste in the contents of that file and commit.
5. **Secret:** go to Settings, Secrets and variables, Actions, New repository secret. Use the name `GEMINI_API_KEY` and paste the key.
6. **First run:** go to Actions, Marketing briefing, Run workflow. It takes about 20 minutes.
7. **Dashboard:** go to Settings, then Pages. Choose Deploy from a branch, then `main` and `/docs`, and save.
   Your link: `https://<your-username>.github.io/marketing-briefing/`

## Optional
- **Email:** add the secrets `GMAIL_USER`, `GMAIL_APP_PASSWORD` (from myaccount.google.com/apppasswords, with spaces removed) and `EMAIL_TO`.
- **Telegram:** add the secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **Backup AI (free):** add `GROQ_API_KEY` (from console.groq.com).
- **Dashboard button in email:** under Settings, Secrets and variables, Actions, open the Variables tab and add `DASHBOARD_URL` with your link.

## Customising (`config.py`)
- **Rename:** change `TITLE` and `TAGLINE`.
- **New section:** add a line to `CATEGORIES` as `"key": ("Name", "what belongs here", "#colour", "emoji"),`
- **New source:** add `("Name", gnews("your keywords")),` or `("Name", "https://site.com/feed"),` to `FEEDS`.
- **More or fewer articles:** change `ARTICLES_PER_CATEGORY`.
- **Time:** edit `cron` in `daily.yml`. Times are in UTC, which is IST minus 5:30.

## Troubleshooting
| Log shows | Fix |
|---|---|
| `No API key found` | The `GEMINI_API_KEY` secret is missing or misspelled |
| `404 ... model` | The Gemini model name changed. Update `gemini-3.8-flash` in `main.py` |
| `429 quota` | The free quota is used up for the day; it resets around 12:30 PM IST. Avoid many manual runs |
| `503 busy` | Google is overloaded. The tool retries on its own; otherwise run it again later |
| Dashboard 404 | Pages must be set to `main` and `/docs`, and the first run must have succeeded |
| No image on a story | That site didn't share a picture, so a pink emoji card is shown instead |

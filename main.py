"""The Marketing Edit - daily marketing briefing.
RSS feeds -> AI picks stories -> reads full articles (+ images) -> writes short articles
-> pink dashboard in docs/ -> optional email / Telegram.
"""
import datetime as dt
import html
import json
import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import feedparser
import requests
import trafilatura

from config import (ARTICLES_PER_CATEGORY, CATEGORIES, FEEDS, HOURS_BACK, MAX_ARTICLES,
                    PER_FEED, TAGLINE, TITLE)

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "")
ROOT = Path(__file__).parent
esc = html.escape


# ================= 1. Collect headlines =================
def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def entry_image(entry):
    """Find a picture in the feed item, if the feed provides one."""
    for key in ("media_content", "media_thumbnail"):
        for m in entry.get(key, []) or []:
            if m.get("url"):
                return m["url"]
    for link in entry.get("links", []) or []:
        if link.get("type", "").startswith("image") and link.get("href"):
            return link["href"]
    found = re.search(r'<img[^>]+src="([^"]+)"', entry.get("summary", "") or "")
    return found.group(1) if found else ""


def fetch_articles():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=HOURS_BACK)
    seen, articles = set(), []
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url, agent="Mozilla/5.0 (marketing-edit)")
        except Exception as e:
            print(f"skip {source}: {e}")
            continue
        count = 0
        for entry in feed.entries:
            if count >= PER_FEED:
                break
            t = entry.get("published_parsed") or entry.get("updated_parsed")
            if t and dt.datetime(*t[:6], tzinfo=dt.timezone.utc) < cutoff:
                continue
            title = clean(entry.get("title", ""))
            key = re.sub(r"\W+", "", title.lower())[:60]
            if not title or not entry.get("link") or key in seen:
                continue
            seen.add(key)
            count += 1
            publisher = (entry.get("source") or {}).get("title") or source
            if publisher != source and title.endswith(" - " + publisher):
                title = title[: -len(" - " + publisher)]
            articles.append({"id": len(articles), "title": title, "link": entry.get("link"),
                             "source": publisher, "snippet": clean(entry.get("summary", ""))[:300],
                             "image": entry_image(entry)})
        print(f"{source}: {count} stories")
    return articles[:MAX_ARTICLES]


BAD_IMAGE_HINTS = ("news.google", "gstatic.com", "googleusercontent.com", "google.com/", "logo", "favicon",
                   "placeholder", "default-image", "default_image", "sprite", "icon", "avatar", "1x1", "blank.")


def good_image(url):
    """Skip logos, Google News artwork and tiny icons - keep real article photos only."""
    u = (url or "").lower()
    return u.startswith("http") and not any(h in u for h in BAD_IMAGE_HINTS)


def real_link(url):
    """Google News links hide the real article - unwrap them so we can read the story and its photo."""
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        result = gnewsdecoder(url, interval=1)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as e:
        print(f"could not unwrap Google News link: {e}")
    return url


def brand_logo(domain):
    """Brand logo from the brand's website (via Google's public icon service). '' if none found."""
    domain = re.sub(r"^https?://|^www\.|/.*$", "", (domain or "").strip().lower())
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
        return ""
    url = f"https://www.google.com/s2/favicons?domain={domain}&sz=256"
    try:
        r = requests.get(url, timeout=15)
        # tiny responses are Google's generic globe icon -> treat as "no logo"
        if r.status_code == 200 and len(r.content) > 2500:
            return url
    except Exception:
        pass
    return ""


def read_page(url):
    """Download the article: main text + its preview image (og:image)."""
    try:
        page = trafilatura.fetch_url(url)
        if not page:
            return "", ""
        text = (trafilatura.extract(page) or "")[:2500]
        img = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', page) \
            or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', page)
        image = html.unescape(img.group(1)) if img else ""
        return text, image if good_image(image) else ""
    except Exception:
        return "", ""


# ================= 2. AI providers =================
def call_gemini(prompt):
    """Free: Google Gemini (key from aistudio.google.com)."""
    models = [os.getenv("GEMINI_MODEL", "gemini-3.8-flash"), "gemini-flash-lite-latest", "gemini-flash-latest"]
    last = ""
    for model in models:
        for attempt in range(3):
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": os.environ["GEMINI_API_KEY"]},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
                timeout=300)
            if r.status_code == 200:
                return "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
            last = f"{model} error {r.status_code}: {r.text[:300]}"
            print(last)
            if r.status_code in (500, 502, 503, 504):
                print(f"Gemini busy - waiting {20 * (attempt + 1)}s...")
                time.sleep(20 * (attempt + 1))
                continue
            break  # quota used up / model not found -> next model
    raise RuntimeError(last)


def call_groq(prompt):
    """Free backup: Groq (key from console.groq.com)."""
    models = [os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), "openai/gpt-oss-120b"]
    last = ""
    for model in models:
        for attempt in range(3):
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                              headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                              json={"model": model, "temperature": 0.3,
                                    "response_format": {"type": "json_object"},
                                    "messages": [{"role": "user", "content": prompt}]},
                              timeout=300)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            last = f"groq {model} error {r.status_code}: {r.text[:300]}"
            print(last)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(30 * (attempt + 1))
                continue
            break
    raise RuntimeError(last)


def call_claude(prompt):
    """Paid option: Anthropic Claude (key from console.anthropic.com)."""
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                               "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 8000,
                            "messages": [{"role": "user", "content": prompt}]},
                      timeout=300)
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def parse_json(text):
    """Read the AI's JSON answer, repairing common small mistakes (trailing commas, code fences, stray text)."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    text = text[text.find("{"): text.rfind("}") + 1]
    for attempt in (text, re.sub(r",\s*([}\]])", r"\1", text)):
        try:
            return json.loads(attempt, strict=False)
        except json.JSONDecodeError:
            continue
    raise ValueError("AI reply was not valid JSON")


def ask_ai(prompt):
    """Uses whichever keys you added, in order: Gemini, Groq, Claude. Re-asks if a reply is broken."""
    errors = []
    for env, fn in (("GEMINI_API_KEY", call_gemini), ("GROQ_API_KEY", call_groq), ("ANTHROPIC_API_KEY", call_claude)):
        if not os.getenv(env):
            continue
        for attempt in range(3):
            try:
                return parse_json(fn(prompt))
            except ValueError as e:
                print(f"{fn.__name__}: broken reply (attempt {attempt + 1}/3), asking again...")
                errors.append(str(e))
                time.sleep(10)
            except Exception as e:
                print(f"{fn.__name__} failed, trying next: {e}")
                errors.append(str(e))
                break
    raise SystemExit("All AI providers failed:\n" + "\n".join(errors or ["No API key found - add GEMINI_API_KEY"]))


# ================= 3. Build the briefing =================
# Backup keywords: if the AI leaves one of these sections empty, matching headlines are used instead.
SECTION_KEYWORDS = {   # (words that must appear, and if given, at least one context word too)
    "ai_martech": (["AI", "generative", "automation", "chatbot", "martech", "adtech", "Advantage\\+", "Performance Max"],
                   ["marketing", "marketer", "advertis", "ads?", "brand", "campaign", "creative", "martech", "adtech",
                    "Meta", "Google"]),
    "ai_world": (["AI", "OpenAI", "ChatGPT", "Gemini", "Anthropic", "Claude", "LLM", "artificial intelligence",
                  "IndiaAI", "Sarvam", "Krutrim", "data centre", "data center"], None),
}

READER = ("a performance and brand marketer in India who wants situational awareness on marketing, "
          "advertising, brands, consumers, startups and the business forces shaping them")


def build_brief(articles):
    cats = "\n".join(f'- "{k}": {v[0]} - {v[1]}' for k, v in CATEGORIES.items())
    items = "\n".join(f'[{a["id"]}] {a["title"]} ({a["source"]})' for a in articles)

    picked = ask_ai(f"""You are the editor of a daily briefing for {READER}.
Prefer Indian stories, but keep the most important global ones.

Sections:
{cats}

Today's headlines (id in brackets):
{items}

Pick the most important, genuinely newsworthy stories. Skip fluff, ads, listicles and repeats of the same event.
Put each in exactly ONE section, at most {ARTICLES_PER_CATEGORY} per section, most important first.
Fill EVERY section: give each section at least 2 stories whenever any reasonably relevant headline exists
(for example, any story about AI tools, AI ads or AI creative counts for "AI in marketing & martech").
Reply with ONLY valid JSON: {{"stories": [{{"id": 0, "category": "campaigns_brands"}}]}}""")

    by_id = {a["id"]: a for a in articles}
    counts = {k: 0 for k in CATEGORIES}
    chosen = []
    for s in picked.get("stories", []):
        a, cat = by_id.get(s.get("id")), s.get("category")
        if a and cat in counts and counts[cat] < ARTICLES_PER_CATEGORY:
            counts[cat] += 1
            chosen.append({**a, "category": cat})

    # make sure no section is left empty: fill it with matching headlines if the AI skipped it
    used = {a["id"] for a in chosen}
    for key, words in SECTION_KEYWORDS.items():
        if key in counts and counts[key] == 0:
            for a in articles:
                if counts[key] >= 2:
                    break
                must, context = words
                hit = any(re.search(rf"\b{w}", a["title"], re.I) for w in must)
                ctx = context is None or any(re.search(rf"\b{w}", a["title"], re.I) for w in context)
                if a["id"] not in used and hit and ctx:
                    used.add(a["id"])
                    counts[key] += 1
                    chosen.append({**a, "category": key})
            print(f"section '{key}' was empty - filled {counts[key]} by keywords")

    for a in chosen:
        a["link"] = real_link(a["link"])
        if "news.google.com" in a["link"]:
            a["full_text"], page_image = "", ""
        else:
            a["full_text"], page_image = read_page(a["link"])
        a["image"] = page_image or (a["image"] if good_image(a["image"]) else "")
        print(f"read {len(a['full_text'])} chars, image={'yes' if a['image'] else 'no'}: {a['title'][:55]}")

    written = {}
    for key, (name, *_rest) in CATEGORIES.items():
        batch = [a for a in chosen if a["category"] == key]
        if not batch:
            continue
        sources = "\n\n".join(f'[{a["id"]}] {a["title"]} ({a["source"]})\n{a["full_text"] or a["snippet"]}'
                              for a in batch)
        try:
            result = ask_ai(f"""You write a daily marketing news briefing for {READER}.
For each story below (section: {name}), write a short news article in your own words that she can read
instead of the original.

Rules:
- "headline": clear and factual.
- "article": 3 to 4 paragraphs, about 180-250 words: what happened, key details and numbers, context,
  what comes next. Separate paragraphs with a blank line (\\n\\n).
- "why": 2 sentences on what this means for marketers and brands - the takeaway or lesson.
- "brand": the main company or brand the story is about (e.g. "Nike"), or "" if there isn't one.
- "domain": that brand's main website domain (e.g. "nike.com", "zomato.com"), or "" if unsure.
- Use only facts from the source text. If a source is only a short snippet, write 1-2 paragraphs and do not
  invent details, quotes or numbers.

Stories:
{sources}

Reply with ONLY valid JSON:
{{"stories": [{{"id": 0, "headline": "...", "article": "para 1\\n\\npara 2", "why": "..."}}]}}""")
            for st in result.get("stories", []):
                written[st.get("id")] = st
            print(f"wrote: {name}")
        except SystemExit as e:
            print(f"skipped {name}: {e}")
        time.sleep(15)  # stay under free-tier per-minute limits

    grouped = {k: [] for k in CATEGORIES}
    for a in chosen:
        w = written.get(a["id"])
        if w and w.get("article"):
            logo = "" if a["image"] else brand_logo(w.get("domain"))
            grouped[a["category"]].append({**a, "headline": w.get("headline") or a["title"],
                                           "article": w["article"], "why": w.get("why", ""),
                                           "brand": w.get("brand", ""), "logo": logo})
    headlines = "\n".join(f'- {s["headline"]}' for v in grouped.values() for s in v)
    if not headlines:
        raise SystemExit("No articles could be written today - see errors above")

    summary = ask_ai(f"""Today's marketing and business headlines for {READER}:
{headlines}

Write:
- "big_picture": 3 sentences connecting today's news into trends marketers should notice.
- "tip": one concrete thing a marketer could try, test or learn this week, based on today's news.
Reply with ONLY valid JSON: {{"big_picture": ["...", "...", "..."], "tip": "..."}}""")
    return {"big_picture": summary.get("big_picture", []), "tip": summary.get("tip", ""), "grouped": grouped}


def paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n|\n", text or "") if p.strip()]


# ================= 4. Dashboard =================
def media(s, emoji, color, section=""):
    """Photo if we have one; otherwise the brand's logo on a pink tile; otherwise an elegant text card."""
    brand = esc(s.get("brand") or "")
    layers = f'<div class="type"><small>{esc(s.get("source", ""))}</small><b>{brand or esc(section)}</b></div>'
    if s.get("logo"):
        layers += (f'<div class="logo"><div class="tile"><img src="{esc(s["logo"])}" alt="{brand}" loading="lazy" '
                   f'referrerpolicy="no-referrer" onerror="this.closest(\'.logo\').remove()"></div>'
                   f'{f"<em>{brand}</em>" if brand else ""}</div>')
    if s.get("image"):
        layers += (f'<img class="photo" src="{esc(s["image"])}" alt="" loading="lazy" referrerpolicy="no-referrer" '
                   f'onerror="this.remove()">')
    return f'<div class="media" style="--c:{color}">{layers}</div>'


def story_html(s, emoji, color, featured=False, section=""):
    body = "".join(f"<p>{esc(p)}</p>" for p in paragraphs(s["article"]))
    return f'''<article class="story{' featured' if featured else ''}">
  {media(s, emoji, color, section)}
  <div class="body">
    <h3>{esc(s["headline"])}</h3>
    {body}
    <div class="why"><b>Why it matters</b>{esc(s["why"])}</div>
    <a class="src" href="{esc(s["link"])}" target="_blank" rel="noopener">{esc(s["source"])} ↗</a>
  </div>
</article>'''


def archive_links(today):
    files = sorted((ROOT / "docs" / "archive").glob("*.html"), reverse=True)
    links = []
    for f in files[:21]:
        try:
            d = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        label = "Today" if d == today.date() else d.strftime("%a, %d %b")
        links.append(f'<a href="archive/{f.name}">{label}</a>')
    return "".join(links) or "<span>Your past briefings will appear here.</span>"


def build_dashboard(brief, today, archive_html):
    total = sum(len(v) for v in brief["grouped"].values())
    chips = [f'<button class="chip on" data-cat="all">All <span>{total}</span></button>']
    sections = []
    for key, (name, _, color, emoji) in CATEGORIES.items():
        stories = brief["grouped"][key]
        if not stories:
            continue
        chips.append(f'<button class="chip" data-cat="{key}" style="--c:{color}">{emoji} {esc(name)} '
                     f'<span>{len(stories)}</span></button>')
        first = story_html(stories[0], emoji, color, featured=True, section=name)
        rest = "".join(story_html(s, emoji, color, section=name) for s in stories[1:])
        sections.append(f'''<section class="cat" data-cat="{key}" style="--c:{color}">
  <h2><i>{emoji}</i>{esc(name)}</h2>
  {first}
  {f'<div class="grid">{rest}</div>' if rest else ''}
</section>''')

    bullets = "".join(f"<li>{esc(b)}</li>" for b in brief["big_picture"])
    page = (ROOT / "template.html").read_text(encoding="utf-8")
    for k, v in {"{{TITLE}}": esc(TITLE), "{{TAGLINE}}": esc(TAGLINE),
                 "{{DATE}}": today.strftime("%A, %d %B %Y"), "{{BIG_PICTURE}}": bullets,
                 "{{TIP}}": esc(brief["tip"]), "{{CHIPS}}": "".join(chips),
                 "{{SECTIONS}}": "".join(sections), "{{ARCHIVE}}": archive_html,
                 "{{COUNT}}": str(total),
                 "{{UPDATED}}": today.strftime("%d %b %Y, %I:%M %p IST")}.items():
        page = page.replace(k, v)
    return page


# ================= 5. Email & Telegram (optional) =================
def build_email(brief, today):
    p = [f'<div style="background:#FFF5F8;padding:24px 12px;font-family:Arial,sans-serif;color:#3A1430">'
         f'<div style="max-width:640px;margin:auto;background:#fff;border-radius:18px;padding:28px;border:1px solid #F9D5E3">'
         f'<p style="text-align:center;color:#C2185B;letter-spacing:2px;font-size:12px;margin:0">{esc(TAGLINE.upper())}</p>'
         f'<h1 style="text-align:center;font-family:Georgia,serif;font-style:italic;font-size:32px;margin:6px 0">{esc(TITLE)}</h1>'
         f'<p style="text-align:center;color:#8A5A78;margin:0 0 20px">{today.strftime("%A, %d %B %Y")}</p>'
         f'<div style="background:#FFE4EE;border-radius:14px;padding:16px 18px"><b>Today\'s big picture</b><ul style="padding-left:18px">'
         + "".join(f"<li style='margin:6px 0'>{esc(b)}</li>" for b in brief["big_picture"]) + "</ul></div>"
         f'<p style="border:2px dashed #F48FB1;border-radius:14px;padding:12px 16px;margin:16px 0">'
         f'<b>💡 Tip of the day:</b> {esc(brief["tip"])}</p>']
    if DASHBOARD_URL:
        p.append(f'<p style="text-align:center"><a href="{DASHBOARD_URL}" style="background:#E8457C;color:#fff;'
                 f'padding:10px 22px;border-radius:999px;text-decoration:none;display:inline-block">Open the dashboard</a></p>')
    for key, (name, _, color, emoji) in CATEGORIES.items():
        stories = brief["grouped"][key]
        if not stories:
            continue
        p.append(f'<h2 style="font-family:Georgia,serif;color:{color};font-size:21px;margin:30px 0 4px">{emoji} {esc(name)}</h2>')
        for s in stories:
            if s.get("image"):
                p.append(f'<img src="{esc(s["image"])}" alt="" style="width:100%;max-height:260px;object-fit:cover;'
                         f'border-radius:12px;margin-top:14px">')
            elif s.get("logo"):
                p.append(f'<div style="background:#FFE4EE;border-radius:12px;padding:18px;text-align:center;margin-top:14px">'
                         f'<img src="{esc(s["logo"])}" alt="" width="64" height="64" style="border-radius:14px;background:#fff;padding:8px"></div>')
            p.append(f'<h3 style="font-family:Georgia,serif;font-size:19px;margin:12px 0 6px">{esc(s["headline"])}</h3>'
                     + "".join(f'<p style="margin:0 0 10px;line-height:1.6">{esc(x)}</p>' for x in paragraphs(s["article"]))
                     + f'<p style="background:#FFF0F5;border-radius:10px;padding:10px 12px;margin:6px 0">'
                     f'<b>Why it matters:</b> {esc(s["why"])}</p>'
                     f'<p style="font-size:12px;margin:4px 0 0"><a href="{esc(s["link"])}" style="color:#C2185B">'
                     f'Source: {esc(s["source"])}</a></p>')
    p.append("</div></div>")
    return "".join(p)


def send_email(brief, today):
    user, pwd, to = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"), os.getenv("EMAIL_TO")
    if not (user and pwd and to):
        print("Email not set up - skipping")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{TITLE} - {today.strftime('%d %b %Y')}"
    msg["From"], msg["To"] = user, to
    msg.attach(MIMEText(build_email(brief, today), "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pwd)
        s.sendmail(user, [x.strip() for x in to.split(",")], msg.as_string())
    print("Email sent")


def send_telegram(brief, today):
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("Telegram not set up - skipping")
        return
    blocks = [f"<b>{esc(TITLE)} - {today.strftime('%d %b %Y')}</b>\n\n"
              + "\n".join(f"• {esc(b)}" for b in brief["big_picture"])
              + f"\n\n💡 <b>Tip:</b> {esc(brief['tip'])}"]
    for key, (name, _, _, emoji) in CATEGORIES.items():
        stories = brief["grouped"][key]
        if stories:
            blocks.append(f"{emoji} <b>{esc(name)}</b>\n" + "\n".join(
                f'• <a href="{esc(s["link"])}">{esc(s["headline"])}</a>' for s in stories))
    if DASHBOARD_URL:
        blocks.append(f'<a href="{DASHBOARD_URL}">Read the full articles on your dashboard</a>')
    messages, cur = [], ""
    for b in blocks:
        if len(cur) + len(b) > 3800:
            messages.append(cur)
            cur = ""
        cur += b + "\n\n"
    messages.append(cur)
    for m in messages:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": m, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=30).raise_for_status()
    print("Telegram sent")


# ================= Run =================
def main():
    today = dt.datetime.now(IST)
    articles = fetch_articles()
    print(f"Collected {len(articles)} headlines")
    if not articles:
        raise SystemExit("No headlines found - check FEEDS in config.py")
    brief = build_brief(articles)

    archive = ROOT / "docs" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    day_file = archive / f"{today:%Y-%m-%d}.html"
    day_file.write_text("", encoding="utf-8")       # so today appears in the archive list
    links = archive_links(today)
    page = build_dashboard(brief, today, links)
    (ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")
    # archive copies sit one folder deeper, so fix their links
    day_file.write_text(page.replace('href="archive/', 'href="'), encoding="utf-8")
    print("Dashboard written to docs/index.html")


    for step in (send_email, send_telegram):
        try:
            step(brief, today)
        except Exception as e:
            print(f"Delivery error ({step.__name__}): {e}")


if __name__ == "__main__":
    main()

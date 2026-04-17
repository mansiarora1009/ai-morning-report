#!/usr/bin/env python3
"""
Morning Report — daily AI content brief
Sources: X/Twitter (Grok API), Hacker News, official company RSS feeds
Output: _morning-reports/YYYY-MM-DD.md

Usage:
    export GROK_API_KEY=your_key_here
    python3 morning_report.py
"""

import os
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

GROK_API_KEY = os.environ.get("GROK_API_KEY", "")

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = Path(os.environ.get("MORNING_REPORT_OUTPUT_DIR", str(BASE_DIR / "_morning-reports")))

X_ACCOUNTS = ["simonw", "karpathy", "swyx", "rileysgoodside", "emollick"]

RSS_FEEDS = {
    "Anthropic":        "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "Anthropic Eng":    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
    "Claude Code":      "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_changelog_claude_code.xml",
    "OpenAI":           "https://openai.com/blog/rss.xml",
    "Google DeepMind":  "https://deepmind.google/blog/rss.xml",
    "xAI":              "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_xainews.xml",
    "Cursor":           "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_cursor.xml",
    "GitHub":           "https://github.blog/feed/",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def grok_request(payload):
    req = urllib.request.Request(
        "https://api.x.ai/v1/responses",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROK_API_KEY}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  Grok API error {e.code}: {e.read().decode()}")
        return None

def extract_text(grok_result):
    if not grok_result:
        return "No data retrieved."
    for item in grok_result.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    return c["text"]
    return "No data retrieved."

# ── Fetchers ──────────────────────────────────────────────────────────────────

def fetch_x_engagement():
    """High-engagement posts about AI tools/workflows from last 24 hours"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    result = grok_request({
        "model": "grok-4-fast",
        "input": [{"role": "user", "content":
            "Find the 5 highest-engagement posts on X from the last 24 hours about: "
            "Claude, ChatGPT, Cursor, AI agents, or AI workflows. "
            "For each: share the full post text, author handle, engagement numbers (likes, views, reposts), and post URL. "
            "Ranked by views/engagement. Skip low-engagement posts under 1000 views."
        }],
        "tools": [{"type": "x_search", "from_date": yesterday, "to_date": today}]
    })
    return extract_text(result)


def fetch_x_accounts():
    """Posts from tracked accounts from last 24 hours"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    result = grok_request({
        "model": "grok-4-fast",
        "input": [{"role": "user", "content":
            f"What did these accounts post on X in the last 24 hours that's relevant to AI workflows, "
            f"practical AI use, or shifts in how people work with AI: "
            f"{', '.join('@' + a for a in X_ACCOUNTS)}. "
            "For each relevant post: full text, author, engagement numbers, and URL. "
            "Skip low-engagement replies and off-topic posts."
        }],
        "tools": [{
            "type": "x_search",
            "allowed_x_handles": X_ACCOUNTS,
            "from_date": yesterday,
            "to_date": today
        }]
    })
    return extract_text(result)


def fetch_hn():
    """Top HN stories — returns formatted string"""
    try:
        req = urllib.request.Request("https://hacker-news.firebaseio.com/v0/topstories.json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            story_ids = json.loads(resp.read())[:40]

        stories = []
        for sid in story_ids:
            req = urllib.request.Request(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                story = json.loads(resp.read())
            if story and story.get("score", 0) >= 100:
                stories.append(
                    f"- [{story['title']}]({story.get('url', f'https://news.ycombinator.com/item?id={sid}')}) "
                    f"— {story['score']} pts, {story.get('descendants', 0)} comments"
                )
        return "\n".join(stories) if stories else "No high-scoring stories today."
    except Exception as e:
        return f"HN fetch error: {e}"


def fetch_rss():
    """Parse official company RSS feeds — returns formatted string"""
    items = []

    for company, url in RSS_FEEDS.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()

            root = ET.fromstring(content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            # Handle Atom feeds
            entries = root.findall(".//atom:entry", ns) or root.findall(".//entry")
            if entries:
                for entry in entries[:3]:
                    title_el = entry.find("atom:title", ns) or entry.find("title")
                    link_el = entry.find("atom:link", ns) or entry.find("link")
                    title = title_el.text if title_el is not None else "Untitled"
                    link = link_el.get("href", "") if link_el is not None else ""
                    if title:
                        items.append(f"- **{company}**: [{title}]({link})")
            else:
                # Handle RSS feeds
                for item in root.findall(".//item")[:3]:
                    title_el = item.find("title")
                    link_el = item.find("link")
                    title = title_el.text if title_el is not None else "Untitled"
                    link = link_el.text if link_el is not None else ""
                    if title:
                        items.append(f"- **{company}**: [{title}]({link})")

        except Exception as e:
            print(f"  RSS error ({company}): {e}")

    return "\n".join(items) if items else "No RSS items retrieved."


# ── Synthesis ─────────────────────────────────────────────────────────────────

def synthesize(x_engagement, x_accounts, hn, rss):
    prompt = f"""You are helping Mansi create content for an AI-focused Instagram Reels page.

Her audience: people in tech who already use AI but want to go beyond basic ChatGPT use.

Her 4 content formats:
- **Tip** — one specific thing the viewer can try
- **Explainer** — makes a vague AI term or trend finally make sense
- **Shift** — points to a bigger pattern changing how people work with AI
- **First Step** — gets someone who knows about X but hasn't tried it to actually do it

Her content filter (pursue): practical workflow discoveries, concepts people don't fully understand, launches that reveal a bigger behavioral shift, "what changed really" takes, patterns in how AI-native people work differently.

Here is today's signal from multiple sources:

---
### X — High Engagement Posts
{x_engagement}

---
### X — Tracked Accounts (@simonw @karpathy @swyx @rileysgoodside @emollick)
{x_accounts}

---
### Official Company Blogs (RSS)
{rss}

---
### Hacker News
{hn}

---

Produce a morning brief with exactly this structure:

## Top 3 Things Worth Paying Attention To
For each: what it is, why it matters to her audience, which format it fits (Tip/Explainer/Shift/First Step), and a one-line reel angle.

## Quick Scan
Bullet list of everything else worth knowing. One line each.

## Pass
Things that showed up but aren't worth a reel. One line each, just so she knows.

Keep it tight and scannable. No filler."""

    result = grok_request({
        "model": "grok-4-fast",
        "input": [{"role": "user", "content": prompt}]
    })
    return extract_text(result)


# ── Output ────────────────────────────────────────────────────────────────────

def write_report(content):
    OUTPUT_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = OUTPUT_DIR / f"{date_str}.md"
    path.write_text(f"# Morning Report — {date_str}\n\n{content}\n", encoding="utf-8")
    print(f"\nReport written to: {path}")
    return path


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not GROK_API_KEY:
        print("Error: set GROK_API_KEY environment variable")
        exit(1)

    print("Fetching high-engagement X posts...")
    x_engagement = fetch_x_engagement()

    print("Fetching tracked account posts...")
    x_accounts = fetch_x_accounts()

    print("Fetching Hacker News stories...")
    hn = fetch_hn()

    print("Fetching RSS feeds...")
    rss = fetch_rss()

    print("Synthesizing report...")
    report = synthesize(x_engagement, x_accounts, hn, rss)

    write_report(report)
    print("Done!")

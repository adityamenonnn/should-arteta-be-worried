"""
Scrapes r/Gunners for recent posts and scores them with VADER sentiment.
Computes and stores a daily worry index.
"""

import ssl
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import nltk
import requests

# Fix SSL cert issues on macOS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download("vader_lexicon", quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from db import get_conn, init_db

FEEDS = [
    "https://www.reddit.com/r/Gunners/new/.rss",
    "https://www.reddit.com/r/Gunners/hot/.rss",
    "https://www.reddit.com/r/Gunners/rising/.rss",
    "https://www.reddit.com/r/Gunners/top/.rss?t=week",
    "https://www.reddit.com/r/Gunners/top/.rss?t=month",
]
HEADERS = {"User-Agent": "should-arteta-be-worried:v1.0"}
ATOM_NS = "http://www.w3.org/2005/Atom"

sia = SentimentIntensityAnalyzer()


def fetch_posts_from_feed(url):
    """Fetch posts from a single RSS feed URL."""
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    posts = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        # The entry ID is the full Reddit URL
        link_el = entry.find(f"{{{ATOM_NS}}}link")
        post_url = link_el.get("href", "") if link_el is not None else ""

        id_el = entry.find(f"{{{ATOM_NS}}}id")
        post_id_raw = id_el.text if id_el is not None else post_url
        post_id = post_id_raw.rstrip("/").rsplit("/", 1)[-1] if "/" in post_id_raw else post_id_raw

        title = entry.find(f"{{{ATOM_NS}}}title").text or ""
        updated = entry.find(f"{{{ATOM_NS}}}updated").text

        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        created_utc = int(dt.timestamp())

        posts.append({
            "id": post_id,
            "title": title,
            "url": post_url,
            "score": 0,
            "upvote_ratio": 0,
            "num_comments": 0,
            "created_utc": created_utc,
        })

    return posts


def fetch_all_posts():
    """Fetch posts from all configured feeds."""
    all_posts = []
    seen_ids = set()

    for url in FEEDS:
        try:
            print(f"  Fetching {url.split('/')[-1].split('?')[0]}...")
            posts = fetch_posts_from_feed(url)
            for p in posts:
                if p["id"] not in seen_ids:
                    seen_ids.add(p["id"])
                    all_posts.append(p)
            time.sleep(2)  # respect rate limits
        except Exception as e:
            print(f"  Skipped (rate limited or error): {e}")

    return all_posts


def score_sentiment(title):
    """Return VADER compound score for a post title (-1 to 1)."""
    return sia.polarity_scores(title)["compound"]


def store_posts(posts):
    """Insert posts into the database, skipping duplicates."""
    conn = get_conn()
    inserted = 0
    for p in posts:
        sentiment = score_sentiment(p["title"])
        try:
            conn.execute(
                """INSERT OR IGNORE INTO posts
                   (id, title, url, score, upvote_ratio, num_comments, sentiment, created_utc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (p["id"], p["title"], p["url"], p["score"], p["upvote_ratio"],
                 p["num_comments"], sentiment, p["created_utc"]),
            )
            inserted += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return inserted


def compute_daily_index():
    """Roll up post sentiments into a daily worry score.

    Worry score: 0 = fans are ecstatic, 100 = fans are furious.
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT date(created_utc, 'unixepoch') as day,
               AVG(sentiment) as avg_sent,
               COUNT(*) as cnt
        FROM posts
        GROUP BY day
        ORDER BY day
    """).fetchall()

    for row in rows:
        avg = row["avg_sent"]
        worry = (1 - avg) / 2 * 100  # map [-1,1] -> [100, 0]
        conn.execute(
            """INSERT OR REPLACE INTO daily_index (date, avg_sentiment, post_count, worry_score)
               VALUES (?, ?, ?, ?)""",
            (row["day"], avg, row["cnt"], round(worry, 2)),
        )

    conn.commit()
    conn.close()
    print(f"Updated daily index for {len(rows)} day(s).")


def main():
    init_db()
    print("Fetching posts from r/Gunners...")
    posts = fetch_all_posts()
    print(f"Fetched {len(posts)} unique posts.")

    inserted = store_posts(posts)
    print(f"Stored {inserted} new posts.")

    compute_daily_index()
    print("Done.")


if __name__ == "__main__":
    main()

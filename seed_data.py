"""
Seeds the database with realistic historical r/Gunners post titles
so the dashboard has 25 days of data to display.
Run once, then delete. Real scraper data will layer on top.
"""

import random
import ssl
import time
from datetime import datetime, timedelta, timezone

import nltk

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

nltk.download("vader_lexicon", quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from db import get_conn, init_db

sia = SentimentIntensityAnalyzer()

# Realistic r/Gunners post titles across different moods
TITLES = [
    # Positive
    "Saka is genuinely world class, what a player we have",
    "Saliba masterclass today, best CB in the league",
    "Rice was absolutely immense in midfield, dominated everything",
    "The atmosphere at the Emirates was incredible today",
    "Arteta's tactics were spot on, we completely outplayed them",
    "Havertz proving everyone wrong, brilliant performance",
    "We are genuine title contenders this season",
    "Odegaard is the best midfielder in the Premier League",
    "What a signing Calafiori has been, the man is everywhere",
    "Raya with another clean sheet, what a keeper",
    "Martinelli back to his best, terrorised their defence",
    "Trossard coming off the bench and changing the game again",
    "Three points and a clean sheet, perfect day",
    "Our squad depth this season is unreal",
    "The way we controlled that game was beautiful football",
    "Timber is such a baller, can play anywhere",
    "That second half performance was genuinely elite",
    "We just beat a top 6 side away from home, massive result",
    "The pressing from the front three was relentless today",
    "Arsenal Women continue to dominate, so proud of this club",
    # Neutral / mixed
    "Pre-match thread: Arsenal vs Crystal Palace",
    "Post-match thread: Arsenal 1-1 Aston Villa",
    "Lineup announced for tomorrow's game",
    "Transfer rumour roundup for the week",
    "Arteta press conference ahead of the weekend",
    "Interesting stat about our set piece record this season",
    "Rival watch thread: City vs Liverpool",
    "Daily discussion thread",
    "Does anyone have a clip of the Saka skill in the first half?",
    "Match going fans, what was the atmosphere like today?",
    "What formation do you think we should play this weekend?",
    "Player ratings thread after yesterday's match",
    "Injury update from training today",
    "Who should start on the right wing this weekend?",
    "Comparison of our stats vs last season at this point",
    # Negative
    "VAR is an absolute joke, we got robbed today",
    "Arteta got his tactics completely wrong today",
    "We desperately need a striker in January",
    "That was the worst performance I've seen all season",
    "How did the ref not give that as a penalty?",
    "Havertz missing sitters again, we need a proper number 9",
    "We keep dropping points against bottom half teams",
    "City getting away with dodgy decisions again, the league is rigged",
    "Spurs fans celebrating like they won the league after a draw",
    "Our away form is becoming a serious concern",
    "Why does Arteta keep making the same substitutions too late?",
    "We lost control of that game in the second half, really poor",
    "The squad looks tired, we need rotation",
    "Another injury, our medical team needs looking at",
    "That defending was shocking, League Two level stuff",
    "We bottled it again, same story every year",
    "Really frustrated with how we set up today, too defensive",
    "Missing Partey badly in midfield, no one can replace him",
    "Liverpool are running away with it while we draw at home",
    "Season is slipping away if we keep performing like this",
]

def seed():
    init_db()
    conn = get_conn()

    now = datetime.now(timezone.utc)
    post_id_base = 100000

    for day_offset in range(25, 0, -1):
        day = now - timedelta(days=day_offset)
        # 8-15 posts per day
        num_posts = random.randint(8, 15)
        titles = random.sample(TITLES, min(num_posts, len(TITLES)))

        for i, title in enumerate(titles):
            # Spread posts across the day
            hour = random.randint(6, 23)
            minute = random.randint(0, 59)
            post_time = day.replace(hour=hour, minute=minute, second=0)
            created_utc = int(post_time.timestamp())

            post_id = f"seed_{post_id_base}"
            post_id_base += 1
            sentiment = sia.polarity_scores(title)["compound"]
            url = ""

            conn.execute(
                """INSERT OR IGNORE INTO posts
                   (id, title, url, score, upvote_ratio, num_comments, sentiment, created_utc)
                   VALUES (?, ?, ?, 0, 0, 0, ?, ?)""",
                (post_id, title, url, sentiment, created_utc),
            )

    conn.commit()
    conn.close()
    print("Seeded 25 days of historical data.")

    # Recompute daily index
    from scraper import compute_daily_index
    compute_daily_index()


if __name__ == "__main__":
    seed()

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            upvote_ratio REAL DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            sentiment REAL DEFAULT 0,
            created_utc INTEGER NOT NULL,
            scraped_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_index (
            date TEXT PRIMARY KEY,
            avg_sentiment REAL NOT NULL,
            post_count INTEGER NOT NULL,
            worry_score REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            opponent TEXT NOT NULL,
            arsenal_goals INTEGER NOT NULL,
            opponent_goals INTEGER NOT NULL,
            competition TEXT DEFAULT 'Premier League',
            UNIQUE(date, opponent)
        );
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialised.")

"""
Fetches recent Arsenal match results from the football-data.org free API.
Free tier: 10 requests/minute, no API key needed for basic endpoints.
"""

import requests
from db import get_conn, init_db

API_BASE = "https://api.football-data.org/v4"
ARSENAL_ID = 57  # Arsenal's ID in football-data.org
HEADERS = {"X-Auth-Token": ""}  # leave empty for free tier


def fetch_matches():
    """Fetch Arsenal's recent finished matches."""
    url = f"{API_BASE}/teams/{ARSENAL_ID}/matches"
    params = {"status": "FINISHED", "limit": 30}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json().get("matches", [])


def store_matches(matches):
    conn = get_conn()
    stored = 0
    for m in matches:
        home = m["homeTeam"]["shortName"]
        away = m["awayTeam"]["shortName"]
        home_goals = m["score"]["fullTime"]["home"]
        away_goals = m["score"]["fullTime"]["away"]
        date = m["utcDate"][:10]
        competition = m["competition"]["name"]

        if home == "Arsenal":
            opponent = away
            arsenal_goals = home_goals
            opp_goals = away_goals
        elif away == "Arsenal":
            opponent = home
            arsenal_goals = away_goals
            opp_goals = home_goals
        else:
            continue

        try:
            conn.execute(
                """INSERT OR IGNORE INTO matches
                   (date, opponent, arsenal_goals, opponent_goals, competition)
                   VALUES (?, ?, ?, ?, ?)""",
                (date, opponent, arsenal_goals, opp_goals, competition),
            )
            stored += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    return stored


def main():
    init_db()
    print("Fetching Arsenal match results...")
    matches = fetch_matches()
    print(f"Got {len(matches)} matches from API.")

    stored = store_matches(matches)
    print(f"Stored {stored} new match results.")


if __name__ == "__main__":
    main()

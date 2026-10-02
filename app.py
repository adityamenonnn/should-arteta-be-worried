from pathlib import Path

from fastapi import FastAPI, Query, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from chemistry import load_players, get_squad_chemistry, rank_replacements, optimize_signings, monte_carlo_chemistry, LINKS
from db import get_conn, init_db
from forecast import build_forecast
from sentiment_model import get_model_info

app = FastAPI(title="Should Arteta Be Worried?")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/index")
def get_index(days: int = Query(30, ge=1, le=365)):
    """Return the daily worry index for the last N days."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT date, avg_sentiment, post_count, worry_score
           FROM daily_index
           ORDER BY date DESC
           LIMIT ?""",
        (days,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


@app.get("/api/posts")
def get_posts(limit: int = Query(50, ge=1, le=200)):
    """Return recent posts with sentiment scores."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, title, url, score, num_comments, sentiment, created_utc
           FROM posts
           ORDER BY created_utc DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/topics")
def get_topics():
    """Return average sentiment grouped by topic keywords."""
    topics = {
        "Arteta": ["arteta", "manager", "mikel", "tactics", "lineup"],
        "Transfers": ["sign", "transfer", "buy", "sell", "loan", "rumour", "deal", "bid"],
        "Players": ["saka", "rice", "saliba", "havertz", "raya", "odegaard", "martinelli", "trossard", "timber", "calafiori"],
        "Referees": ["ref", "referee", "var", "penalty", "offside", "decision"],
        "Rivals": ["spurs", "tottenham", "chelsea", "city", "liverpool", "united"],
    }

    conn = get_conn()
    all_posts = conn.execute("SELECT title, sentiment FROM posts").fetchall()
    conn.close()

    result = {}
    for topic, keywords in topics.items():
        matching = [
            r["sentiment"]
            for r in all_posts
            if any(kw in r["title"].lower() for kw in keywords)
        ]
        if matching:
            avg = sum(matching) / len(matching)
            result[topic] = {
                "avg_sentiment": round(avg, 3),
                "post_count": len(matching),
                "worry_score": round((1 - avg) / 2 * 100, 1),
            }

    return result


@app.get("/api/matches")
def get_matches(limit: int = Query(20, ge=1, le=50)):
    """Return recent Arsenal match results."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT date, opponent, arsenal_goals, opponent_goals, competition
           FROM matches
           ORDER BY date DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# --- Squad Lab endpoints ---

@app.get("/squad")
def squad_page():
    return FileResponse(STATIC_DIR / "squad.html")


@app.get("/api/squad")
def get_squad():
    """Return Arsenal squad and transfer targets."""
    return load_players()


@app.post("/api/chemistry")
def compute_chemistry(squad: dict = Body(...)):
    """Compute chemistry links for a given squad layout.

    Expects: {"GK": "raya", "RB": "white", ...}
    """
    data = load_players()
    all_players = {p["id"]: p for p in data["arsenal"] + data.get("bench", []) + data.get("targets", [])}

    resolved = {}
    for pos, pid in squad.items():
        if pid in all_players:
            resolved[pos] = all_players[pid]

    links = get_squad_chemistry(resolved)
    avg = sum(l["score"] for l in links) / len(links) if links else 50
    return {"links": links, "overall": round(avg, 1)}


@app.get("/api/candidates/{position}")
def get_candidates(position: str):
    """Get ranked transfer targets for a position based on chemistry fit."""
    data = load_players()

    # Build default squad
    squad = {}
    for p in data["arsenal"]:
        squad[p["position"]] = p

    return rank_replacements(position, squad, data["targets"])


@app.get("/api/forecast")
def get_forecast(days: int = Query(7, ge=1, le=30)):
    """Predict the worry index for the next N days using Ridge regression."""
    return build_forecast(days_ahead=days)


@app.get("/api/model-info")
def model_info():
    """Return info about which sentiment model is active."""
    return get_model_info()


@app.post("/api/montecarlo")
def run_montecarlo(squad: dict = Body(...)):
    """Run Monte Carlo simulation on squad chemistry.

    Adds Gaussian noise to player stats across 1000 simulations
    to quantify uncertainty in chemistry scores.
    """
    data = load_players()
    all_players = {p["id"]: p for p in data["arsenal"] + data.get("bench", []) + data.get("targets", [])}

    resolved = {}
    for pos, pid in squad.items():
        if pid in all_players:
            resolved[pos] = all_players[pid]

    return monte_carlo_chemistry(resolved, n_simulations=1000)


@app.post("/api/optimize")
def optimize(max_signings: int = Body(3, embed=True)):
    """Find the optimal combination of signings to maximize team chemistry.

    Treats the squad as a graph (positions = nodes, chemistry = edge weights)
    and brute-forces all combinations of 1..max_signings swaps to find the
    assignment that maximizes total edge weight.
    """
    data = load_players()

    base_squad = {}
    for p in data["arsenal"]:
        base_squad[p["position"]] = p

    bench = data.get("bench", [])
    targets = data.get("targets", [])

    return optimize_signings(base_squad, bench, targets, max_signings=max_signings)

# Should Arteta Be Worried?

A full-stack fan sentiment tracker and squad chemistry optimizer for Arsenal FC. Scrapes Reddit for real-time fan opinion, scores it with NLP, and serves an interactive dashboard. Includes a squad lab where you can swap players, visualize chemistry between positions, and run a Branch and Bound algorithm to find the mathematically optimal set of transfer signings.

**Live data from r/Gunners. Squad data from the Premier League API. No external ML libraries.**

---

## Features

### 1. Sentiment Dashboard

Monitors fan sentiment on r/Gunners and distills it into a single **Worry Index** (0-100).

- **Real-time scraping**: Pulls posts from multiple Reddit RSS feeds (new, hot, top/week, top/month) every 6 hours via GitHub Actions
- **NLP scoring**: Each post title is scored using VADER (Valence Aware Dictionary and sEntiment Reasoner), which rates text from -1 (negative) to +1 (positive) using a lexicon of ~7,500 words plus rules for caps, negation, punctuation, and degree modifiers
- **Worry Index**: Maps the daily average sentiment to a 0-100 scale: `worry = (1 - avg_sentiment) / 2 * 100`
- **Trend chart**: Line graph showing the index over time, with Arsenal match results overlaid as scatter points so you can correlate wins/losses to sentiment swings
- **Topic breakdown**: Posts are bucketed by keyword matching into topics (Arteta, Transfers, Players, Referees, Rivals), each with its own worry score
- **Post feed**: Scrollable list of scraped posts, each linked to the original Reddit thread with a color-coded sentiment badge

### 2. Squad Lab

Interactive formation builder with FIFA-style chemistry lines, powered by real player statistics.

- **Formation view**: SVG pitch showing Arsenal's starting XI in a 4-3-3, with player nodes at their positions
- **Chemistry links**: 17 edges connecting adjacent positions (e.g. RB-RW, CDM-RCM, LW-ST). Each edge is scored 0-100 based on how well the two players' stats complement each other, and color-coded green/yellow/red
- **Live squad data**: Starting XI and bench pulled from the Fantasy Premier League API, mapped to formation positions
- **Player swapping**: Click any player to open a panel showing transfer targets and bench alternatives. Each candidate has a side-by-side stat comparison against the current player. Click to swap them in and watch the chemistry lines update instantly
- **15 transfer targets** across all positions, including PL players (stats from FPL API) and non-PL targets (Wirtz, Nico Williams, Kvaratskhelia, Davies, Kim Min-jae) with manually sourced stats

### 3. Transfer Optimizer (Branch and Bound)

Given a budget of 1-3 signings, finds the combination that maximizes total team chemistry.

**How it works:**

The squad is modelled as a **weighted graph**:
- **Nodes** = formation positions (GK, RB, RCB, LCB, LB, CDM, RCM, LCM, RW, ST, LW)
- **Edges** = chemistry links between adjacent positions (17 total)
- **Edge weight** = chemistry score between the two assigned players

The optimizer uses **Branch and Bound** (Land and Doig, 1960) to search the space of possible signing combinations:

1. **Branching**: At each position with available candidates, the algorithm branches into "keep current player" or "swap in candidate X"
2. **Bounding**: At each node, an optimistic upper bound is computed by assuming every remaining position gets the best possible single-swap improvement. If this upper bound cannot beat the current best solution, the entire subtree is pruned
3. **Pruning**: Subtrees that provably cannot improve on the incumbent are skipped entirely, avoiding unnecessary computation

The dashboard shows **nodes explored** vs **nodes pruned** so you can see the algorithm's search efficiency. For a typical run with 3 max signings and ~20 candidates, Branch and Bound explores ~130 nodes and prunes ~55 subtrees, compared to the ~1,300 nodes a naive brute-force search would evaluate.

---

## Chemistry Scoring

Chemistry between two connected players is calculated from complementary stat pairings specific to their positional relationship:

| Link | What's measured |
|------|----------------|
| Fullback to Winger | Crossing frequency vs. carry progression, xA vs. xG, press alignment |
| CB to CB | Aerial dominance, passing accuracy, interception/tackle balance |
| CDM to CM | Progressive passing vs. key passes, tackle/dribble balance, press intensity |
| CM to Winger | Through balls vs. dribbling, xA vs. xG, creative synergy |
| Winger to ST | xA vs. xG, crossing vs. aerial ability, key passes vs. finishing |

Each stat is normalized to 0-1 using observed ranges across top leagues. The pair score uses a **geometric mean** (`sqrt(norm_a * norm_b)`) which rewards both players being strong rather than one compensating for the other. Weighted pairs are summed into a final 0-100 score per link.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI |
| Database | SQLite |
| NLP | VADER (nltk) |
| Data sources | Reddit RSS, FPL API, football-data.org |
| Frontend | Vanilla HTML/CSS/JS, Chart.js |
| Scheduling | GitHub Actions (cron every 6 hours) |
| Hosting | Runs locally, deployable to Render free tier |

No external ML/AI libraries beyond nltk's VADER lexicon. The chemistry model, Branch and Bound optimizer, and all scoring logic are implemented from scratch.

---

## Project Structure

```
should-arteta-be-worried/
  app.py                  # FastAPI server, API endpoints, static file serving
  scraper.py              # Reddit RSS scraper + VADER sentiment scoring
  matches.py              # Arsenal match results from football-data.org
  fetch_squad.py          # Pulls live squad from FPL API, maps to formation
  chemistry.py            # Chemistry scoring engine + Branch and Bound optimizer
  db.py                   # SQLite schema and connection helpers
  seed_data.py            # Seeds historical sentiment data for demo purposes
  data/
    players.json          # Squad data: starters, bench, transfer targets
  static/
    index.html            # Sentiment dashboard page
    style.css             # Shared dark theme styles
    app.js                # Dashboard charts and data loading
    squad.html            # Squad lab page
    squad.css             # Pitch and swap panel styles
    squad.js              # Formation rendering, chemistry lines, optimizer UI
  .github/workflows/
    scrape.yml            # GitHub Actions cron job for automated scraping
```

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Scrape initial data
python scraper.py

# Fetch squad from FPL API
python fetch_squad.py

# Start the server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open:
- **http://localhost:8000** for the sentiment dashboard
- **http://localhost:8000/squad** for the squad lab

---

## Key Algorithms and Concepts

For interview reference:

- **VADER Sentiment Analysis**: Rule-based NLP model using a human-validated lexicon. Handles social media text well (slang, caps, punctuation, negation). O(n) per document where n is word count.
- **Branch and Bound**: Combinatorial optimization algorithm that explores a search tree while pruning branches using upper-bound estimates. Guarantees finding the global optimum. Worst case is exponential but pruning typically reduces the search space significantly.
- **Graph Modelling**: Squad modelled as a weighted undirected graph. Chemistry optimization is a constrained maximum weight assignment problem on this graph.
- **Geometric Mean Scoring**: Used for chemistry pairing to ensure both players must contribute. Unlike arithmetic mean, geometric mean penalizes lopsided pairs where one stat is high and the other is low.
- **Data Pipeline**: Automated ETL from Reddit RSS to SQLite with deduplication, transformation (sentiment scoring), and aggregation (daily index rollup).

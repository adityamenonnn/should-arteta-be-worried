# Should Arteta Be Worried?

A fan sentiment tracker and squad chemistry optimizer for Arsenal FC. Scrapes r/Gunners for real-time fan opinion, scores it with a trained NLP classifier, and serves an interactive dashboard. Includes a squad lab where you can swap players in a 4-3-3 formation, visualize chemistry between positions, run Monte Carlo simulations on chemistry uncertainty, and use Branch and Bound to find the mathematically optimal set of transfer signings.

**Live data from r/Gunners. Squad data from the FPL API. Sentiment classifier trained from scratch.**

![Python](https://img.shields.io/badge/python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)

---

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
  - [Sentiment Pipeline](#1-sentiment-pipeline)
  - [Chemistry Model](#2-chemistry-model)
  - [Branch and Bound Optimizer](#3-branch-and-bound-optimizer)
  - [Monte Carlo Simulation](#4-monte-carlo-simulation)
  - [Worry Forecast](#5-worry-forecast)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [How to Reproduce and Learn From This](#how-to-reproduce-and-learn-from-this)
- [Tech Stack](#tech-stack)

---

## Features

### Sentiment Dashboard
- Scrapes posts from 5 r/Gunners RSS feeds (new, hot, rising, top/week, top/month) every 6 hours via GitHub Actions
- Scores each post with a trained TF-IDF + Logistic Regression classifier that outperforms VADER by 18% F1 on football text
- Computes a daily Worry Index (0-100) and displays the trend over time
- Overlays Arsenal match results on the trend chart so you can see how wins/losses affect sentiment
- Breaks down sentiment by topic (Arteta, Transfers, Players, Referees, Rivals)
- Shows a 7-day worry forecast using Ridge regression

### Squad Lab
- Interactive 4-3-3 formation with chemistry lines between adjacent positions
- Click any player to open a swap panel with transfer targets and bench alternatives
- Radar chart comparison appears on hover, showing normalized stats side-by-side
- Monte Carlo simulation adds noise to stats across 1,000 runs to show chemistry uncertainty
- Branch and Bound optimizer finds the best combination of 1-3 signings to maximize team chemistry

---

## How It Works

### 1. Sentiment Pipeline

**Data collection** (`scraper.py`):
The scraper pulls posts from Reddit's Atom RSS feeds. For each post, it extracts the title, timestamp, and a unique ID. Posts are deduplicated across feeds and stored in SQLite.

**Sentiment scoring** (`sentiment_model.py`, `train_sentiment.py`):

The project uses a two-stage approach:

1. **VADER** (Valence Aware Dictionary and sEntiment Reasoner) provides noisy baseline labels. VADER uses a lexicon of ~7,500 words rated for sentiment, plus rules for caps, negation, punctuation, and degree modifiers. It's fast and decent on social media text, but it doesn't understand football slang ("bottled" = very negative, "masterclass" = very positive, "pre-match thread" = neutral).

2. **TF-IDF + Logistic Regression** is trained on these VADER labels with football-specific corrections applied. The corrections are a list of regex patterns that override VADER's labels for football terminology. For example:
   - "bottled", "sitters", "robbed", "shocking" are forced negative
   - "masterclass", "world class", "clean sheet", "title contenders" are forced positive
   - "pre-match thread", "daily discussion", "lineup announced" are forced neutral

The pipeline:
```
Reddit RSS posts
    -> VADER labels each title (positive/neutral/negative)
    -> Football overrides correct ~15-20% of labels
    -> 36 synthetic examples are added for edge cases
    -> TF-IDF vectorizer converts titles to 5000-dim sparse vectors (unigrams + bigrams)
    -> Logistic Regression (balanced class weights) learns the mapping
    -> Saves to models/sentiment_pipeline.pkl
```

**Why TF-IDF + LogReg and not a neural model?**
- Lightweight (42KB model file vs 250MB+ for DistilBERT)
- Deploys anywhere without GPU
- 93% F1 is plenty for this use case
- The interesting part is the domain-specific label correction, not the model architecture

**Worry Index**: maps average daily sentiment [-1, 1] to [0, 100]:
```
worry = (1 - avg_sentiment) / 2 * 100
```
So +1 (very positive) = 0 worry, -1 (very negative) = 100 worry.

### 2. Chemistry Model

**The graph** (`chemistry.py`):

The squad is modelled as a weighted undirected graph:
- **11 nodes** = formation positions (GK, RB, RCB, LCB, LB, CDM, RCM, LCM, RW, ST, LW)
- **17 edges** = links between adjacent positions in a 4-3-3
- **Edge weight** = chemistry score (0-100) between the two players at those positions

**How a chemistry score is calculated:**

Each positional link has 4-5 stat pairings that measure how well two players complement each other. For example, the RB-RW link uses:

| Stat A (RB) | Stat B (RW) | Weight |
|---|---|---|
| crosses/90 | progressive carries/90 | 0.3 |
| progressive passes/90 | dribbles/90 | 0.2 |
| xA/90 | xG/90 | 0.3 |
| press/90 | press/90 | 0.2 |

For each pair:
1. Both stats are normalized to [0, 1] using observed min/max ranges across top leagues
2. **Geometric mean**: `score = sqrt(norm_a * norm_b)`
3. The weighted sum across all pairs gives the link score, scaled to 0-100

**Why geometric mean?** It rewards both players being strong. If one player has 0.9 and the other has 0.1, arithmetic mean gives 0.5 (decent), but geometric mean gives 0.3 (bad). This correctly penalizes lopsided pairings where one player doesn't pull their weight.

**Team chemistry** = simple average of all 17 link scores.

### 3. Branch and Bound Optimizer

Given a budget of 1-3 signings, finds the combination that maximizes total team chemistry.

**Algorithm** (Land and Doig, 1960):

The search space is a tree where each level corresponds to a "swappable" position, and at each position we choose: keep the current player, or swap in one of the candidates.

```
                        [root: base squad]
                       /                    \
              [keep RCB]                  [swap RCB -> Kim]
              /        \                  /              \
      [keep LCB]    [swap LCB]    [keep LCB]       [swap LCB]
         ...           ...           ...               ...
```

**Bounding**: At each node, we compute an optimistic upper bound by assuming every remaining position gets its best possible single-swap improvement. If this upper bound can't beat the current best solution, the entire subtree is pruned.

**Example run** (3 max signings, ~20 candidates):
- Naive brute force: ~1,300 nodes
- Branch and Bound: ~130 explored, ~55 pruned
- Same optimal result, ~10x less computation

The dashboard shows nodes explored vs pruned so you can see the search efficiency.

### 4. Monte Carlo Simulation

The deterministic chemistry score assumes player stats are fixed. In reality, performance varies game to game. Monte Carlo quantifies this uncertainty.

**How it works:**
1. For each of 1,000 simulations, every player stat is perturbed with Gaussian noise: `stat += N(0, 0.1 * (max - min))` where max/min are the stat's observed range
2. Chemistry is recomputed with the noisy stats
3. The result is a distribution of chemistry outcomes

**Output**: mean, standard deviation, 5th/25th/75th/95th percentiles, and a histogram. This lets you say "chemistry is 33.4 +/- 1.7 with 90% CI [30.5, 36.0]" instead of just "chemistry is 33.4".

### 5. Worry Forecast

Predicts the worry index for the next 7 days using Ridge regression.

**Features** (11 total):
- `lag_1d`, `lag_3d`, `lag_7d`: recent worry scores
- `trend`: lag_1 - lag_3 (is worry rising or falling?)
- `volatility`: standard deviation of last 7 days
- `post_volume`: number of posts (more posts = more engagement)
- `match_impact`: most recent result mapped to a sentiment impact score
- `win_rate`, `loss_rate`, `draw_rate`, `avg_goal_diff`: last 5 matches

**Ridge regression** is fitted with closed-form solution: `w = (X'X + alpha*I)^{-1} X'y`. Implemented from scratch with NumPy (no sklearn at inference time). The forecast iteratively predicts each day, feeding predictions back as lagged features.

---

## Project Structure

```
should-arteta-be-worried/
  app.py                  # FastAPI server, all API endpoints
  scraper.py              # Reddit RSS scraper + sentiment scoring
  matches.py              # Arsenal match results from football-data.org
  fetch_squad.py          # Pulls squad from FPL API, maps to 4-3-3
  chemistry.py            # Chemistry scoring, B&B optimizer, Monte Carlo
  forecast.py             # Worry forecast (Ridge regression)
  train_sentiment.py      # Trains the sentiment classifier
  sentiment_model.py      # Loads trained model for inference (VADER fallback)
  db.py                   # SQLite schema + connection helpers
  seed_data.py            # Seeds fake historical data for demo
  data/
    players.json          # Squad: starters, bench, transfer targets
  models/
    sentiment_pipeline.pkl  # Trained TF-IDF + LogReg (gitignored)
    metrics.json            # F1, accuracy, comparison vs VADER
  static/
    index.html            # Sentiment dashboard
    style.css             # Shared styles
    app.js                # Dashboard charts and data loading
    squad.html            # Squad lab page
    squad.css             # Pitch, swap panel, monte carlo styles
    squad.js              # Formation rendering, radar, optimizer UI
  .github/workflows/
    scrape.yml            # Cron job: scrape + commit every 6 hours
  Procfile                # For Render deployment
  render.yaml             # Render service config
```

---

## Setup

### Prerequisites
- Python 3.10+
- pip

### Install and run

```bash
# clone it
git clone https://github.com/adityamenonnn/should-arteta-be-worried.git
cd should-arteta-be-worried

# install deps
pip install -r requirements.txt

# seed the database with demo data (so the dashboard isn't empty)
python3 seed_data.py

# fetch the current Arsenal squad from FPL API
python3 fetch_squad.py

# train the sentiment classifier
python3 train_sentiment.py

# start the server
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Then open:
- **http://localhost:8000** for the sentiment dashboard
- **http://localhost:8000/squad** for the squad lab

### Scrape real data

```bash
# scrape r/Gunners right now
python3 scraper.py

# fetch Arsenal match results (needs football-data.org, may 403 without API key)
python3 matches.py
```

The GitHub Actions workflow runs `scraper.py` every 6 hours automatically.

---

## How to Reproduce and Learn From This

If you want to build something similar or understand how each piece works, here's the order I'd suggest:

### Step 1: The data pipeline (start here)

Read `db.py` first. It's 50 lines. It creates three SQLite tables: posts, daily_index, matches.

Then read `scraper.py`. It fetches RSS feeds, parses XML, scores sentiment, and stores posts. Run it once: `python3 scraper.py`. Check the database: `sqlite3 data.db "SELECT title, sentiment FROM posts LIMIT 10"`.

**Key concept**: an ETL pipeline (Extract from RSS, Transform with NLP scoring, Load into SQLite).

### Step 2: The sentiment model

Read `train_sentiment.py` top to bottom. The core ideas:
- VADER gives you noisy labels for free (no manual annotation needed)
- Domain-specific overrides fix the labels VADER gets wrong
- TF-IDF converts text to numerical features (bag of words with term frequency weighting)
- Logistic Regression learns a linear decision boundary in that feature space
- The geometric trick: using a worse model's output as training data for a better model

Run `python3 train_sentiment.py` and look at the classification report. Try adding your own override patterns and see if F1 changes.

### Step 3: The chemistry graph

Read `chemistry.py` from the top. Follow the data flow:
1. `LINKS` defines the graph topology (which positions connect)
2. `CHEMISTRY_RULES` defines what stats matter for each link
3. `normalize()` maps raw stats to [0, 1]
4. `compute_link_chemistry()` combines normalized stats with geometric mean
5. `get_squad_chemistry()` computes all 17 links

Try modifying the stat pairings or weights and see how chemistry changes.

### Step 4: Branch and Bound

Read `optimize_signings()` in `chemistry.py`. It's a textbook B&B implementation:
1. Start with the base squad
2. At each position, branch: keep current player or swap in a candidate
3. Compute upper bound for remaining positions
4. If upper bound <= current best, prune
5. Track the best solution found

To understand B&B intuitively: imagine you're buying 3 items from a shop. If after picking 1 item you can already tell that even the best remaining 2 items won't make this a better deal than what you've already found, skip that entire branch of choices.

### Step 5: Monte Carlo

Read `monte_carlo_chemistry()` in `chemistry.py`. The idea:
1. Player stats aren't fixed, they have variance
2. Add Gaussian noise proportional to each stat's range
3. Recompute chemistry 1,000 times
4. The distribution tells you how robust the chemistry score is

This is the same technique used in financial risk modelling (Value at Risk), physics simulations, and game AI.

### Step 6: The forecast

Read `forecast.py`. It's a simple regression:
1. Build features from historical data (lagged values, trends, match results)
2. Fit Ridge regression (linear regression + L2 regularization)
3. Predict iteratively (each day's prediction becomes the next day's input)

The Ridge regression is implemented from scratch: `w = (X'X + aI)^{-1} X'y`. Compare this to using `sklearn.linear_model.Ridge` and you'll see they give the same result.

### Step 7: The frontend

Read `static/app.js` and `static/squad.js`. It's all vanilla JS:
- `fetch()` calls to the API
- Chart.js for line/scatter charts
- SVG for the radar chart and chemistry lines
- DOM manipulation for everything else

No React, no build step, no npm. Just HTML, CSS, JS files served by FastAPI.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Database | SQLite |
| NLP | TF-IDF + Logistic Regression (scikit-learn), VADER fallback (nltk) |
| Forecasting | Ridge Regression (NumPy, from scratch) |
| Optimization | Branch and Bound (from scratch) |
| Simulation | Monte Carlo (NumPy) |
| Data sources | Reddit RSS, FPL API, football-data.org |
| Frontend | Vanilla HTML/CSS/JS, Chart.js, SVG |
| CI/CD | GitHub Actions (cron every 6h) |
| Deployment | Render (Procfile + render.yaml) |

No external ML/AI libraries beyond scikit-learn for training and nltk's VADER as a fallback. The chemistry model, Branch and Bound optimizer, Monte Carlo simulation, Ridge regression forecaster, and all scoring logic are implemented from scratch.

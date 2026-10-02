"""
Worry Index forecaster.

Predicts next-week sentiment using:
  - Lagged sentiment (last 1, 3, 7 days)
  - Recent form (W/D/L in last 5 matches)
  - Upcoming fixture difficulty (opponent league position, home/away)
  - Day-of-week effects

Uses Ridge regression with handcrafted features. Trained on historical
daily_index + match data from the database.
"""

import numpy as np
from db import get_conn


def _get_historical_data():
    """Pull daily worry scores and match results."""
    conn = get_conn()
    index_rows = conn.execute(
        "SELECT date, worry_score, avg_sentiment, post_count FROM daily_index ORDER BY date"
    ).fetchall()
    match_rows = conn.execute(
        "SELECT date, arsenal_goals, opponent_goals, opponent FROM matches ORDER BY date"
    ).fetchall()
    conn.close()
    return [dict(r) for r in index_rows], [dict(r) for r in match_rows]


def _match_result_score(arsenal_goals, opponent_goals):
    """Convert match result to a sentiment impact score."""
    diff = arsenal_goals - opponent_goals
    if diff > 0:
        return -10.0 * min(diff, 3)  # Wins reduce worry (capped at 3 goal diff)
    elif diff < 0:
        return 12.0 * min(abs(diff), 3)  # Losses increase worry
    return 3.0  # Draws slightly increase worry


def _recent_form_features(matches, before_date):
    """Compute form features from the last 5 matches before a given date."""
    recent = [m for m in matches if m["date"] < before_date][-5:]
    if not recent:
        return [0.0, 0.0, 0.0, 0.0]

    wins = sum(1 for m in recent if m["arsenal_goals"] > m["opponent_goals"])
    draws = sum(1 for m in recent if m["arsenal_goals"] == m["opponent_goals"])
    losses = sum(1 for m in recent if m["arsenal_goals"] < m["opponent_goals"])
    avg_gd = np.mean([m["arsenal_goals"] - m["opponent_goals"] for m in recent])

    return [wins / len(recent), losses / len(recent), draws / len(recent), avg_gd]


def _build_features(index_data, match_data):
    """Build feature matrix and target vector."""
    X, y = [], []

    for i in range(7, len(index_data)):
        row = index_data[i]
        date = row["date"]

        # Lagged worry scores
        lag_1 = index_data[i - 1]["worry_score"]
        lag_3 = np.mean([index_data[i - j]["worry_score"] for j in range(1, min(4, i + 1))])
        lag_7 = np.mean([index_data[i - j]["worry_score"] for j in range(1, min(8, i + 1))])

        # Trend (is worry rising or falling?)
        trend = lag_1 - lag_3

        # Volatility (how much has worry been swinging?)
        recent_scores = [index_data[i - j]["worry_score"] for j in range(1, min(8, i + 1))]
        volatility = np.std(recent_scores) if len(recent_scores) > 1 else 0.0

        # Post volume (more posts = more engagement = potentially more extreme sentiment)
        post_count = index_data[i - 1].get("post_count", 10)

        # Recent match form
        form_feats = _recent_form_features(match_data, date)

        # Most recent match impact
        recent_matches = [m for m in match_data if m["date"] <= date]
        if recent_matches:
            last_match = recent_matches[-1]
            match_impact = _match_result_score(last_match["arsenal_goals"], last_match["opponent_goals"])
            days_since = max(1, (len(index_data) - i))  # Rough proxy
        else:
            match_impact = 0.0
            days_since = 7

        features = [
            lag_1,
            lag_3,
            lag_7,
            trend,
            volatility,
            post_count,
            match_impact,
            *form_feats,
        ]

        X.append(features)
        y.append(row["worry_score"])

    return np.array(X), np.array(y)


def _ridge_fit(X, y, alpha=1.0):
    """Simple Ridge regression (no sklearn needed for inference).

    w = (X^T X + alpha I)^{-1} X^T y
    """
    n_features = X.shape[1]
    XtX = X.T @ X + alpha * np.eye(n_features)
    Xty = X.T @ y
    w = np.linalg.solve(XtX, Xty)
    return w


def build_forecast(days_ahead=7):
    """Build a worry forecast for the next N days.

    Returns:
        dict with forecast data, model metrics, and feature importances
    """
    index_data, match_data = _get_historical_data()

    if len(index_data) < 10:
        return {
            "forecast": [],
            "r_squared": 0.0,
            "error": "Not enough historical data (need 10+ days)",
        }

    X, y = _build_features(index_data, match_data)

    if len(X) < 5:
        return {
            "forecast": [],
            "r_squared": 0.0,
            "error": "Not enough features to train",
        }

    # Train/test split (last 20% as test)
    split = max(1, int(len(X) * 0.8))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Normalize features
    mu = X_train.mean(axis=0)
    sigma = X_train.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_train_norm = (X_train - mu) / sigma
    X_test_norm = (X_test - mu) / sigma

    # Add bias
    X_train_b = np.column_stack([np.ones(len(X_train_norm)), X_train_norm])
    X_test_b = np.column_stack([np.ones(len(X_test_norm)), X_test_norm])

    # Fit
    w = _ridge_fit(X_train_b, y_train, alpha=1.0)

    # Evaluate
    y_pred_test = X_test_b @ w
    ss_res = np.sum((y_test - y_pred_test) ** 2)
    ss_tot = np.sum((y_test - y_test.mean()) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    mae = np.mean(np.abs(y_test - y_pred_test))

    # Feature importance (absolute normalized weights, skip bias)
    feature_names = [
        "lag_1d", "lag_3d", "lag_7d", "trend", "volatility",
        "post_volume", "match_impact", "win_rate", "loss_rate",
        "draw_rate", "avg_goal_diff",
    ]
    importances = np.abs(w[1:])  # Skip bias
    importance_order = np.argsort(importances)[::-1]
    top_features = [
        {"name": feature_names[i], "importance": round(float(importances[i]), 3)}
        for i in importance_order[:5]
    ]

    # Generate forecast: iteratively predict the next day
    forecast_points = []
    last_date = index_data[-1]["date"]

    # Current features for prediction
    current_X = X[-1:].copy()

    for day in range(1, days_ahead + 1):
        current_norm = (current_X - mu) / sigma
        current_b = np.column_stack([np.ones(1), current_norm])
        pred = float(current_b @ w)
        pred = max(0, min(100, pred))  # Clamp to valid range

        forecast_points.append({
            "day_offset": day,
            "predicted_worry": round(pred, 1),
        })

        # Shift lag features for next prediction
        if current_X.shape[1] >= 3:
            current_X[0, 2] = current_X[0, 1]  # lag_7 <- lag_3
            current_X[0, 1] = current_X[0, 0]  # lag_3 <- lag_1
            current_X[0, 0] = pred              # lag_1 <- prediction

    return {
        "forecast": forecast_points,
        "r_squared": round(float(r_squared), 3),
        "mae": round(float(mae), 1),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "top_features": top_features,
        "last_date": last_date,
        "current_worry": round(float(y[-1]), 1),
    }

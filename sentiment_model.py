"""
Loads the trained sentiment classifier for inference.
Falls back to VADER if no trained model is available.
"""

import pickle
import ssl
from pathlib import Path

import nltk

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

nltk.download("vader_lexicon", quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer

MODEL_PATH = Path(__file__).parent / "models" / "sentiment_pipeline.pkl"

_pipeline = None
_sia = SentimentIntensityAnalyzer()

# Map 3-class prediction to compound-style score [-1, 1]
CLASS_TO_SCORE = {0: -0.6, 1: 0.0, 2: 0.6}


def _load_model():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if MODEL_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            _pipeline = pickle.load(f)
        return _pipeline
    return None


def score_sentiment(title):
    """Return a sentiment score for a post title.

    Uses the trained classifier if available, otherwise falls back to VADER.
    Returns a float in [-1, 1].
    """
    model = _load_model()
    if model is not None:
        # Get class probabilities for a smoother score
        probs = model.predict_proba([title])[0]
        # Weighted sum: negative=-1, neutral=0, positive=1
        score = probs[0] * (-1.0) + probs[1] * 0.0 + probs[2] * 1.0
        return round(score, 4)
    # Fallback to VADER
    return _sia.polarity_scores(title)["compound"]


def get_model_info():
    """Return info about which model is active."""
    model = _load_model()
    if model is not None:
        metrics_path = MODEL_PATH.parent / "metrics.json"
        metrics = {}
        if metrics_path.exists():
            import json
            with open(metrics_path) as f:
                metrics = json.load(f)
        return {
            "model": "TF-IDF + Logistic Regression",
            "status": "trained",
            **metrics,
        }
    return {
        "model": "VADER (fallback)",
        "status": "untrained",
    }

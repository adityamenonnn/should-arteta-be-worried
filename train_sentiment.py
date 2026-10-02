"""
Train a TF-IDF + Logistic Regression sentiment classifier on football Reddit posts.

Uses VADER labels as noisy supervision, then applies football-specific corrections
to teach the model domain patterns that VADER's general lexicon misses.

Usage:
    python train_sentiment.py

Saves the trained model to models/sentiment_pipeline.pkl
Prints evaluation metrics (F1, accuracy, classification report).
"""

import json
import pickle
import re
import ssl
from pathlib import Path

import nltk
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

nltk.download("vader_lexicon", quiet=True)
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from db import get_conn, init_db

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "sentiment_pipeline.pkl"

# Football-specific sentiment overrides.
# VADER doesn't understand football slang, so we manually correct these.
# Maps regex pattern -> sentiment class (0=negative, 1=neutral, 2=positive)
FOOTBALL_OVERRIDES = [
    # Strongly positive
    (r"\b(masterclass|world.?class|immense|brilliant|elite|unreal|incredible)\b", 2),
    (r"\btitle.?contenders?\b", 2),
    (r"\b(clean.?sheet|three points|massive (result|win))\b", 2),
    (r"\b(what a (player|signing|goal|keeper|win|performance))\b", 2),
    (r"\b(best .* in the (league|world|prem))\b", 2),
    (r"\b(buzzing|ecstatic|clinical|dominated)\b", 2),
    (r"\bback to his best\b", 2),
    (r"\bproud of this\b", 2),

    # Strongly negative
    (r"\b(bottled|bottle(d|r|rs)?)\b", 0),
    (r"\b(sitter(s)?|missing sitters)\b", 0),
    (r"\b(robbed|robbery|rigged)\b", 0),
    (r"\b(shocking|dreadful|abysmal|shambles|embarrassing)\b", 0),
    (r"\b(worst .* (all season|i.ve seen|ever))\b", 0),
    (r"\b(meltdown|full meltdown|slipping away)\b", 0),
    (r"\b(same (story|thing) every (year|season))\b", 0),
    (r"\bdesperate(ly)? need\b", 0),
    (r"\b(furious|fuming|disgraceful|joke of a)\b", 0),
    (r"\b(league.?two|championship level)\b", 0),
    (r"\bvar is\b", 0),
    (r"\bhow did the ref\b", 0),
    (r"\bgot (his|the) tactics.*(wrong|all wrong)\b", 0),

    # Neutral (match threads, discussion)
    (r"^(pre|post).?match thread", 1),
    (r"^(lineup|line.?up) announced", 1),
    (r"^daily discussion", 1),
    (r"^rival watch", 1),
    (r"^(press conference|presser)", 1),
    (r"^(player ratings|rating) thread", 1),
    (r"^(injury|team) update", 1),
]

sia = SentimentIntensityAnalyzer()


def vader_label(text):
    """Convert VADER compound score to 3-class label."""
    score = sia.polarity_scores(text)["compound"]
    if score > 0.05:
        return 2  # positive
    elif score < -0.05:
        return 0  # negative
    return 1  # neutral


def override_label(text, vader_class):
    """Apply football-specific overrides to correct VADER mistakes."""
    lower = text.lower()
    for pattern, label in FOOTBALL_OVERRIDES:
        if re.search(pattern, lower):
            return label
    return vader_class


def load_training_data():
    """Load posts from DB and generate labels."""
    init_db()
    conn = get_conn()
    rows = conn.execute("SELECT title, sentiment FROM posts").fetchall()
    conn.close()

    texts = []
    labels = []

    for row in rows:
        title = row["title"]
        # Get VADER's label
        v_label = vader_label(title)
        # Apply football corrections
        final_label = override_label(title, v_label)

        texts.append(title)
        labels.append(final_label)

    return texts, labels


def augment_data(texts, labels):
    """Add synthetic training examples for football-specific patterns."""
    augmented = [
        # Positive examples VADER might miss
        ("Saka masterclass today absolutely world class", 2),
        ("Three points and a clean sheet, perfect weekend", 2),
        ("What a signing, he's been immense since arriving", 2),
        ("We are genuine title contenders this year", 2),
        ("Best midfielder in the league no question", 2),
        ("Dominated from start to finish, clinical finishing", 2),
        ("The pressing was relentless, they couldn't handle us", 2),
        ("Incredible atmosphere at the Emirates tonight", 2),
        ("Back to his best after that injury, love to see it", 2),
        ("What a goal that was, take a bow", 2),
        ("Massive result, we go top of the table", 2),
        ("Unreal composure from the backline today", 2),

        # Negative examples VADER might miss
        ("We bottled it again typical Arsenal", 0),
        ("Havertz missing sitters every single game", 0),
        ("VAR is an absolute joke, clear penalty not given", 0),
        ("League Two defending from our centre backs today", 0),
        ("Same story every season, collapse when it matters", 0),
        ("Arteta got his tactics completely wrong today", 0),
        ("We desperately need a proper striker in January", 0),
        ("Season is slipping away and nobody seems to care", 0),
        ("Worst performance I have seen in years", 0),
        ("How did the ref not give that penalty absolute robbery", 0),
        ("Full meltdown mode on this sub and rightly so", 0),
        ("Shocking display from start to finish", 0),

        # Neutral examples
        ("Pre-match thread Arsenal vs Chelsea", 1),
        ("Post-match thread Arsenal 2-1 Wolves", 1),
        ("Lineup announced for tomorrow", 1),
        ("Press conference quotes from the manager", 1),
        ("Transfer rumour roundup January window", 1),
        ("Daily discussion thread", 1),
        ("Rival watch City vs Liverpool tonight", 1),
        ("Player ratings thread after the match", 1),
        ("Injury update Odegaard back in training", 1),
        ("What formation should we play this weekend", 1),
        ("Interesting stat comparison with last season", 1),
        ("Does anyone have a clip of that goal", 1),
    ]

    for text, label in augmented:
        texts.append(text)
        labels.append(label)

    return texts, labels


def train():
    """Train and evaluate the sentiment classifier."""
    print("Loading training data from database...")
    texts, labels = load_training_data()
    print(f"  {len(texts)} posts loaded from DB")

    texts, labels = augment_data(texts, labels)
    print(f"  {len(texts)} total samples after augmentation")

    # Class distribution
    labels_arr = np.array(labels)
    for cls, name in [(0, "negative"), (1, "neutral"), (2, "positive")]:
        print(f"  {name}: {(labels_arr == cls).sum()}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # Build pipeline
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        )),
    ])

    print("\nTraining TF-IDF + Logistic Regression...")
    pipeline.fit(X_train, y_train)

    # Evaluate
    y_pred = pipeline.predict(X_test)
    f1 = f1_score(y_test, y_pred, average="weighted")
    print(f"\nWeighted F1: {f1:.3f}")
    print("\nClassification Report:")
    print(classification_report(
        y_test, y_pred,
        target_names=["negative", "neutral", "positive"],
    ))

    # Compare with VADER on test set
    vader_preds = [vader_label(t) for t in X_test]
    vader_f1 = f1_score(y_test, vader_preds, average="weighted")
    print(f"VADER F1 on same test set: {vader_f1:.3f}")
    print(f"Improvement: +{(f1 - vader_f1) * 100:.1f}% F1")

    # Save model
    MODEL_DIR.mkdir(exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)
    print(f"\nModel saved to {MODEL_PATH}")

    # Save evaluation metrics
    metrics = {
        "model_f1": round(f1, 3),
        "vader_f1": round(vader_f1, 3),
        "improvement_pct": round((f1 - vader_f1) * 100, 1),
        "train_size": len(X_train),
        "test_size": len(X_test),
        "total_samples": len(texts),
    }
    with open(MODEL_DIR / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {MODEL_DIR / 'metrics.json'}")


if __name__ == "__main__":
    train()

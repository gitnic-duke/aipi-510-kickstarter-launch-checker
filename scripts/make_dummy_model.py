"""Build a placeholder model so the API can be built and deployed before the
real model exists (task T7). Replaced by the trained model in T15.

It is a real scikit-learn Pipeline that takes exactly the columns in
src/schema.py, so the API code path is identical to production. It is fit on
random synthetic rows, so its predictions mean nothing, except that smaller
goals score higher, which gives the front-end's what-if chart a visible slope.

Usage (from the repo root):
    python -m scripts.make_dummy_model               # writes models/model.joblib
    python -m scripts.make_dummy_model --out other.joblib
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.schema import CATEGORICAL, FEATURES, NUMERIC


def make_synthetic_data(n: int = 500, seed: int = 42) -> tuple[pd.DataFrame, np.ndarray]:
    """Random rows shaped like LaunchInput, plus a fake success label."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(
        {
            "main_category": rng.choice(["Games", "Music", "Technology", "Film & Video", "Art"], n),
            "category": rng.choice(
                ["Tabletop Games", "Indie Rock", "Gadgets", "Documentary", "Painting"], n
            ),
            "country": rng.choice(["US", "GB", "CA", "DE"], n),
            "goal_usd": rng.lognormal(mean=8.5, sigma=1.2, size=n),
            "duration_days": rng.integers(1, 61, n),
            "launch_month": rng.integers(1, 13, n),
            "launch_weekday": rng.integers(0, 7, n),
            "name": [f"Placeholder project {i}" for i in range(n)],
        }
    )[FEATURES]
    p_success = 1 / (1 + np.exp(np.log(X["goal_usd"]) - 8.5))
    y = rng.binomial(1, p_success)
    return X, y


def build_pipeline() -> Pipeline:
    """Preprocessing + model in one object, matching the shared-contract format."""
    preprocess = ColumnTransformer(
        [
            # handle_unknown="ignore": categories never seen in training don't crash it
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("numeric", StandardScaler(), NUMERIC),
        ]
        # TEXT columns (name) are dropped here; the real model may use them.
    )
    return Pipeline([("preprocess", preprocess), ("model", LogisticRegression(max_iter=1000))])


def build_and_save(out: Path, n: int = 500, seed: int = 42) -> Path:
    X, y = make_synthetic_data(n=n, seed=seed)
    pipeline = build_pipeline().fit(X, y)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("models/model.joblib"))
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    path = build_and_save(args.out, n=args.rows, seed=args.seed)
    print(f"Wrote placeholder model to {path}")


if __name__ == "__main__":
    main()

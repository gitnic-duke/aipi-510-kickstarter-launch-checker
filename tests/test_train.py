"""Tests for the training pipeline (tasks T11-T13).

Synthetic in-memory data only: no GCS, no W&B, so these run in CI.
"""

import numpy as np
import pandas as pd
import pytest

from scripts.make_dummy_model import make_synthetic_data
from src.features import build_pipeline, title_features
from src.schema import FEATURES, LEAKY, TARGET
from src.train import evaluate, feature_columns, split_data

SPLIT = {"test_size": 0.15, "val_size": 0.15, "stratify": True}


def synthetic_frame(n: int = 600) -> pd.DataFrame:
    X, y = make_synthetic_data(n=n, seed=0)
    df = X.copy()
    df[TARGET] = y
    df["backers"] = y * 100  # leaky: perfectly reveals the outcome
    df["pledged_usd"] = y * 1000.0
    return df


def test_split_sizes_and_no_overlap():
    df = synthetic_frame()
    splits = split_data(df, FEATURES, SPLIT, seed=42)
    sizes = {name: len(y) for name, (_, y) in splits.items()}
    assert sum(sizes.values()) == len(df)
    assert sizes["test"] == pytest.approx(0.15 * len(df), abs=2)
    assert sizes["val"] == pytest.approx(0.15 * len(df), abs=2)
    idx = [set(X.index) for X, _ in splits.values()]
    assert not (idx[0] & idx[1]) and not (idx[0] & idx[2]) and not (idx[1] & idx[2])


def test_split_is_reproducible():
    df = synthetic_frame()
    a = split_data(df, FEATURES, SPLIT, seed=42)
    b = split_data(df, FEATURES, SPLIT, seed=42)
    assert list(a["test"][0].index) == list(b["test"][0].index)


def test_leaky_columns_only_when_requested():
    assert not set(LEAKY) & set(feature_columns(False))
    assert set(LEAKY) <= set(feature_columns(True))


def test_title_features():
    out = title_features(pd.DataFrame({"name": ["Board Game 2", "Hi", None]}))
    assert out.tolist() == [[12, 3, 1], [2, 1, 0], [0, 0, 0]]


@pytest.mark.parametrize(
    "model_type,params",
    [
        ("logistic_regression", {"C": 1.0, "max_iter": 1000}),
        ("xgboost", {"n_estimators": 20, "max_depth": 3, "learning_rate": 0.1}),
    ],
)
def test_pipeline_trains_on_api_columns(model_type, params):
    df = synthetic_frame()
    splits = split_data(df, FEATURES, SPLIT, seed=42)
    model = build_pipeline(model_type, params, seed=42).fit(*splits["train"])
    X_test, y_test = splits["test"]
    proba = model.predict_proba(X_test[FEATURES])[:, 1]
    assert np.all((proba >= 0) & (proba <= 1))
    metrics = evaluate(model, X_test, y_test)
    assert set(metrics) >= {"roc_auc", "log_loss", "accuracy", "f1"}


def test_pipeline_ignores_unseen_categories():
    df = synthetic_frame()
    model = build_pipeline("logistic_regression", {"max_iter": 1000}, seed=42)
    model.fit(df[FEATURES], df[TARGET])
    row = df[FEATURES].head(1).copy()
    row["category"] = "Never Seen Before"
    assert 0 <= model.predict_proba(row)[0, 1] <= 1


def test_leakage_inflates_the_score():
    df = synthetic_frame()
    clean = split_data(df, feature_columns(False), SPLIT, seed=42)
    leaky = split_data(df, feature_columns(True), SPLIT, seed=42)
    params = {"max_iter": 1000}
    m_clean = build_pipeline("logistic_regression", params, 42).fit(*clean["train"])
    m_leaky = build_pipeline("logistic_regression", params, 42, include_leaky=True).fit(
        *leaky["train"]
    )
    assert (
        evaluate(m_leaky, *leaky["test"])["roc_auc"] > evaluate(m_clean, *clean["test"])["roc_auc"]
    )

"""Feature engineering inside the scikit-learn Pipeline (tasks T5/T11).

Everything the model needs is computed from the raw LaunchInput columns inside
the saved Pipeline, so training and serving can't diverge: the API passes the
same 8 columns and gets identical features.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.schema import CATEGORICAL, LEAKY

# Month and weekday are cyclical labels, not quantities, so they are one-hot encoded.
ONE_HOT = CATEGORICAL + ["launch_month", "launch_weekday"]
TITLE = ["name"]


def title_features(names: pd.DataFrame) -> np.ndarray:
    """Length, word count and 'has a digit' for each campaign title."""
    title = names.iloc[:, 0].fillna("").astype(str)
    return np.column_stack(
        [
            title.str.len(),
            title.str.split().str.len().fillna(0),
            title.str.contains(r"\d").astype(int),
        ]
    ).astype(float)


def build_preprocess(include_leaky: bool = False) -> ColumnTransformer:
    log_scaled = make_pipeline(FunctionTransformer(np.log1p), StandardScaler())
    steps = [
        # handle_unknown="ignore": a category never seen in training can't crash the API
        ("one_hot", OneHotEncoder(handle_unknown="ignore"), ONE_HOT),
        ("goal", log_scaled, ["goal_usd"]),  # goals are heavily skewed, so log them
        ("duration", StandardScaler(), ["duration_days"]),
        ("title", make_pipeline(FunctionTransformer(title_features), StandardScaler()), TITLE),
    ]
    if include_leaky:
        # Leakage demo only: post-launch columns that reveal the outcome.
        steps.append(
            ("leaky", make_pipeline(FunctionTransformer(np.log1p), StandardScaler()), LEAKY)
        )
    return ColumnTransformer(steps)


def build_model(model_type: str, params: dict, seed: int):
    if model_type == "logistic_regression":
        return LogisticRegression(random_state=seed, **params)
    if model_type == "xgboost":
        return XGBClassifier(
            random_state=seed, tree_method="hist", eval_metric="logloss", n_jobs=-1, **params
        )
    raise ValueError(f"Unknown model.type {model_type!r}; use logistic_regression or xgboost")


def build_pipeline(model_type: str, params: dict, seed: int, include_leaky: bool = False):
    """One object (features + model) that is saved with joblib and served by the API."""
    return Pipeline(
        [
            ("preprocess", build_preprocess(include_leaky)),
            ("model", build_model(model_type, params, seed)),
        ]
    )

"""Training entry point (tasks T11-T13).

Reads config.yaml, loads the versioned processed data (src/data/ingest.py),
makes a stratified train/validation/test split, trains the configured model,
evaluates it, and logs everything to Weights & Biases: config, data version,
git commit, metrics, ROC curve, confusion matrix and the model artifact.

Usage (from the repo root, after `wandb login`):
    python -m src.train                  # train with config.yaml
    python -m src.train --promote        # also mark this model as `production`
    python -m src.train --no-wandb       # quick local run without logging

Experiments are changed in config.yaml only (model.type, features.include_leaky),
never in code.
"""

import argparse
import logging
import subprocess
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from src.config import load_config
from src.features import build_pipeline
from src.schema import FEATURES, LEAKY, TARGET

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("train")

MODEL_DIR = Path("models")
ARTIFACT_NAME = "kickstarter-model"


def feature_columns(include_leaky: bool) -> list[str]:
    return FEATURES + LEAKY if include_leaky else list(FEATURES)


def split_data(df: pd.DataFrame, columns: list[str], cfg: dict, seed: int):
    """Stratified train/validation/test split. Sizes are fractions of ALL rows."""
    test_size, val_size = cfg["test_size"], cfg["val_size"]
    stratify = df[TARGET] if cfg.get("stratify", True) else None
    rest, test = train_test_split(df, test_size=test_size, random_state=seed, stratify=stratify)
    # val_size is a share of all rows, so rescale it to a share of what's left.
    val_share = val_size / (1 - test_size)
    stratify_rest = rest[TARGET] if cfg.get("stratify", True) else None
    train, val = train_test_split(
        rest, test_size=val_share, random_state=seed, stratify=stratify_rest
    )
    return {
        name: (part[columns], part[TARGET])
        for name, part in [("train", train), ("val", val), ("test", test)]
    }


def evaluate(model, X: pd.DataFrame, y: pd.Series) -> dict:
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {
        "roc_auc": roc_auc_score(y, proba),
        "log_loss": log_loss(y, proba),
        "brier": brier_score_loss(y, proba),
        "accuracy": accuracy_score(y, pred),
        "precision": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and log a model.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument(
        "--promote", action="store_true", help="Add the `production` alias to this model in W&B"
    )
    parser.add_argument("--no-wandb", action="store_true", help="Skip W&B logging")
    args = parser.parse_args()

    cfg = load_config(args.config)
    seed = cfg["seed"]
    model_type = cfg["model"]["type"]
    params = cfg["model"]["params"][model_type]
    include_leaky = cfg["features"]["include_leaky"]
    if args.promote and include_leaky:
        raise SystemExit("Refusing to promote a leaky model: it can never be served.")

    from src.data.ingest import load_meta, load_processed

    df = load_processed(cfg)
    meta = load_meta(cfg)
    columns = feature_columns(include_leaky)
    splits = split_data(df, columns, cfg["split"], seed)
    logger.info("Rows: train %d, val %d, test %d", *(len(splits[s][1]) for s in splits))

    pipeline = build_pipeline(model_type, params, seed, include_leaky)
    X_train, y_train = splits["train"]
    logger.info("Training %s (include_leaky=%s)...", model_type, include_leaky)
    pipeline.fit(X_train, y_train)

    metrics = {}
    for name in ("train", "val", "test"):
        for metric, value in evaluate(pipeline, *splits[name]).items():
            metrics[f"{name}/{metric}"] = value
    logger.info(
        "val ROC-AUC %.4f | test ROC-AUC %.4f", metrics["val/roc_auc"], metrics["test/roc_auc"]
    )

    MODEL_DIR.mkdir(exist_ok=True)
    # The leaky model gets its own file so it can never be deployed by accident.
    model_path = MODEL_DIR / ("model-leaky.joblib" if include_leaky else "model.joblib")
    joblib.dump(pipeline, model_path)
    logger.info("Saved model to %s", model_path)

    if args.no_wandb:
        return

    import wandb

    tags = [model_type, "leaky" if include_leaky else "clean"]
    run = wandb.init(
        project=cfg["tracking"]["project"],
        entity=cfg["tracking"].get("entity"),
        job_type="train",
        tags=tags,
        config={**cfg, "data_meta": meta, "git_commit": git_commit(), "features": columns},
    )
    run.log(metrics)
    run.summary.update(metrics)

    X_test, y_test = splits["test"]
    proba = pipeline.predict_proba(X_test)
    run.log(
        {
            "test/roc_curve": wandb.plot.roc_curve(
                y_test.to_numpy(), proba, labels=["failed", "successful"]
            ),
            "test/confusion_matrix": wandb.plot.confusion_matrix(
                y_true=y_test.to_numpy(),
                preds=(proba[:, 1] >= 0.5).astype(int),
                class_names=["failed", "successful"],
            ),
        }
    )

    artifact = wandb.Artifact(
        ARTIFACT_NAME,
        type="model",
        description=f"{model_type} Pipeline (leaky={include_leaky})",
        metadata={
            "model_type": model_type,
            "include_leaky": include_leaky,
            "data_version": cfg["data"]["processed_version"],
            "git_commit": git_commit(),
            "test_roc_auc": metrics["test/roc_auc"],
        },
    )
    artifact.add_file(str(model_path), name="model.joblib")
    aliases = ["latest", "leaky-do-not-deploy"] if include_leaky else ["latest"]
    if args.promote:
        aliases.append("production")
    run.log_artifact(artifact, aliases=aliases)
    logger.info("Logged %s to W&B with aliases %s", ARTIFACT_NAME, aliases)
    run.finish()


if __name__ == "__main__":
    main()

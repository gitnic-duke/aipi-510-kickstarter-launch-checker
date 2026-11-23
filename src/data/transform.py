"""Transform + validate (task T5).

Reads the raw CSV from gs://<bucket>/raw/, keeps successful/failed campaigns,
builds launch-day features, runs data quality checks, and writes to
gs://<bucket>/processed/<version>/:
  - kickstarter.parquet   features + target + leaky columns (see below)
  - _meta.json            row counts, success rate, source, timestamp
  - category_values.json  valid categorical values for the front-end dropdowns

Leaky post-launch columns (backers, pledged_usd) are KEPT here on purpose:
training drops them unless config `features.include_leaky: true`, which is what
makes the leakage demo run possible. They are never part of the served model.

A change to cleaning logic = a new version folder (bump data.processed_version);
an existing version is never overwritten.

The cleaning and validation functions are pure (DataFrame in, DataFrame out) so
they can be tested without any cloud access.

Usage (from the repo root, after `gcloud auth application-default login`):
    python -m src.data.transform
"""

import argparse
import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.config import load_config
from src.data import gcs
from src.schema import CATEGORICAL, CATEGORY_VALUES_FILE, FEATURES, LEAKY, TARGET

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("transform")

RAW_COLUMNS = [
    "name",
    "category",
    "main_category",
    "deadline",
    "launched",
    "state",
    "backers",
    "country",
    "usd_pledged_real",
    "usd_goal_real",
]
KEEP_STATES = {"successful", "failed"}
OUTPUT_COLUMNS = FEATURES + LEAKY + [TARGET]
FIRST_VALID_YEAR = 2009  # Kickstarter launched in 2009; earlier dates are placeholders (1970)


class DataQualityError(ValueError):
    """Raised when the processed data fails a quality check."""


def read_raw_csv(path: str | Path) -> pd.DataFrame:
    """Read the Kaggle CSV, trying UTF-8 first and falling back to Latin-1."""
    try:
        return pd.read_csv(path, encoding="utf-8", low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", low_memory=False)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn raw Kaggle rows into model-ready rows (pure function)."""
    raw.columns = raw.columns.str.strip()
    missing = set(RAW_COLUMNS) - set(raw.columns)
    if missing:
        raise DataQualityError(f"Raw data is missing columns: {sorted(missing)}")

    df = raw[RAW_COLUMNS].copy()

    # Only finished campaigns with a clear outcome (drops canceled, live, suspended, undefined).
    df = df[df["state"].isin(KEEP_STATES)]

    launched = pd.to_datetime(df["launched"], errors="coerce")
    deadline = pd.to_datetime(df["deadline"], errors="coerce")
    df = df.assign(
        name=df["name"].astype("string").str.strip(),
        goal_usd=pd.to_numeric(df["usd_goal_real"], errors="coerce"),
        pledged_usd=pd.to_numeric(df["usd_pledged_real"], errors="coerce"),
        backers=pd.to_numeric(df["backers"], errors="coerce"),
        duration_days=(deadline - launched.dt.normalize()).dt.days,
        launch_month=launched.dt.month,
        launch_weekday=launched.dt.day_of_week,  # 0 = Monday
        launch_year=launched.dt.year,
        success=(df["state"] == "successful").astype(int),
    )

    valid = (
        df["launch_year"].ge(FIRST_VALID_YEAR)
        & df["country"].astype("string").str.fullmatch(r"[A-Z]{2}").fillna(False).astype(bool)
        & df["name"].notna()
        & df["name"].str.len().gt(0)
        & df["goal_usd"].gt(0)
        & df["duration_days"].between(1, 92)
    )
    dropped = int((~valid).sum())
    if dropped:
        logger.info("Dropping %d rows with invalid dates, country, name, goal or duration", dropped)
    df = df[valid]

    df = df.astype(
        {
            "duration_days": "int64",
            "launch_month": "int64",
            "launch_weekday": "int64",
            "backers": "int64",
        }
    )
    return df[OUTPUT_COLUMNS].reset_index(drop=True)


def validate(df: pd.DataFrame, min_rows: int = 1) -> None:
    """Data quality checks. Raises DataQualityError listing every failed check."""
    problems = []

    if list(df.columns) != OUTPUT_COLUMNS:
        problems.append(f"Columns {list(df.columns)} != expected {OUTPUT_COLUMNS}")
    if len(df) < min_rows:
        problems.append(f"Only {len(df)} rows; expected at least {min_rows}")

    present = [c for c in OUTPUT_COLUMNS if c in df.columns]
    nulls = df[present].isna().sum()
    if nulls.any():
        problems.append(f"Null values: {nulls[nulls > 0].to_dict()}")

    range_checks = {
        "goal_usd": df.get("goal_usd", pd.Series(dtype=float)).gt(0),
        "duration_days": df.get("duration_days", pd.Series(dtype=float)).between(1, 92),
        "launch_month": df.get("launch_month", pd.Series(dtype=float)).between(1, 12),
        "launch_weekday": df.get("launch_weekday", pd.Series(dtype=float)).between(0, 6),
        TARGET: df.get(TARGET, pd.Series(dtype=float)).isin([0, 1]),
        "backers": df.get("backers", pd.Series(dtype=float)).ge(0),
        "pledged_usd": df.get("pledged_usd", pd.Series(dtype=float)).ge(0),
    }
    for column, ok in range_checks.items():
        bad = int((~ok).sum())
        if bad:
            problems.append(f"{column}: {bad} rows out of range")

    if TARGET in df.columns and len(df) and df[TARGET].nunique() < 2:
        problems.append(f"{TARGET} has only one class")

    if problems:
        raise DataQualityError("Data quality checks failed:\n- " + "\n- ".join(problems))


def category_values(df: pd.DataFrame) -> dict:
    """Valid values of each categorical feature, for the front-end dropdowns."""
    values = {col: sorted(df[col].dropna().unique().tolist()) for col in CATEGORICAL}
    values["categories_by_main"] = {
        main: sorted(group["category"].unique().tolist())
        for main, group in df.groupby("main_category")
    }
    return values


def build_meta(df: pd.DataFrame, source: str, version: str) -> dict:
    return {
        "version": version,
        "source": source,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows": len(df),
        "columns": list(df.columns),
        "success_rate": round(float(df[TARGET].mean()), 4),
        "leaky_columns": LEAKY,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean, validate and publish processed data.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()

    cfg = load_config(args.config)["data"]
    version = cfg["processed_version"]
    prefix = f"processed/{version}"
    bucket = gcs.get_bucket(cfg["bucket"])

    parquet_blob = f"{prefix}/{cfg['processed_file']}"
    if gcs.blob_exists(bucket, parquet_blob):
        raise SystemExit(
            f"gs://{cfg['bucket']}/{parquet_blob} already exists. Versions are never "
            "overwritten: bump data.processed_version in config.yaml for new cleaning logic."
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw_file = gcs.download_file(bucket, cfg["raw_path"], tmp / "raw.csv")
        df = clean(read_raw_csv(raw_file))
        validate(df, min_rows=cfg.get("min_rows", 1))
        logger.info("Clean data: %d rows, success rate %.3f", len(df), df[TARGET].mean())

        local_parquet = tmp / cfg["processed_file"]
        df.to_parquet(local_parquet, index=False)
        source = f"gs://{cfg['bucket']}/{cfg['raw_path']}"

        # Parquet first, metadata after, so a half-finished run is easy to spot.
        logger.info("Wrote %s", gcs.upload_file(bucket, local_parquet, parquet_blob))
        meta = json.dumps(build_meta(df, source, version), indent=2)
        logger.info("Wrote %s", gcs.upload_text(bucket, meta, f"{prefix}/_meta.json"))
        values = json.dumps(category_values(df), indent=2)
        logger.info("Wrote %s", gcs.upload_text(bucket, values, f"{prefix}/{CATEGORY_VALUES_FILE}"))


if __name__ == "__main__":
    main()

"""Ingest (task T6): load processed/<version> from GCS for training.

The version comes from config.yaml (data.processed_version), so every training
run reads a fixed, versioned snapshot. Files are cached under
data/processed/<version>/ (gitignored); pass refresh=True to re-download.

Usage:
    from src.data.ingest import load_processed
    df = load_processed(load_config())
"""

import json
from pathlib import Path

import pandas as pd

from src.data import gcs
from src.schema import CATEGORY_VALUES_FILE

CACHE_DIR = Path("data/processed")


def _cached_download(cfg: dict, filename: str, refresh: bool = False) -> Path:
    version = cfg["data"]["processed_version"]
    local = CACHE_DIR / version / filename
    if refresh or not local.exists():
        bucket = gcs.get_bucket(cfg["data"]["bucket"])
        gcs.download_file(bucket, f"processed/{version}/{filename}", local)
    return local


def load_processed(cfg: dict, refresh: bool = False) -> pd.DataFrame:
    """Return the processed training data for the configured version."""
    return pd.read_parquet(_cached_download(cfg, cfg["data"]["processed_file"], refresh))


def load_meta(cfg: dict, refresh: bool = False) -> dict:
    """Return _meta.json for the configured version (logged with each training run)."""
    return json.loads(_cached_download(cfg, "_meta.json", refresh).read_text())


def load_category_values(cfg: dict, refresh: bool = False) -> dict:
    return json.loads(_cached_download(cfg, CATEGORY_VALUES_FILE, refresh).read_text())


if __name__ == "__main__":
    from src.config import load_config

    config = load_config()
    data = load_processed(config)
    print(f"Loaded {len(data)} rows, columns: {list(data.columns)}")
    print(f"Success rate: {data['success'].mean():.3f}")

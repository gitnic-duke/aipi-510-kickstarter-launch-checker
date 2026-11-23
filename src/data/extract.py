"""Extract (task T4): upload the raw Kaggle CSV, untouched, to gs://<bucket>/raw/.

The raw layer is never edited: if the file already exists in the bucket, this
script stops instead of overwriting it (use --force only to repair a bad upload).

Get the CSV first, either:
  - by hand: download ks-projects-201801.csv from
    https://www.kaggle.com/datasets/kemical/kickstarter-projects
  - or with the Kaggle API (needs ~/.kaggle/kaggle.json):
    kaggle datasets download -d kemical/kickstarter-projects -p data/raw --unzip

Usage (from the repo root, after `gcloud auth application-default login`):
    python -m src.data.extract --csv data/raw/ks-projects-201801.csv
"""

import argparse
import logging
from pathlib import Path

from src.config import load_config
from src.data import gcs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("extract")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload the raw Kaggle CSV to GCS.")
    parser.add_argument("--csv", type=Path, required=True, help="Path to ks-projects-201801.csv")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--force", action="store_true", help="Overwrite an existing raw file")
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}")

    cfg = load_config(args.config)["data"]
    bucket = gcs.get_bucket(cfg["bucket"])

    if gcs.blob_exists(bucket, cfg["raw_path"]) and not args.force:
        logger.info(
            "gs://%s/%s already exists; raw data is never overwritten.",
            cfg["bucket"],
            cfg["raw_path"],
        )
        return

    uri = gcs.upload_file(bucket, args.csv, cfg["raw_path"])
    logger.info("Uploaded %s (%.1f MB) to %s", args.csv, args.csv.stat().st_size / 1e6, uri)


if __name__ == "__main__":
    main()

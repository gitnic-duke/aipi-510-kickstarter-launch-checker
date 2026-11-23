"""Thin helpers around Google Cloud Storage.

Authentication uses Application Default Credentials
(`gcloud auth application-default login`), so no key files are needed.
The client is created lazily, so importing this module never needs credentials
(tests and CI import the data modules without any cloud access).
"""

from pathlib import Path

from google.cloud import storage


def get_bucket(bucket_name: str) -> storage.Bucket:
    return storage.Client().bucket(bucket_name)


def blob_exists(bucket: storage.Bucket, blob_path: str) -> bool:
    return bucket.blob(blob_path).exists()


def upload_file(bucket: storage.Bucket, local_path: str | Path, blob_path: str) -> str:
    bucket.blob(blob_path).upload_from_filename(str(local_path))
    return f"gs://{bucket.name}/{blob_path}"


def upload_text(bucket: storage.Bucket, text: str, blob_path: str) -> str:
    bucket.blob(blob_path).upload_from_string(text, content_type="application/json")
    return f"gs://{bucket.name}/{blob_path}"


def download_file(bucket: storage.Bucket, blob_path: str, local_path: str | Path) -> Path:
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    bucket.blob(blob_path).download_to_filename(str(local_path))
    return local_path

"""
GCS signal storage — read/write the live signal snapshot from Cloud Storage.

The bucket name is controlled by GCS_SIGNALS_BUCKET (default: alphaforgeai-signals).
The object key is always ``latest.json``.

On Cloud Run the default service account has objectAdmin on the bucket.
For local development, set GOOGLE_APPLICATION_CREDENTIALS or run
``gcloud auth application-default login``.
"""

import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME = "latest.json"


def _client_and_blob(bucket_name: str):
    """Return (storage.Client, Blob) lazily to avoid import cost at startup."""
    from google.cloud import storage  # type: ignore

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(_BLOB_NAME)
    return client, blob


def upload_snapshot(snapshot: dict, bucket_name: str = "alphaforgeai-signals") -> bool:
    """
    Persist *snapshot* to GCS as ``latest.json``.

    Returns True on success, False on any error (caller decides fallback).
    """
    try:
        _, blob = _client_and_blob(bucket_name)
        blob.upload_from_string(
            json.dumps(snapshot, indent=2),
            content_type="application/json",
        )
        log.info(
            "event=gcs_upload ok bucket=%s signal_count=%d",
            bucket_name,
            snapshot.get("signal_count", "?"),
        )
        return True
    except Exception as exc:
        log.error("event=gcs_upload_failed bucket=%s error=%s", bucket_name, exc)
        return False


def download_snapshot(bucket_name: str = "alphaforgeai-signals") -> Optional[dict]:
    """
    Read ``latest.json`` from GCS and return the parsed dict.

    Returns None if the object does not exist or any error occurs.
    """
    try:
        _, blob = _client_and_blob(bucket_name)
        if not blob.exists():
            log.warning("event=gcs_download_missing bucket=%s blob=%s", bucket_name, _BLOB_NAME)
            return None
        data = blob.download_as_text()
        snapshot = json.loads(data)
        log.info(
            "event=gcs_download ok bucket=%s signal_count=%d generated_at=%s",
            bucket_name,
            snapshot.get("signal_count", "?"),
            snapshot.get("generated_at", "unknown"),
        )
        return snapshot
    except Exception as exc:
        log.error("event=gcs_download_failed bucket=%s error=%s", bucket_name, exc)
        return None

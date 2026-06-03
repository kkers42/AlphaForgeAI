"""
GCS explainer storage — read/write the live explainer payload from Cloud Storage.

Bucket: GCS_EXPLAINERS_BUCKET (default: alphaforgeai-explainers)
Object: latest.json
"""

import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME = "latest.json"


def _client_and_blob(bucket_name: str):
    from google.cloud import storage  # type: ignore
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(_BLOB_NAME)
    return client, blob


def upload_explainers(payload: dict, bucket_name: str = "alphaforgeai-explainers") -> bool:
    try:
        _, blob = _client_and_blob(bucket_name)
        blob.upload_from_string(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        log.info(
            "event=explainers_upload ok bucket=%s total=%d",
            bucket_name,
            payload.get("summary", {}).get("total", "?"),
        )
        return True
    except Exception as exc:
        log.error("event=explainers_upload_failed bucket=%s error=%s", bucket_name, exc)
        return False


def download_explainers(bucket_name: str = "alphaforgeai-explainers") -> Optional[dict]:
    try:
        _, blob = _client_and_blob(bucket_name)
        if not blob.exists():
            log.warning("event=explainers_download_missing bucket=%s", bucket_name)
            return None
        data = blob.download_as_text()
        payload = json.loads(data)
        log.info(
            "event=explainers_download ok bucket=%s total=%d generated_at=%s",
            bucket_name,
            payload.get("summary", {}).get("total", "?"),
            payload.get("generated_at", "unknown"),
        )
        return payload
    except Exception as exc:
        log.error("event=explainers_download_failed bucket=%s error=%s", bucket_name, exc)
        return None

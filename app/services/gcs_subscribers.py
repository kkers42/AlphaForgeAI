"""
GCS subscriber storage — read/write email subscribers from Cloud Storage.

Bucket: GCS_SUBSCRIBERS_BUCKET (default: alphaforgeai-subscribers)
Object: subscribers.json
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME = "subscribers.json"
_EMAIL_RE  = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _client_and_blob(bucket_name: str):
    from google.cloud import storage  # type: ignore
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(_BLOB_NAME)
    return client, blob


def _load(bucket_name: str) -> list[dict]:
    try:
        _, blob = _client_and_blob(bucket_name)
        if not blob.exists():
            return []
        return json.loads(blob.download_as_text()).get("subscribers", [])
    except Exception as exc:
        log.error("event=subscribers_load_failed bucket=%s error=%s", bucket_name, exc)
        return []


def _save(subscribers: list[dict], bucket_name: str) -> bool:
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":       len(subscribers),
        "subscribers": subscribers,
    }
    try:
        _, blob = _client_and_blob(bucket_name)
        blob.upload_from_string(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        log.info("event=subscribers_saved bucket=%s total=%d", bucket_name, len(subscribers))
        return True
    except Exception as exc:
        log.error("event=subscribers_save_failed bucket=%s error=%s", bucket_name, exc)
        return False


def add_subscriber(email: str, bucket_name: str, source: str = "landing") -> tuple[bool, str]:
    """
    Add an email subscriber.
    Returns (success, message) where message is 'added' | 'duplicate' | 'invalid' | 'error'.
    """
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return False, "invalid"

    subscribers = _load(bucket_name)
    existing    = {s["email"] for s in subscribers}

    if email in existing:
        log.info("event=subscriber_duplicate email_hash=%s", hash(email))
        return True, "duplicate"

    subscribers.append({
        "email":      email,
        "source":     source,
        "subscribed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })

    ok = _save(subscribers, bucket_name)
    if ok:
        log.info("event=subscriber_added total=%d source=%s", len(subscribers), source)
        return True, "added"
    return False, "error"


def count_subscribers(bucket_name: str) -> Optional[int]:
    try:
        subscribers = _load(bucket_name)
        return len(subscribers)
    except Exception:
        return None

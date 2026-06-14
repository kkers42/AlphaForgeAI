"""
GCS whale alert storage — read/write whale transfer events from Cloud Storage.

Bucket: GCS_WHALE_ALERTS_BUCKET (default: alphaforgeai-whale-alerts)
Object: whale_alerts.json
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME = "whale_alerts.json"
_MAX_STORED = 500


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
        return json.loads(blob.download_as_text()).get("events", [])
    except Exception as exc:
        log.error("event=whale_alerts_load_failed bucket=%s error=%s", bucket_name, exc)
        return []


def _save(events: list[dict], bucket_name: str) -> bool:
    payload = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":  len(events),
        "events": events,
    }
    try:
        _, blob = _client_and_blob(bucket_name)
        blob.upload_from_string(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        log.info("event=whale_alerts_saved bucket=%s total=%d", bucket_name, len(events))
        return True
    except Exception as exc:
        log.error("event=whale_alerts_save_failed bucket=%s error=%s", bucket_name, exc)
        return False


def ingest_events(new_events: list[dict], bucket_name: str) -> tuple[int, int]:
    """
    Merge new events into stored events, deduplicating by transaction_hash.
    Returns (added_count, total_count).
    """
    existing = _load(bucket_name)
    seen_hashes = {e.get("transaction_hash") for e in existing if e.get("transaction_hash")}

    added = 0
    for ev in new_events:
        tx_hash = ev.get("transaction_hash", "")
        if tx_hash and tx_hash in seen_hashes:
            continue
        if tx_hash:
            seen_hashes.add(tx_hash)
        existing.append(ev)
        added += 1

    # Keep most recent _MAX_STORED events sorted by timestamp desc
    existing.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    if len(existing) > _MAX_STORED:
        existing = existing[:_MAX_STORED]

    _save(existing, bucket_name)
    return added, len(existing)


def get_events(bucket_name: str, limit: int = 50, asset: Optional[str] = None) -> list[dict]:
    events = _load(bucket_name)
    if asset:
        events = [e for e in events if e.get("symbol", "").upper() == asset.upper()]
    return events[:limit]

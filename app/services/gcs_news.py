"""
GCS news storage — read/write news articles from Cloud Storage.

Bucket: GCS_NEWS_BUCKET (default: alphaforgeai-news)
Objects:
  latest.json  — active feed, last _MAX_AGE_DAYS days, max _MAX_ARTICLES
  archive.json — append-only, every article ever ingested, never deleted
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME    = "latest.json"
_ARCHIVE_NAME = "archive.json"
_MAX_ARTICLES = 50          # max articles in the active feed
_MAX_AGE_DAYS = 7           # articles older than this move to archive only


def _client_and_blob(bucket_name: str, blob_name: str = _BLOB_NAME):
    from google.cloud import storage  # type: ignore
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(blob_name)
    return client, blob


def _split_articles(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split into (fresh, aged) based on _MAX_AGE_DAYS."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)
    fresh, aged = [], []
    for a in articles:
        pub = a.get("published_at", "")
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            (fresh if dt >= cutoff else aged).append(a)
        except (ValueError, AttributeError):
            fresh.append(a)  # keep in active feed if date unparseable
    return fresh, aged


def _merge_articles(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """Deduplicate by URL, merge, sort newest-first."""
    seen = {a["url"] for a in existing}
    additions = [item for item in new_items if item["url"] not in seen]
    merged = existing + additions
    merged.sort(key=lambda a: a.get("published_at", ""), reverse=True)
    return merged


def _archive_articles(aged: list[dict], bucket_name: str) -> None:
    """Append aged-out articles to archive.json — never deletes."""
    if not aged:
        return
    try:
        _, blob = _client_and_blob(bucket_name, _ARCHIVE_NAME)
        if blob.exists():
            existing = json.loads(blob.download_as_text()).get("articles", [])
        else:
            existing = []
        merged = _merge_articles(existing, aged)
        merged.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total":        len(merged),
            "articles":     merged,
        }
        blob.upload_from_string(json.dumps(payload, indent=2), content_type="application/json")
        log.info("event=news_archive ok bucket=%s archived=%d total=%d",
                 bucket_name, len(aged), len(merged))
    except Exception as exc:
        log.error("event=news_archive_failed bucket=%s error=%s", bucket_name, exc)


def download_payload(bucket_name: str, blob_name: str = _BLOB_NAME) -> Optional[dict]:
    try:
        _, blob = _client_and_blob(bucket_name, blob_name)
        if not blob.exists():
            log.warning("event=news_download_missing bucket=%s blob=%s", bucket_name, blob_name)
            return None
        data    = blob.download_as_text()
        payload = json.loads(data)
        log.info(
            "event=news_download ok bucket=%s blob=%s total=%d",
            bucket_name,
            blob_name,
            payload.get("total", "?"),
        )
        return payload
    except Exception as exc:
        log.error("event=news_download_failed bucket=%s error=%s", bucket_name, exc)
        return None


def _upload_latest(articles: list[dict], bucket_name: str) -> bool:
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":        len(articles),
        "articles":     articles,
    }
    try:
        _, blob = _client_and_blob(bucket_name, _BLOB_NAME)
        blob.upload_from_string(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        log.info("event=news_upload ok bucket=%s total=%d", bucket_name, len(articles))
        return True
    except Exception as exc:
        log.error("event=news_upload_failed bucket=%s error=%s", bucket_name, exc)
        return False


def ingest_articles(new_items: list[dict], bucket_name: str) -> tuple[int, int]:
    """Merge new items into storage.  Returns (added_count, total_count).

    Flow:
      1. Merge new items into existing active feed (dedup by URL).
      2. Split merged list into fresh (<= _MAX_AGE_DAYS) and aged (> _MAX_AGE_DAYS).
      3. Write fresh[:_MAX_ARTICLES] to latest.json (active feed).
      4. Append aged articles to archive.json (never deleted).
    """
    existing_payload = download_payload(bucket_name)
    existing         = existing_payload.get("articles", []) if existing_payload else []
    seen             = {a["url"] for a in existing}
    added_count      = sum(1 for item in new_items if item["url"] not in seen)

    merged           = _merge_articles(existing, new_items)
    fresh, aged      = _split_articles(merged)
    active           = fresh[:_MAX_ARTICLES]

    _upload_latest(active, bucket_name)
    _archive_articles(aged, bucket_name)   # append-only, nothing deleted

    return added_count, len(active)

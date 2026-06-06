"""
GCS news storage — read/write news articles from Cloud Storage.

Bucket: GCS_NEWS_BUCKET (default: alphaforgeai-news)
Object: latest.json
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME = "latest.json"
_MAX_ARTICLES = 50          # hard cap on stored articles
_MAX_AGE_DAYS = 7           # drop articles older than this


def _client_and_blob(bucket_name: str):
    from google.cloud import storage  # type: ignore
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(_BLOB_NAME)
    return client, blob


def _trim_articles(articles: list[dict]) -> list[dict]:
    """Drop articles older than _MAX_AGE_DAYS, then cap at _MAX_ARTICLES."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_AGE_DAYS)
    fresh = []
    for a in articles:
        pub = a.get("published_at", "")
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if dt >= cutoff:
                fresh.append(a)
        except (ValueError, AttributeError):
            fresh.append(a)  # keep if unparseable
    return fresh[:_MAX_ARTICLES]


def _merge_articles(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """Deduplicate by URL, merge, sort newest-first, trim by age and count."""
    seen = {a["url"] for a in existing}
    additions = [item for item in new_items if item["url"] not in seen]
    merged = existing + additions
    merged.sort(key=lambda a: a.get("published_at", ""), reverse=True)
    return _trim_articles(merged)


def download_payload(bucket_name: str) -> Optional[dict]:
    try:
        _, blob = _client_and_blob(bucket_name)
        if not blob.exists():
            log.warning("event=news_download_missing bucket=%s", bucket_name)
            return None
        data    = blob.download_as_text()
        payload = json.loads(data)
        log.info(
            "event=news_download ok bucket=%s total=%d",
            bucket_name,
            payload.get("total", "?"),
        )
        return payload
    except Exception as exc:
        log.error("event=news_download_failed bucket=%s error=%s", bucket_name, exc)
        return None


def _upload(articles: list[dict], bucket_name: str) -> bool:
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":        len(articles),
        "articles":     articles,
    }
    try:
        _, blob = _client_and_blob(bucket_name)
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
    """Merge new items into storage.  Returns (added_count, total_count)."""
    existing_payload = download_payload(bucket_name)
    existing         = existing_payload.get("articles", []) if existing_payload else []
    seen             = {a["url"] for a in existing}
    added_count      = sum(1 for item in new_items if item["url"] not in seen)
    merged           = _merge_articles(existing, new_items)
    _upload(merged, bucket_name)
    return added_count, len(merged)

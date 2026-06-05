"""
GCS blog storage — read/write blog posts from Cloud Storage.

Bucket: GCS_BLOG_BUCKET (default: alphaforgeai-blog)
Object: latest.json
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_BLOB_NAME  = "latest.json"
_MAX_POSTS  = 50


def _client_and_blob(bucket_name: str):
    from google.cloud import storage  # type: ignore
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob   = bucket.blob(_BLOB_NAME)
    return client, blob


def slugify(title: str, published_at: str) -> str:
    """Generate a slug from title + date: lowercase, spaces→hyphens, strip special chars."""
    base = title.lower()
    base = re.sub(r"[^\w\s-]", "", base)
    base = re.sub(r"[\s_]+", "-", base).strip("-")
    try:
        dt   = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        date = dt.strftime("%Y-%m-%d")
    except Exception:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{base}-{date}"


def _merge_posts(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """Deduplicate by slug, merge, sort newest-first, cap at _MAX_POSTS."""
    seen      = {p["slug"] for p in existing}
    additions = [item for item in new_items if item["slug"] not in seen]
    merged    = existing + additions
    merged.sort(key=lambda p: p.get("published_at", ""), reverse=True)
    return merged[:_MAX_POSTS]


def download_payload(bucket_name: str) -> Optional[dict]:
    try:
        _, blob = _client_and_blob(bucket_name)
        if not blob.exists():
            log.warning("event=blog_download_missing bucket=%s", bucket_name)
            return None
        data    = blob.download_as_text()
        payload = json.loads(data)
        log.info(
            "event=blog_download ok bucket=%s total=%d",
            bucket_name,
            payload.get("total", "?"),
        )
        return payload
    except Exception as exc:
        log.error("event=blog_download_failed bucket=%s error=%s", bucket_name, exc)
        return None


def _upload(posts: list[dict], bucket_name: str) -> bool:
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":        len(posts),
        "posts":        posts,
    }
    try:
        _, blob = _client_and_blob(bucket_name)
        blob.upload_from_string(
            json.dumps(payload, indent=2),
            content_type="application/json",
        )
        log.info("event=blog_upload ok bucket=%s total=%d", bucket_name, len(posts))
        return True
    except Exception as exc:
        log.error("event=blog_upload_failed bucket=%s error=%s", bucket_name, exc)
        return False


def ingest_posts(new_items: list[dict], bucket_name: str) -> tuple[int, int]:
    """Merge new posts into storage.  Returns (added_count, total_count)."""
    existing_payload = download_payload(bucket_name)
    existing         = existing_payload.get("posts", []) if existing_payload else []
    seen             = {p["slug"] for p in existing}
    added_count      = sum(1 for item in new_items if item["slug"] not in seen)
    merged           = _merge_posts(existing, new_items)
    _upload(merged, bucket_name)
    return added_count, len(merged)

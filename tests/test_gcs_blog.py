"""Tests for gcs_blog deduplication and merge logic, and blog route auth."""

import pytest
from unittest.mock import MagicMock, patch

from app.services.gcs_blog import _MAX_POSTS, _merge_posts, slugify


def _post(slug: str, published_at: str) -> dict:
    return {
        "slug":         slug,
        "title":        "Test Post",
        "published_at": published_at,
        "summary":      "Test summary.",
        "content":      "Test content.",
        "sources":      [],
        "assets":       ["BTC"],
        "tags":         ["daily-brief"],
        "author":       "AlphaForgeAI",
    }


# ── Unit: _merge_posts ────────────────────────────────────────────────────────

class TestMergePosts:
    def test_new_post_added(self):
        existing = [_post("post-a-2026-06-01", "2026-06-01T10:00:00Z")]
        new      = [_post("post-b-2026-06-02", "2026-06-02T10:00:00Z")]
        result   = _merge_posts(existing, new)
        assert len(result) == 2

    def test_duplicate_slug_not_added(self):
        existing = [_post("post-a-2026-06-01", "2026-06-01T10:00:00Z")]
        new      = [_post("post-a-2026-06-01", "2026-06-01T11:00:00Z")]
        result   = _merge_posts(existing, new)
        assert len(result) == 1

    def test_sorted_newest_first(self):
        existing = [_post("old-2026-06-01", "2026-06-01T08:00:00Z")]
        new      = [_post("new-2026-06-02", "2026-06-02T12:00:00Z")]
        result   = _merge_posts(existing, new)
        assert result[0]["slug"] == "new-2026-06-02"

    def test_capped_at_max_posts(self):
        existing = [_post(f"post-{i}-2026-01-01", "2026-01-01T00:00:00Z") for i in range(_MAX_POSTS)]
        new      = [_post("newest-2026-06-02", "2026-06-02T12:00:00Z")]
        result   = _merge_posts(existing, new)
        assert len(result) == _MAX_POSTS

    def test_newest_survives_cap(self):
        existing = [_post(f"post-{i}-2026-01-01", "2026-01-01T00:00:00Z") for i in range(_MAX_POSTS)]
        new      = [_post("newest-2026-06-02", "2026-06-02T12:00:00Z")]
        result   = _merge_posts(existing, new)
        assert result[0]["slug"] == "newest-2026-06-02"

    def test_empty_existing(self):
        new    = [_post("post-a-2026-06-01", "2026-06-01T10:00:00Z")]
        result = _merge_posts([], new)
        assert len(result) == 1

    def test_empty_new(self):
        existing = [_post("post-a-2026-06-01", "2026-06-01T10:00:00Z")]
        result   = _merge_posts(existing, [])
        assert len(result) == 1

    def test_both_empty(self):
        assert _merge_posts([], []) == []

    def test_mixed_dup_and_new(self):
        existing = [_post("post-a-2026-06-01", "2026-06-01T10:00:00Z")]
        new = [
            _post("post-a-2026-06-01", "2026-06-01T10:00:00Z"),  # duplicate
            _post("post-b-2026-06-02", "2026-06-02T11:00:00Z"),  # new
        ]
        result = _merge_posts(existing, new)
        assert len(result) == 2
        slugs = {p["slug"] for p in result}
        assert "post-a-2026-06-01" in slugs
        assert "post-b-2026-06-02" in slugs


# ── Unit: slugify ─────────────────────────────────────────────────────────────

class TestSlugify:
    def test_basic_title(self):
        slug = slugify("Crypto Daily Brief", "2026-06-06T00:00:00Z")
        assert slug == "crypto-daily-brief-2026-06-06"

    def test_special_chars_stripped(self):
        slug = slugify("BTC/ETH: What's Next?", "2026-06-06T00:00:00Z")
        assert "?" not in slug
        assert "/" not in slug
        assert ":" not in slug

    def test_date_appended(self):
        slug = slugify("My Post", "2026-06-15T00:00:00Z")
        assert slug.endswith("-2026-06-15")


# ── Integration: route auth (mocked GCS) ─────────────────────────────────────

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

_VALID_POST = {
    "slug":         "test-post-2026-06-01",
    "title":        "Test Post",
    "published_at": "2026-06-01T10:00:00Z",
    "summary":      "A test summary.",
    "content":      "Test content body.",
    "sources":      ["https://example.com"],
    "assets":       ["BTC"],
    "tags":         ["test"],
    "author":       "AlphaForgeAI",
}


class TestBlogRouteAuth:
    def test_missing_api_key_returns_401_or_503(self):
        # No key configured → 503; wrong key → 401
        resp = client.post(
            "/api/blog/ingest",
            json={"schema_version": 1, "posts": [_VALID_POST]},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code in (401, 503)

    def test_valid_key_accepted(self):
        with patch("app.core.config.settings.blog_ingest_api_key", "test-secret-key"), \
             patch("app.services.gcs_blog.ingest_posts", return_value=(1, 1)):
            resp = client.post(
                "/api/blog/ingest",
                json={"schema_version": 1, "posts": [_VALID_POST]},
                headers={"Authorization": "Bearer test-secret-key"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] is True

    def test_invalid_slug_returns_404(self):
        with patch("app.services.gcs_blog.download_payload", return_value={"posts": [], "total": 0, "generated_at": None}):
            resp = client.get("/blog/nonexistent-slug-2099-01-01")
        assert resp.status_code == 404

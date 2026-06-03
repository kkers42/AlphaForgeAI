"""Tests for gcs_news deduplication and merge logic."""

import pytest

from app.services.gcs_news import _MAX_ARTICLES, _merge_articles


def _article(url: str, published_at: str) -> dict:
    return {
        "title":        "Test Article",
        "source":       "TestSource",
        "url":          url,
        "published_at": published_at,
        "category":     "bitcoin",
        "assets":       ["BTC"],
        "sentiment":    "neutral",
        "summary":      "Test summary.",
    }


class TestMergeArticles:
    def test_new_article_added(self):
        existing = [_article("https://example.com/1", "2026-05-25T10:00:00Z")]
        new      = [_article("https://example.com/2", "2026-05-25T11:00:00Z")]
        result   = _merge_articles(existing, new)
        assert len(result) == 2

    def test_duplicate_url_not_added(self):
        existing = [_article("https://example.com/1", "2026-05-25T10:00:00Z")]
        new      = [_article("https://example.com/1", "2026-05-25T11:00:00Z")]
        result   = _merge_articles(existing, new)
        assert len(result) == 1

    def test_sorted_newest_first(self):
        existing = [_article("https://example.com/old", "2026-05-25T08:00:00Z")]
        new      = [_article("https://example.com/new", "2026-05-25T12:00:00Z")]
        result   = _merge_articles(existing, new)
        assert result[0]["url"] == "https://example.com/new"

    def test_capped_at_max_articles(self):
        existing = [_article(f"https://example.com/{i}", "2026-01-01T00:00:00Z") for i in range(_MAX_ARTICLES)]
        new      = [_article("https://example.com/newest", "2026-05-25T12:00:00Z")]
        result   = _merge_articles(existing, new)
        assert len(result) == _MAX_ARTICLES

    def test_newest_survives_cap(self):
        existing = [_article(f"https://example.com/{i}", "2026-01-01T00:00:00Z") for i in range(_MAX_ARTICLES)]
        new      = [_article("https://example.com/newest", "2026-05-25T12:00:00Z")]
        result   = _merge_articles(existing, new)
        assert result[0]["url"] == "https://example.com/newest"

    def test_empty_existing(self):
        new    = [_article("https://example.com/1", "2026-05-25T10:00:00Z")]
        result = _merge_articles([], new)
        assert len(result) == 1

    def test_empty_new(self):
        existing = [_article("https://example.com/1", "2026-05-25T10:00:00Z")]
        result   = _merge_articles(existing, [])
        assert len(result) == 1

    def test_both_empty(self):
        assert _merge_articles([], []) == []

    def test_mixed_dup_and_new(self):
        existing = [_article("https://example.com/1", "2026-05-25T10:00:00Z")]
        new = [
            _article("https://example.com/1", "2026-05-25T10:00:00Z"),  # duplicate
            _article("https://example.com/2", "2026-05-25T11:00:00Z"),  # new
        ]
        result = _merge_articles(existing, new)
        assert len(result) == 2
        urls = {a["url"] for a in result}
        assert "https://example.com/1" in urls
        assert "https://example.com/2" in urls

    def test_multiple_new_articles(self):
        new = [
            _article("https://example.com/1", "2026-05-25T10:00:00Z"),
            _article("https://example.com/2", "2026-05-25T11:00:00Z"),
            _article("https://example.com/3", "2026-05-25T09:00:00Z"),
        ]
        result = _merge_articles([], new)
        assert len(result) == 3
        assert result[0]["url"] == "https://example.com/2"
        assert result[2]["url"] == "https://example.com/3"

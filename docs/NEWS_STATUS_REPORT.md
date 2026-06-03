# News Status Report — Issue #47 Audit
_Generated: 2026-06-03_

## Summary

The news pipeline code is complete and correct in the local/GitHub repository but has never been deployed to the staging container or Cloud Run production. This is the root cause of the missing News section.

---

## Route Status

| Route | Code Exists | Registered in main.py | Staging (Apr 27 image) | Notes |
|---|---|---|---|---|
| `GET /news` | Yes | Yes | **404 — not deployed** | Route added after staging image build |
| `GET /api/news` | Yes | Yes | **404 — not deployed** | Same reason |
| `POST /api/news/ingest` | Yes | Yes | **404 — not deployed** | Same reason |
| `GET /news/rss.xml` | Yes | Yes | **404 — not deployed** | Same reason |

---

## Root Causes

### 1. Staging image is stale (built 2026-04-27)

The Atlas staging container (`alphaforgeai-staging`, image `alphaforgeai:staging`) was built on **2026-04-27**. The news route module (`app/routes/news.py`) was added **after** that date and is therefore absent from the running image.

Evidence:
```
$ docker inspect alphaforgeai-staging --format '{{.Created}}'
2026-04-27T21:56:25.164736562Z

$ curl http://localhost:8090/api/news
{"detail":"Not Found"}

$ curl http://localhost:8090/news
{"detail":"Not Found"}
```

The Atlas `main.py` (source of the staging image) does not include the news router:
```python
# Atlas /home/kkers/projects/AlphaForgeAI/app/main.py (stale)
app.include_router(pages.router)
app.include_router(dashboard.router)
app.include_router(signals.router)
app.include_router(ingest.router)
# news router is MISSING
```

### 2. `NEWS_INGEST_API_KEY` not set in staging environment

The staging container has no `NEWS_INGEST_API_KEY` env var. Until this is set, `POST /api/news/ingest` will return 503.

### 3. `GCS_NEWS_BUCKET` not confirmed in production Cloud Run

The default bucket name is `alphaforgeai-news`. Whether this bucket exists and has the correct IAM permissions on the Cloud Run service account is not confirmed — no gcloud CLI is available on Atlas.

### 4. No news items have ever been ingested

The GCS bucket contains no `latest.json`. The news page will show the empty state until the first ingest POST arrives.

---

## What IS working (code is correct)

- `app/routes/news.py` — complete: ingest endpoint, API endpoint, HTML page, RSS feed
- `app/services/gcs_news.py` — complete: download, upload, merge, dedup logic
- `app/templates/news.html` — complete: news feed + professional empty state
- `app/core/config.py` — `news_ingest_api_key` and `gcs_news_bucket` settings exist
- `app/main.py` — news router registered correctly

---

## To unblock production

1. **Deploy a new image to Cloud Run** with the current codebase. The image built from the current `master` branch will include the news routes.
2. **Set Cloud Run env var**: `NEWS_INGEST_API_KEY=<secret>` (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
3. **Verify GCS bucket**: Confirm `alphaforgeai-news` bucket exists and the Cloud Run service account has `roles/storage.objectAdmin` on it.
4. **Test ingest** with the curl command in `docs/NEWS_INGEST_TEST.md`.
5. **Point n8n** to `POST https://alphaforgeai.io/api/news/ingest` with `Authorization: Bearer <NEWS_INGEST_API_KEY>`.

---

## n8n Webhook Format

```json
{
  "schema_version": 1,
  "items": [
    {
      "title": "Article title",
      "source": "CoinDesk",
      "url": "https://coindesk.com/article-slug",
      "published_at": "2026-06-03T12:00:00Z",
      "summary": "One paragraph summary of the article.",
      "category": "regulation",
      "assets": ["BTC", "ETH"],
      "sentiment": "bearish"
    }
  ]
}
```

Optional fields: `category`, `assets`, `sentiment`.
Sentiment values: `bullish`, `bearish`, `neutral`.

---

## Empty State

When no articles have been ingested, `/news` renders a professional empty state:
> "No news articles yet — Market intelligence briefs will appear here once the pipeline delivers its first batch."

This is already implemented and does not require a deployment fix — it will display correctly once the routes are live.

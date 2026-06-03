# News Ingest — Manual curl Test
_Reference doc for Issue #47 / POST /api/news/ingest_

## Prerequisites

- Cloud Run deployment is current (includes news routes)
- `NEWS_INGEST_API_KEY` is set as a Cloud Run secret/env var
- You have the key value

---

## Test: ingest a sample article

```bash
NEWS_API_KEY="<your-NEWS_INGEST_API_KEY>"
BASE_URL="https://alphaforgeai.io"  # or http://localhost:8090 for staging

curl -s -X POST "$BASE_URL/api/news/ingest" \
  -H "Authorization: Bearer $NEWS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": 1,
    "items": [
      {
        "title": "Test: Bitcoin holds above $60k ahead of ETF inflows",
        "source": "AlphaForgeAI Test",
        "url": "https://alphaforgeai.io/test-article-001",
        "published_at": "2026-06-03T12:00:00Z",
        "summary": "This is a test article to verify the news ingest pipeline is working correctly. It should appear on the /news page after this request succeeds.",
        "category": "market",
        "assets": ["BTC"],
        "sentiment": "bullish"
      }
    ]
  }'
```

### Expected success response

```json
{"accepted": true, "received": 1, "added": 1, "total": 1}
```

---

## Test: verify article appears in API

```bash
curl -s "$BASE_URL/api/news" | python3 -m json.tool | head -40
```

Expected: JSON with `articles` array containing the test article.

---

## Test: verify /news page renders the article

Open `$BASE_URL/news` in a browser. The test article should appear as a card.

---

## Test: verify RSS feed

```bash
curl -s "$BASE_URL/news/rss.xml" | head -40
```

Expected: valid RSS 2.0 XML with a `<item>` for the test article.

---

## Error responses

| Status | Reason |
|---|---|
| 401 | Wrong API key |
| 503 | `NEWS_INGEST_API_KEY` not set in Cloud Run |
| 422 | Missing required fields (title, source, url, published_at, summary) or schema_version != 1 |
| 400 | Body is not valid JSON |

---

## n8n HTTP Request node configuration

- **Method**: POST
- **URL**: `https://alphaforgeai.io/api/news/ingest`
- **Authentication**: Header Auth
  - Header name: `Authorization`
  - Header value: `Bearer <NEWS_INGEST_API_KEY>`
- **Body**: JSON — see schema above (`schema_version: 1`, `items: [...]`)

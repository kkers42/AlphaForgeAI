# Forge News Automation Pipeline

## Overview

Automated crypto market news ingestion, enrichment, and distribution pipeline. Runs hands-off every 4 hours with no manual intervention required.

## Architecture

```
8 RSS Feeds → Merge → Dedup/Filter → OpenAI Enrich → Filter (score≥4) → /api/news/ingest
                                                                                    ↓
                                                                            GCS (alphaforgeai-news)
                                                                                    ↓
                                                                         /news page (live)
                                                                                    ↓ (30min later)
                                                             Forge News X Publisher → @ALphaForgeAIio
```

## Components

### 1. News Ingest Workflow (`n8n/alphaforgeai_news_ingest.json`)

**Schedule:** 08:00, 12:00, 17:00, 21:00 ET daily

**Sources:**
- CoinDesk RSS
- Cointelegraph RSS
- The Block RSS
- Decrypt RSS
- Bitcoin Magazine RSS
- Coinbase Blog RSS
- Binance Blog RSS
- Kraken Blog RSS

**Processing:**
1. Merge all feeds
2. Deduplicate by URL, filter to last 48h, max 20 articles
3. Block generic roundup/brief articles via title blocklist
4. Enrich each article via OpenAI GPT-4o-mini:
   - `relevance_score` (1–10)
   - `summary` (2–3 sentence market-focused summary)
   - `category` (market, regulation, technology, defi, nft, other)
   - `assets` (e.g. ["BTC", "ETH"])
   - `sentiment` (bullish | bearish | neutral)
5. Filter: only articles with `relevance_score >= 4` proceed
6. POST batch to `https://alphaforgeai.io/api/news/ingest` (Bearer token auth)

**n8n Workflow ID:** `3KNcAiuXdeJmxx66`

### 2. Forge News X Publisher (`n8n/alphaforgeai_forge_news_x.json`)

**Schedule:** 08:30, 12:30, 17:30, 21:30 ET daily (30min after ingest)

**Logic:**
1. Fetch `/api/news` JSON from alphaforgeai.io
2. Filter articles: `relevance_score >= 7` AND `published_at` within last 4h
3. Pick highest-scoring article
4. Format tweet (≤280 chars): sentiment emoji + title + summary snippet + URL + asset tags + #crypto #AlphaForgeAI
5. Post to @ALphaForgeAIio via n8n Twitter node (credential: X (Twitter) OAuth1)

**Sentiment Emoji Mapping:**
- Bullish → 📈
- Bearish → 📉
- Neutral → ⚪

### 3. Breaking News Blog Trigger (`n8n/alphaforgeai_breaking_news.json`)

**Schedule:** Every 30 minutes

**Logic:** Monitors for articles with `relevance_score >= 8` within last 4h. If found and no breaking blog post in last 3h, triggers Claude to write a 350–500 word breaking news post and publishes to `/blog`.

## API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `POST /api/news/ingest` | Bearer `NEWS_INGEST_API_KEY` | Batch ingest articles from n8n |
| `GET /api/news` | None | JSON feed of current articles |
| `GET /news` | None | Rendered news page |
| `GET /news/rss.xml` | None | RSS feed for syndication |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEWS_INGEST_API_KEY` | — | Required. Bearer token for ingest endpoint |
| `GCS_NEWS_BUCKET` | `alphaforgeai-news` | GCS bucket for article storage |

## Deployment

### Deploy Forge News X Publisher to n8n

```bash
# SSH to VPS2
ssh root@72.61.0.186

# Import workflow via n8n UI or API
# Upload n8n/alphaforgeai_forge_news_x.json
# Activate workflow
```

The workflow uses credential **"X (Twitter) OAuth1"** (`WPpWGXWXaAS8H8ng`) which must exist in the target n8n instance.

## Monitoring

- n8n execution logs: VPS2 n8n dashboard → Executions
- Article count: `GET https://alphaforgeai.io/api/news` → `.total`
- X posts: @ALphaForgeAIio timeline

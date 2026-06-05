# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

## [0.5.0] — 2026-06-05 — News pipeline + site recovery (Issue #47)

### Added
- `/news` route and `news.html` template — live crypto news feed page
- `/api/news` and `/api/news/ingest` endpoints backed by GCS (`alphaforgeai-news` bucket)
- `gcs_news.py` service layer for GCS read/write
- n8n workflow: `AlphaForgeAI - Crypto News Ingest` on n8n.snowportal.cloud
  - 8 RSS sources: CoinDesk, Cointelegraph, Decrypt, Bitcoin Magazine, Coinbase Blog, Binance Blog, Kraken Blog
  - OpenAI (gpt-4o-mini) scoring, summarization, category + sentiment classification
  - Relevance filter (score ≥ 4), 48h dedup window, max 20 articles/run
  - Schedule: 4x/day at 8AM, 12PM, 5PM, 9PM ET
  - Webhook trigger: `POST https://n8n.snowportal.cloud/webhook/alphaforgeai-news-trigger`
- News nav link added to base.html
- `docs/NEWS_STATUS_REPORT.md`, `docs/NEWS_INGEST_TEST.md`, `docs/THEME_STATUS_REPORT.md`
- `tests/test_gcs_news.py` (10 tests)

### Changed
- CSS: full `prefers-color-scheme` light/dark theme support via CSS variables
- Homepage hero rewritten — clear product identity, 4 feature cards (Signals, News, Market Memory, Research)
- Cloud Run: `NEWS_INGEST_API_KEY` and `GCS_NEWS_BUCKET` env vars set, revision `alphaforgeai-00014-sl4`

### Fixed
- n8n openAi node v1.6 not sending `messages` → replaced with HTTP Request node
- Parse node losing original article title/url/source after OpenAI HTTP call
- The Block RSS 403 crashing entire run → `continueOnFail` on all RSS nodes
- POST node double-serializing body (`contentType: json` + `JSON.stringify`) → `contentType: raw`
- Schedule misconfigured (single 22:30 UTC cron) → 4 crons in ET timezone

## [0.4.0] — Initial tracked release

### Added
- MCP development environment integration
- Live Sentinel signal pipeline active (GCS: alphaforgeai-signals)
- Standard project documentation (PROJECT_RULES, AI_WORKFLOW)

# AlphaForgeAI n8n Workflows

## alphaforgeai_news_ingest.json

Crypto news ingestion workflow that runs twice daily (8:00 AM ET / 5:00 PM ET).

### Pipeline

1. Schedule Trigger - cron 0 13 * * * and 0 22 * * * (UTC)
2. RSS Feeds (8 sources) - CoinDesk, Cointelegraph, The Block, Decrypt, Bitcoin Magazine, Coinbase Blog, Binance Blog, Kraken Blog
3. Merge + Dedup - deduplicates by URL, filters to last 12 hours
4. OpenAI Enrichment (gpt-4o-mini) - scores relevance 0-10, extracts summary/category/assets/sentiment
5. Filter - drops articles with relevance_score below 7
6. Build Payload - wraps into schema_version:1 items array
7. POST - sends to https://alphaforgeai.io/api/news/ingest using stored credential
8. Log - captures status code and response body in execution log

### Credentials required (set in n8n UI)

- OpenAI AlphaForgeAI (openAiApi): Add your OpenAI API key
- AlphaForgeAI News Ingest Key (httpHeaderAuth): Pre-configured Bearer token

### Workflow ID on Atlas n8n

v2UklINa1V07oUsX

### Importing

Import alphaforgeai_news_ingest.json via n8n UI (Workflows > Import) or via API:
curl -X POST http://localhost:5678/api/v1/workflows -H 'X-N8N-API-KEY: <key>' -H 'Content-Type: application/json' -d @alphaforgeai_news_ingest.json

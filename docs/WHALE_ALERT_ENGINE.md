# Whale Alert Engine

## Overview

Tracks large on-chain cryptocurrency transfers (>$1M USD) every 4 hours, stores them in GCS, and publishes the top alert to @ALphaForgeAIio on X.

## Architecture

```
Whale Alert API (free tier) → Parse + Normalise → Gate
                                                    ↓ (has alerts)
                                  POST /api/whale-alerts/ingest → GCS (alphaforgeai-whale-alerts)
                                  Post to X (@ALphaForgeAIio)
```

## Data Source

**Whale Alert API** — `https://api.whale-alert.io/v1/transactions`

- Free tier: up to 10 req/min, transactions ≥$500K, max lookback 3600s
- This workflow uses min_value=$1,000,000 and lookback=14400s (4h)
- Requires: `WHALE_ALERT_API_KEY` environment variable in n8n

Get a free API key at: https://whale-alert.io/signup

## Alert Schema

Each event stored in GCS has:

| Field | Type | Description |
|---|---|---|
| `transaction_hash` | string | On-chain tx hash (dedup key) |
| `blockchain` | string | e.g. "ethereum", "bitcoin" |
| `symbol` | string | e.g. "ETH", "BTC", "USDT" |
| `amount` | number | Token amount |
| `amount_usd` | number | USD equivalent at time of transfer |
| `amount_formatted` | string | e.g. "12.5K", "1.2M" |
| `amount_usd_formatted` | string | e.g. "$12.5M" |
| `from_owner_type` | string | unknown \| exchange \| wallet \| contract \| burn \| mint |
| `from_owner` | string | Named entity if known |
| `to_owner_type` | string | Same options |
| `to_owner` | string | Named entity if known |
| `alert_type` | string | transfer \| exchange_inflow \| exchange_outflow \| burn \| mint |
| `description` | string | Human-readable: "12.5K ETH ($12.5M) moved from wallet to Coinbase" |
| `impact` | string | bullish \| bearish \| neutral |
| `timestamp` | ISO 8601 | Transaction timestamp |
| `url` | string | whale-alert.io link |

### Impact Classification

| Alert Type | Threshold | Signal |
|---|---|---|
| exchange_inflow | ≥$10M | bearish (sell-side pressure) |
| exchange_inflow | <$10M | neutral |
| exchange_outflow | ≥$10M | bullish (accumulation signal) |
| exchange_outflow | <$10M | neutral |
| transfer | any | neutral |

Exchange-to-exchange transactions are filtered out (low market impact).

## n8n Workflow (`n8n/alphaforgeai_whale_alerts.json`)

**Schedule:** 08:00, 12:00, 16:00, 20:00 ET daily

**Required n8n setup:**
1. Set `WHALE_ALERT_API_KEY` as an n8n environment variable
2. Create an n8n credential "AlphaForgeAI Whale Alerts Ingest Key" (HTTP Header Auth, header: `Authorization`, value: `Bearer <WHALE_ALERTS_INGEST_API_KEY>`)
3. The X credential "X (Twitter) OAuth1" (`WPpWGXWXaAS8H8ng`) is shared with Alpha Alerts

## API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `POST /api/whale-alerts/ingest` | Bearer `WHALE_ALERTS_INGEST_API_KEY` | Batch ingest events from n8n |
| `GET /api/whale-alerts` | None | JSON feed of recent whale events |
| `GET /api/whale-alerts?asset=ETH` | None | Filter by asset symbol |
| `GET /api/whale-alerts?limit=50` | None | Limit results (max 100) |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WHALE_ALERTS_INGEST_API_KEY` | — | Required. Bearer token for ingest endpoint |
| `GCS_WHALE_ALERTS_BUCKET` | `alphaforgeai-whale-alerts` | GCS bucket for event storage |

## Pre-deploy Checklist

- [ ] Create GCS bucket `alphaforgeai-whale-alerts` in `us-central1` with uniform bucket-level access
- [ ] Grant Cloud Run service account `roles/storage.objectAdmin` on the new bucket
- [ ] Generate `WHALE_ALERTS_INGEST_API_KEY`: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Add `WHALE_ALERTS_INGEST_API_KEY` to Cloud Run environment variables
- [ ] Get Whale Alert API key from https://whale-alert.io/signup
- [ ] Add `WHALE_ALERT_API_KEY` as n8n environment variable
- [ ] Create n8n HTTP Header Auth credential "AlphaForgeAI Whale Alerts Ingest Key"
- [ ] Import `n8n/alphaforgeai_whale_alerts.json` into n8n and activate

## Tweet Format Example

```
🐋 Whale Alert
📉 12.5K ETH ($12.5M) moved from wallet to Coinbase

Alert type: exchange inflow
Market signal: Bearish

https://whale-alert.io/transaction/ethereum/0xabc...

$ETH #WhaleAlert #crypto #AlphaForgeAI
```

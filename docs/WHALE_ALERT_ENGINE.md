# Whale Alert Engine

## Overview

Tracks large on-chain ETH transfers (≥$1M USD) every 4 hours by monitoring known exchange hot wallets via the free **Etherscan API**. Stores events in GCS and publishes the top alert to @ALphaForgeAIio on X.

## Architecture

```
Etherscan txlist (Coinbase / Binance / Kraken hot wallets)
  + Etherscan ETH price
          ↓
  Merge & Filter (≥$1M, last 4h, dedup by tx hash)
          ↓ (has alerts)
  POST /api/whale-alerts/ingest → GCS (alphaforgeai-whale-alerts)
  Post to X (@ALphaForgeAIio)
```

## Data Sources

**Etherscan API** (free, no wallet required beyond key)

- `module=account&action=txlist` — last 100 txns per wallet
- `module=stats&action=ethprice` — live ETH/USD price
- Rate limit: 5 req/sec, 100k req/day (this workflow uses 4 calls/run × 4 runs/day = **16 calls/day**)
- API key stored as `ETHERSCAN_API_KEY` in n8n environment

**Monitored wallets (Engine A):**

| Exchange | Address |
|---|---|
| Coinbase | `0xa090e606e30bd747d4e6245a1517ebe430f0057e` |
| Binance  | `0x28C6c06298d514Db089934071355E5743bf21d60` |
| Kraken   | `0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2` |

## Alert Schema

Each event stored in GCS:

| Field | Type | Description |
|---|---|---|
| `transaction_hash` | string | On-chain tx hash (dedup key) |
| `blockchain` | string | `"ethereum"` |
| `symbol` | string | `"ETH"` |
| `amount` | number | ETH amount |
| `amount_usd` | number | USD equivalent at time of transfer |
| `from_owner_type` | string | `"exchange"` (source wallet is known exchange) |
| `to_owner_type` | string | `"unknown"` (destination not classified in MVP) |
| `alert_type` | string | `"large_transfer"` |
| `timestamp` | ISO 8601 | Transaction timestamp |
| `url` | string | Etherscan link to the transaction |
| `source_wallet` | string | `"Coinbase"` / `"Binance"` / `"Kraken"` |
| `from_address` | string | Raw `from` address |
| `to_address` | string | Raw `to` address |

## n8n Workflow (`n8n/alphaforgeai_whale_alerts.json`)

**Schedule:** 08:00, 12:00, 16:00, 20:00 ET daily

**Nodes:**
1. Schedule Trigger (4× daily)
2. Fetch ETH Price (Etherscan stats)
3. Fetch Coinbase Txns
4. Fetch Binance Txns
5. Fetch Kraken Txns
6. Merge & Filter Events (Code — dedup, filter ≥$1M, sort by size desc)
7. Has Alerts? (IF count > 0)
8. POST to AlphaForgeAI (`/api/whale-alerts/ingest`, bearer auth)
9. Format Tweet
10. Post to X

**Required n8n environment variables (set in `/opt/stack/.env` on VPS2):**
- `ETHERSCAN_API_KEY` — Etherscan free API key
- `WHALE_INGEST_KEY` — Bearer token matching `WHALE_ALERTS_INGEST_API_KEY` on Cloud Run

X credential "X (Twitter) OAuth1" (`WPpWGXWXaAS8H8ng`) is shared with Alpha Alerts.

## API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `POST /api/whale-alerts/ingest` | Bearer `WHALE_ALERTS_INGEST_API_KEY` | Batch ingest events from n8n |
| `GET /api/whale-alerts` | None | JSON feed of recent whale events |
| `GET /api/whale-alerts?asset=ETH` | None | Filter by asset symbol |
| `GET /api/whale-alerts?limit=50` | None | Limit results (max 100) |

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `ETHERSCAN_API_KEY` | n8n (VPS2 .env) | Etherscan free API key |
| `WHALE_INGEST_KEY` | n8n (VPS2 .env) | Bearer token for ingest endpoint |
| `WHALE_ALERTS_INGEST_API_KEY` | Cloud Run | Must match `WHALE_INGEST_KEY` |
| `GCS_WHALE_ALERTS_BUCKET` | Cloud Run | Default: `alphaforgeai-whale-alerts` |

## Pre-deploy Checklist

- [x] `ETHERSCAN_API_KEY` added to VPS2 `/opt/stack/.env` and n8n container
- [x] `WHALE_INGEST_KEY` generated and added to VPS2 `/opt/stack/.env` and n8n container
- [ ] Create GCS bucket `alphaforgeai-whale-alerts` in `us-central1` with uniform bucket-level access
- [ ] Grant Cloud Run service account `roles/storage.objectAdmin` on the bucket
- [ ] Retrieve `WHALE_INGEST_KEY` from VPS2: `cat /root/.whale_ingest_key`
- [ ] Add `WHALE_ALERTS_INGEST_API_KEY=<value>` to Cloud Run environment variables
- [ ] Import `n8n/alphaforgeai_whale_alerts.json` into n8n and activate

## Tweet Format

```
WHALE ALERT
12500 ETH ($42.3M) moved from Binance hot wallet

https://etherscan.io/tx/0xabc...

#Ethereum #ETH #CryptoWhales #AlphaForgeAI
```

## Future On-Chain Improvements (Issues #85, #86)

- **Engine B** (Issue #85): Scan all Ethereum blocks for any transfer ≥$1M, not just known wallets
- **Engine C** (Issue #86): BTC large transfers via mempool.space (no API key required)
- If budget allows: CoinGecko Pro or CoinMarketCap for multi-asset price feeds and richer metadata

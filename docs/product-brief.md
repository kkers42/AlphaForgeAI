# AlphaForgeAI — Product Brief

## What It Is

AlphaForgeAI is an AI-assisted crypto signal and market insight platform. It surfaces quantitative trading signals, onchain data context, and daily market explainers in a format readable by both technical and non-technical audiences.

## Problem It Solves

Retail crypto participants are drowning in noise — Twitter hype, influencer calls, and gut-feel trading. Meanwhile, institutional-grade quant tools exist but are inaccessible. AlphaForgeAI bridges this gap by packaging real model output and onchain data into clear, actionable content.

## Core Value Proposition

- **Signal transparency** — signals come from a real XGBoost model trained on 90 days of price + onchain data, not a black box
- **Plain-language explainers** — AI-written daily market breakdowns that explain *why* something happened, not just *what*
- **Onchain context** — long/short ratios, exchange netflows, and open interest made readable
- **No hype** — no price predictions, no "guaranteed returns", no influencer framing

## Current Build State (v0.3.1)

| Module | Status |
|--------|--------|
| FastAPI app | ✅ Running |
| Homepage | ✅ Live |
| Dashboard stub | ✅ Live |
| Shared layout | ✅ `app/templates/base.html` |
| Signal domain model | ✅ `app/domain/signals.py` |
| Centralized config | ✅ `app/core/config.py` — v0.3.1, signal_source, fallback, Sentinel SSH + timeout |
| Signal repository | ✅ `app/repositories/signal_repository.py` — local + SSH loaders, status/error_message |
| Snapshot file | ✅ `data/signals_snapshot.json` — v2 metadata envelope |
| Signal service | ✅ `app/services/signal_service.py` — env-aware fallback, status="fallback" |
| Signal feed page | ✅ `GET /signals` — status dot, per-status notices (ok/empty/error/fallback) |
| Health endpoints | ✅ `GET /health` + `GET /health/signals` — config summary, no live SSH probe |
| Content pipeline | 🔲 Phase 3 |
| Live signal feed (Sentinel SSH active) | 🔲 Phase 3 — set SIGNAL_SOURCE=sentinel_ssh to enable |
| Onchain explorer | 🔲 Phase 4 |
| Auth + monetisation | 🔲 Phase 5 |

## Signal Architecture

```
GET /signals
    └── signal_service.get_signals() → SignalSnapshot
            ├── signal_repository.get_signals()             ← primary
            │       ├── settings.signal_source dispatcher
            │       │     "local_snapshot" → _load_local_snapshot_raw()
            │       │     "sentinel_ssh"   → _load_sentinel_snapshot_raw()
            │       │                              └── subprocess SSH → snapshot.py
            │       └── _parse_snapshot()          ← validates, extracts metadata
            │
            └── mock fallback (if allowed by settings)
                    set used_mock_fallback = True
                    source = "mock_fallback"
```

**SignalSnapshot fields passed to template:**
- `signals` — validated list
- `source` — e.g. `"local_snapshot"`, `"sentinel_ssh"`, `"mock_fallback"`
- `generated_at` — ISO timestamp from snapshot metadata
- `model_version` — e.g. `"xgboost-nightly"`
- `used_mock_fallback` — drives warning notice in UI
- `status` — `"ok"` / `"empty"` / `"error"` / `"fallback"` (drives dot color + notice type)
- `error_message` — short string, set on `"error"` paths, preserved through `"fallback"`

**Status → UI mapping:**

| status | Source bar dot | Notice style | Notice content |
|--------|---------------|-------------|----------------|
| `ok` | 🟢 green | info (grey) | "Signals loaded from ..." |
| `empty` | 🟡 yellow | warn (yellow) | "Snapshot is empty..." |
| `error` | 🔴 red | error (red) | error_message |
| `fallback` | 🟡 yellow | warn (yellow) | "Mock fallback active" |

**To go live**: set `SIGNAL_SOURCE=sentinel_ssh` and `SENTINEL_SSH_HOST=192.168.1.40`.
Source, metadata, and UI all update automatically — no template or service changes needed.

## Mock Fallback Policy

| Environment | Default fallback | Override env var |
|-------------|-----------------|-----------------|
| `development` | **allowed** | `ALLOW_MOCK_FALLBACK=false` |
| `production` | **disabled** | `ALLOW_MOCK_FALLBACK=true` |

Production does not silently inject mock data. An empty or unreachable snapshot
(including SSH failures) shows an empty feed with a clear warning — operators
can diagnose the failure rather than serving stale data undetected.

## Sentinel SSH Config

| Env var | Default | Purpose |
|---------|---------|---------|
| `SIGNAL_SOURCE` | `local_snapshot` | Set to `sentinel_ssh` to enable live feed |
| `SENTINEL_SSH_HOST` | *(empty)* | Sentinel IP or hostname — required for SSH source |
| `SENTINEL_SSH_USER` | `kkers` | SSH username |
| `SENTINEL_SSH_KEY_PATH` | *(empty)* | Private key path; omit to use SSH agent |
| `SENTINEL_SSH_TIMEOUT` | `18` | Subprocess + ConnectTimeout in seconds |
| `SENTINEL_SSH_STRICT_HOST_KEY` | `false` | Enable SSH known-hosts checking |
| `SENTINEL_SNAPSHOT_COMMAND` | `python3 /data/ai-trading-bot/snapshot.py` | Command run on Sentinel |

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Fast check: service identity + signal source config summary |
| `GET /health/signals` | Signal source config detail: host, timeout, command (no SSH probe) |

## Snapshot Format (v2)

```json
{
  "generated_at":  "2026-04-22T12:00:00Z",
  "model_version": "xgboost-nightly",
  "source":        "local_snapshot",
  "signals":       [ { ... } ]
}
```

Legacy bare-array format is still accepted for backward compatibility.

## Signal Model Contract

A `Signal` has:
- `symbol` — asset ticker (e.g. "ETH")
- `direction` — LONG / SHORT / FLAT
- `timeframe` — 15m / 1h / 4h
- `confidence` — 0.0–1.0 model confidence
- `regime` — market regime label (uptrend, downtrend, ranging)
- `thesis` — plain-language explanation of the signal
- `top_features` — optional ranked feature importance from XGBoost

## Target Audience

- Retail crypto traders who want edge without building it themselves
- DeFi participants who want to understand market structure
- Content consumers who want signal-backed analysis, not opinion

## Monetisation Path (Long Term)

| Tier | Offering | Model |
|------|----------|-------|
| Free | Daily market explainer post | Ad-supported or lead gen |
| Basic | Weekly signal digest (top 5 setups) | $9/mo |
| Pro | Live signal feed, onchain dashboard | $29/mo |
| API | Raw signal endpoint for algo traders | Usage-based |

## Tech Stack

- **Backend**: FastAPI (Python)
- **Templates**: Jinja2 with shared base layout
- **Config**: Centralized `Settings` dataclass, env-aware
- **ML**: XGBoost, trained nightly on Orion (RTX 2080 Ti)
- **Data**: Coinbase Advanced Trade API, OKX onchain API, Alternative.me F&G
- **Content pipeline**: N8N → LLM (Claude/GPT) → structured JSON → blog post (Phase 3)
- **Hosting**: TBD (Hostinger VPS or Railway)

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

## Current Build State (v0.3.0)

| Module | Status |
|--------|--------|
| FastAPI app | ✅ Running |
| Homepage | ✅ Live |
| Dashboard stub | ✅ Live — module status overview |
| Shared layout (base.html) | ✅ In place |
| Signal domain model | ✅ Typed — `app/domain/signals.py` |
| Centralized settings | ✅ `app/core/config.py` |
| Signal repository | ✅ `app/repositories/signal_repository.py` — reads from local JSON snapshot |
| Signal service layer | ✅ `app/services/signal_service.py` — calls repository, mock fallback |
| Signal snapshot file | ✅ `data/signals_snapshot.json` — 7 realistic signals, swap-ready |
| Signal feed page | ✅ `GET /signals` — 7 signals with direction, confidence, thesis, features |
| Content pipeline | 🔲 Phase 3 |
| Live signal feed (Sentinel SSH) | 🔲 Phase 3 |
| Onchain explorer | 🔲 Phase 4 |
| Auth + monetisation | 🔲 Phase 5 |

## Signal Architecture

```
GET /signals
    └── signal_service.get_signals()
            └── signal_repository.get_signals()         ← primary
                    └── _load_snapshot()                ← reads data/signals_snapshot.json
            └── signal_service.get_mock_signals()       ← fallback (snapshot missing/empty)
```

**Next swap**: replace `_load_snapshot()` in `signal_repository.py` with an SSH call to
Sentinel. The service, route, and template are untouched.

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

## What It Is Not (Phase 1–3)

- Not a trading platform — no order execution
- Not a portfolio tracker — no account connection
- Not a prediction engine — signals are probabilistic, not guarantees

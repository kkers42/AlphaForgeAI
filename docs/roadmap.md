# AlphaForgeAI — Roadmap

## Phase 1 — Foundation (Current)

> Goal: clean, runnable project skeleton. Nothing invented, nothing broken.

- [x] FastAPI app with `/` and `/health` routes
- [x] Jinja2 template homepage
- [x] Static CSS — dark theme, branded
- [x] Project structure, README, docs
- [ ] Deploy to VPS (Hostinger / Railway)
- [ ] Domain + SSL

---

## Phase 2 — Content Pipeline

> Goal: publish real content automatically. One daily post, no manual work.

- [ ] N8N workflow: scrape crypto news + macro feeds every 2h
- [ ] LLM (Claude/GPT) interprets headlines → structured JSON (bullish/bearish score, key event, impact 0-10)
- [ ] Daily market summary post auto-generated and published to `/blog/{date}`
- [ ] Blog index route `/blog` listing recent posts
- [ ] Posts stored as markdown files or SQLite (no heavy DB yet)
- [ ] RSS feed at `/feed.xml`

---

## Phase 3 — Signal Dashboard

> Goal: surface real model output publicly (no auth needed for basic view).

- [ ] `/signals` route — shows today's top 3 XGBoost setups
- [ ] Each signal card: asset, direction, confidence %, regime, entry zone, key features
- [ ] Signal data pulled from Sentinel via SSH snapshot (same pattern as trading dashboard)
- [ ] Auto-refreshes every 15 minutes
- [ ] No trade execution — read-only display

---

## Phase 4 — Onchain Explorer

> Goal: make onchain data readable.

- [ ] `/onchain` route — L/S ratio, OI, exchange netflow for BTC + ETH
- [ ] Data from existing `onchain_fetcher.py` pipeline (OKX API)
- [ ] Chart.js sparklines for 7-day trend
- [ ] Plain-language interpretation: "BTC L/S ratio at 1.8 — historically elevated, precedes retracement 62% of the time"

---

## Phase 5 — Monetisation

> Goal: first paying subscriber.

- [ ] Auth system (FastAPI + JWT or Clerk.dev)
- [ ] Stripe integration for subscriptions
- [ ] Pro tier: live signal feed, full onchain dashboard, email digest
- [ ] Email newsletter (Resend or Mailgun) — weekly signal summary
- [ ] Paywall on `/signals/live` and `/onchain/full`

---

## Guiding Principles

- Ship real things, not demos
- Every public-facing number comes from a real model or real data source
- No hype, no price targets, no "this is financial advice" territory
- Build the audience before the paywall

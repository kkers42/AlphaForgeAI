# AlphaForgeAI — Roadmap

## Phase 1 — Foundation ✅

> Clean, runnable project skeleton.

- [x] FastAPI app with `/` and `/health` routes
- [x] Jinja2 homepage template
- [x] Dark theme CSS, branded
- [x] Project structure, README, docs

---

## Phase 1.5 — Structure Layer ✅

> Prepare the codebase for modules without overbuilding.

- [x] Centralized settings — `app/core/config.py`
- [x] Shared base template — `app/templates/base.html`
- [x] Dashboard route and stub page — `GET /dashboard`
- [x] Signal domain model — `app/domain/signals.py` (typed contract)
- [x] Route split — `pages.py` + `dashboard.py`
- [x] Environment-aware footer and `/health` response
- [ ] Deploy to VPS (Hostinger / Railway)
- [ ] Domain + SSL

---

## Phase 2 — Signal Feed ✅

> Turn the typed domain model into a visible, working page.

- [x] `app/services/signal_service.py` — `get_mock_signals()` returns 7 realistic signals
- [x] `app/routes/signals.py` — `GET /signals` with summary counts passed to template
- [x] `app/templates/signals.html` — feed of signal cards: direction badge, confidence bar, regime tag, thesis, top features
- [x] Nav updated to include Signals link with active state
- [x] Dashboard Signal Feed card updated to "Preview" status with link to `/signals`
- [x] CSS: direction badges, confidence bar, feature chips, mock notice, summary pills

---

## Phase 2.5 — Repository Layer ✅

> Introduce a clean data loading architecture before wiring in live data.

- [x] `app/repositories/signal_repository.py` — loads signals from local JSON snapshot
- [x] `data/signals_snapshot.json` — 7 realistic signals; stand-in for Sentinel output
- [x] `app/services/signal_service.py` refactored — calls repository as primary source,
      `get_mock_signals()` retained as explicit fallback only
- [x] `app/routes/signals.py` updated — calls `get_signals()` instead of `get_mock_signals()`
- [x] Error handling: missing file, bad JSON, wrong type, and per-record validation failures
      all produce safe empty/partial results without crashing the app
- [x] Swap guide documented in `signal_repository.py` — one function to change for SSH source

**Extension point**: replace `_load_snapshot()` in `signal_repository.py` with an SSH call
to Sentinel — the service, route, and template are untouched.

---

## Phase 3 — Content Pipeline

> Publish real AI-written content automatically. One daily post, no manual work.

- [ ] N8N workflow: scrape crypto news + macro feeds every 2h
- [ ] LLM (Claude/GPT) interprets headlines → structured JSON
  - bullish/bearish score
  - key event summary
  - impact rating 0–10
  - affected assets
- [ ] Daily market summary auto-generated → `/blog/{date}`
- [ ] Blog index route `/blog`
- [ ] Posts stored as markdown or SQLite
- [ ] RSS feed at `/feed.xml`

**Extension point**: `app/domain/signals.py` → `thesis` field is designed to accept LLM-generated text directly.

---

## Phase 3 — Live Signal Feed

> Replace the local snapshot with real XGBoost output from Sentinel.

- [ ] `_load_snapshot()` in `signal_repository.py` replaced with SSH fetch from Sentinel
- [ ] Sentinel runs `snapshot.py` — outputs signal JSON alongside position/trade data
- [ ] `/signals` route auto-refreshes (meta refresh or lightweight JS)
- [ ] Dashboard Signal Feed card updated to "Live" status

**Extension point**: `Signal` model already typed. `signal_repository.py` swap guide is
in its module docstring — one function, zero template changes.

---

## Phase 4 — Onchain Explorer

> Make onchain data readable without charts and jargon.

- [ ] `/onchain` route
- [ ] L/S ratio, OI, exchange netflow for BTC + ETH
- [ ] Data from `onchain_fetcher.py` pipeline (OKX API)
- [ ] Chart.js sparklines for 7-day trend (single JS dependency, justified)
- [ ] Plain-language interpretation alongside each metric

---

## Phase 5 — Monetisation

> First paying subscriber.

- [ ] Auth (FastAPI + JWT or Clerk.dev)
- [ ] Stripe integration for subscriptions
- [ ] Pro tier: live signal feed, full onchain dashboard, email digest
- [ ] Email newsletter (Resend or Mailgun) — weekly signal digest
- [ ] Paywall on `/signals/live` and `/onchain/full`

---

## Guiding Principles

- Ship real things, not demos
- Every public-facing number comes from a real model or real data source
- No hype, no price targets, no "this is financial advice" territory
- Build audience before paywall
- Extend the domain model (`app/domain/`) before building UI — contract first

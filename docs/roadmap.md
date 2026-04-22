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
- [x] CSS: direction badges, confidence bar, feature chips, summary pills

---

## Phase 2.5 — Repository Layer ✅

> Introduce a clean data loading architecture before wiring in live data.

- [x] `app/repositories/signal_repository.py` — loads signals from local JSON snapshot
- [x] `data/signals_snapshot.json` — 7 realistic signals; stand-in for Sentinel output
- [x] `app/services/signal_service.py` refactored — calls repository as primary source;
      `get_mock_signals()` retained as explicit fallback only
- [x] `app/routes/signals.py` updated — calls `get_signals()` instead of `get_mock_signals()`
- [x] Error handling: missing file, bad JSON, wrong type, and per-record validation failures
      all produce safe empty/partial results without crashing the app

---

## Phase 2.6 — Architecture Cleanup ✅

> Correctness, observability, and production readiness before the Sentinel swap.

- [x] Version bumped to `0.3.0` in `app/core/config.py`
- [x] `signal_source` setting added to config (default: `"local_snapshot"`)
- [x] `allow_mock_fallback` property added to `Settings`:
      - `development` → `True` by default
      - `production` → `False` by default
      - Overridable at runtime via `ALLOW_MOCK_FALLBACK` env var
- [x] Snapshot format upgraded to v2 — `data/signals_snapshot.json` now carries:
      `generated_at`, `model_version`, `source`; bare-array (v1) still accepted
- [x] `SignalSnapshot` dataclass introduced in `signal_repository.py` — carries signals
      and metadata through every layer to the template
- [x] Repository returns `SignalSnapshot`; service decorates it with `used_mock_fallback`
- [x] Route passes `data_source`, `generated_at`, `model_version`, `used_mock_fallback`
      to template
- [x] `/signals` page shows source meta bar (source, model, generated time) and
      context-sensitive notice (snapshot info / mock warning / empty-feed warning)
- [x] CSS: `.source-meta` bar, `.snapshot-notice`, `.snapshot-notice-warn`
- [x] In production, empty snapshot → empty feed with warning; no silent mock injection
- [x] Swap guide updated in `signal_repository.py` — SSH source emits v2 format;
      metadata populates automatically after the swap

**Extension point**: replace `_load_raw()` in `signal_repository.py`.
Everything above it — `SignalSnapshot`, `_parse_snapshot()`, `get_signals()`,
error handling, the service, the route, and all templates — is unchanged.

---

## Phase 3 — Content Pipeline

> Publish real AI-written content automatically. One daily post, no manual work.

- [ ] N8N workflow: scrape crypto news + macro feeds every 2h
- [ ] LLM (Claude/GPT) interprets headlines → structured JSON
  - bullish/bearish score, key event summary, impact rating, affected assets
- [ ] Daily market summary auto-generated → `/blog/{date}`
- [ ] Blog index route `/blog`
- [ ] Posts stored as markdown or SQLite
- [ ] RSS feed at `/feed.xml`

---

## Phase 2.7 — Sentinel SSH Source ✅

> Wire the repository to the real Sentinel signal output without touching the UI.

- [x] `_load_local_snapshot_raw()` — renamed from `_load_raw()`, unchanged behaviour
- [x] `_load_sentinel_snapshot_raw()` — subprocess SSH to Sentinel, parses stdout JSON
- [x] Source dispatcher in `get_signals()` — `settings.signal_source` selects loader
- [x] Safe error handling for: missing config, SSH timeout, non-zero exit, bad JSON
- [x] Source label override: when Sentinel metadata omits `source`, tag is set to
      `"sentinel_ssh"` automatically so the UI always reflects the active source
- [x] Config fields added: `sentinel_ssh_host`, `sentinel_ssh_user`,
      `sentinel_ssh_key_path`, `sentinel_snapshot_command`
- [x] Env vars documented: `SENTINEL_SSH_HOST`, `SENTINEL_SSH_USER`,
      `SENTINEL_SSH_KEY_PATH`, `SENTINEL_SNAPSHOT_COMMAND`
- [x] README and product-brief updated

**To go live**: set `SIGNAL_SOURCE=sentinel_ssh` and `SENTINEL_SSH_HOST=192.168.1.40`.
No code changes required. Template, service, and route are unchanged.

---

## Phase 3 — Live Signal Feed

> Activate Sentinel SSH source and keep the feed current.

- [ ] Sentinel `snapshot.py` extended to emit a `signals` array in v2 envelope format
      alongside existing position/trade data
- [ ] `SIGNAL_SOURCE=sentinel_ssh` set in production environment (or `.env`)
- [ ] `/signals` route auto-refreshes (meta refresh or lightweight JS)
- [ ] Dashboard Signal Feed card updated to "Live" status
- [ ] `data_source` on signals page shows `"sentinel_ssh"` automatically

---

## Phase 4 — Onchain Explorer

> Make onchain data readable without charts and jargon.

- [ ] `/onchain` route
- [ ] L/S ratio, OI, exchange netflow for BTC + ETH
- [ ] Data from `onchain_fetcher.py` pipeline (OKX API)
- [ ] Chart.js sparklines for 7-day trend
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
- Production never silently masks failures with mock data

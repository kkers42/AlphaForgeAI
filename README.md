# AlphaForgeAI

**AI-assisted crypto signal and market insight platform.**

Built on a real XGBoost trading system, AlphaForgeAI surfaces quantitative signals, onchain data context, and daily AI-written market explainers — for traders who want edge without the noise.

---

## Project Overview

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Templates | Jinja2 with shared base layout |
| Styling | Vanilla CSS (dark theme) |
| Config | `app/core/config.py` — centralized settings |
| Domain | `app/domain/signals.py` — typed Signal model |
| Repository | `app/repositories/signal_repository.py` — loads signals from local JSON snapshot |
| Services | `app/services/signal_service.py` — calls repository; falls back to mock data |
| ML Engine | XGBoost (nightly GPU retrain) |
| Data | Coinbase Advanced Trade API, OKX Onchain API |

---

## Local Setup

### 1. Clone the repository

```powershell
git clone https://github.com/kkers42/AlphaForgeAI.git
cd AlphaForgeAI
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the development server

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Signal Data Source

Signals are loaded from a local JSON snapshot file:

```
data/signals_snapshot.json
```

This file contains the same structure as the Sentinel live snapshot and acts as a
stand-in until the SSH repository is wired in. To update signals, edit this file
directly — the route and template require no changes.

**To swap to the Sentinel/SSH source**: replace `_load_snapshot()` in
`app/repositories/signal_repository.py` with a function that fetches the JSON
over SSH. See the swap guide in that file's docstring.

---

## Available Routes

| Route | Description |
|-------|-------------|
| `GET /` | Homepage — hero + feature overview |
| `GET /dashboard` | Dashboard — module status and roadmap view |
| `GET /signals` | Signal feed — repository-backed signals with direction, confidence, regime, thesis |
| `GET /health` | Health check — returns service name, version, environment |

---

## Folder Structure

```
AlphaForgeAI/
├── app/
│   ├── main.py                  # FastAPI app init, static mount, router wiring
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py            # Centralized settings (name, version, environment)
│   ├── domain/
│   │   ├── __init__.py
│   │   └── signals.py           # Signal Pydantic model — typed contract
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── signal_repository.py # Loads + validates signals from local JSON snapshot
│   ├── services/
│   │   ├── __init__.py
│   │   └── signal_service.py    # get_signals() → repository; get_mock_signals() → fallback
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py             # GET / and GET /health
│   │   ├── dashboard.py         # GET /dashboard
│   │   └── signals.py           # GET /signals
│   ├── templates/
│   │   ├── base.html            # Shared layout — header, nav, footer, blocks
│   │   ├── index.html           # Homepage (extends base.html)
│   │   ├── dashboard.html       # Dashboard module status page (extends base.html)
│   │   └── signals.html         # Signal feed page (extends base.html)
│   └── static/
│       └── css/
│           └── styles.css       # Full dark-theme CSS
├── data/
│   └── signals_snapshot.json    # Local signal snapshot — stand-in for Sentinel output
├── docs/
│   ├── product-brief.md
│   └── roadmap.md
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Environment

The app reads an `ENVIRONMENT` env var (defaults to `development`).

```powershell
# Run in production mode
$env:ENVIRONMENT = "production"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The environment label appears in the page footer and in the `/health` response.

---

## Roadmap Summary

- **Phase 1** ✅ Foundation: FastAPI skeleton, branded homepage, docs
- **Phase 1.5** ✅ Structure: config, base layout, dashboard stub, signal domain model
- **Phase 2** ✅ Signal feed: typed service layer, mock signals, working `/signals` page
- **Phase 2.5** ✅ Repository layer: `signal_repository.py` loads from `data/signals_snapshot.json`
- **Phase 3** — Content pipeline: AI-written daily market posts via N8N + LLM
- **Phase 3** — Live signals: swap `_load_snapshot()` for SSH fetch from Sentinel
- **Phase 4** — Onchain explorer: L/S ratio, OI, netflow charts
- **Phase 5** — Monetisation: auth, Stripe subscriptions, email digest

See [`docs/roadmap.md`](docs/roadmap.md) for full detail.

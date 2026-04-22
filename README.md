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
| Config | `app/core/config.py` — version, environment, signal source, fallback policy, Sentinel SSH settings |
| Domain | `app/domain/signals.py` — typed Signal model |
| Repository | `app/repositories/signal_repository.py` — local snapshot or Sentinel SSH source |
| Services | `app/services/signal_service.py` — calls repository; env-aware mock fallback |
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

## Signal Data Sources

The active source is controlled by the `SIGNAL_SOURCE` environment variable
(default: `local_snapshot`).

### `local_snapshot` (default)

Reads `data/signals_snapshot.json` from the project root.

```json
{
  "generated_at":  "2026-04-22T12:00:00Z",
  "model_version": "xgboost-nightly",
  "source":        "local_snapshot",
  "signals":       [ ... ]
}
```

A bare JSON array (legacy format) is also accepted.

### `sentinel_ssh`

SSHes to the Sentinel trading server and runs `snapshot.py`, which emits the
same v2 JSON envelope.  Requires three environment variables:

| Variable | Description |
|----------|-------------|
| `SENTINEL_SSH_HOST` | IP or hostname (e.g. `192.168.1.40`) |
| `SENTINEL_SSH_USER` | SSH username (default: `kkers`) |
| `SENTINEL_SSH_KEY_PATH` | Path to private key (optional — omit to use SSH agent) |

```powershell
$env:SIGNAL_SOURCE       = "sentinel_ssh"
$env:SENTINEL_SSH_HOST   = "192.168.1.40"
$env:SENTINEL_SSH_KEY_PATH = "C:/Users/josh/.ssh/id_rsa"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On SSH failure (timeout, non-zero exit, invalid JSON) the repository returns
an empty `SignalSnapshot`. In development the service falls back to mocks; in
production the `/signals` page renders with a warning and zero cards.

The `/signals` page shows the active source, model version, and generation
time from the snapshot metadata.  No template or service changes are needed
when switching sources.

---

## Mock Fallback Behaviour

| Environment | Default | Override |
|-------------|---------|----------|
| `development` | fallback **allowed** — UI never blank during local work | `ALLOW_MOCK_FALLBACK=false` |
| `production` | fallback **disabled** — empty snapshot shows empty feed | `ALLOW_MOCK_FALLBACK=true` |

In production, if the snapshot is missing or empty, the `/signals` page renders
with zero signal cards and a warning notice — mock data is not injected silently.

---

## Available Routes

| Route | Description |
|-------|-------------|
| `GET /` | Homepage — hero + feature overview |
| `GET /dashboard` | Dashboard — module status and roadmap view |
| `GET /signals` | Signal feed — snapshot-backed signals with source metadata |
| `GET /health` | Health check — returns service name, version, environment |

---

## Folder Structure

```
AlphaForgeAI/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py            # version 0.3.0, signal_source, allow_mock_fallback
│   ├── domain/
│   │   ├── __init__.py
│   │   └── signals.py           # Signal Pydantic model
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── signal_repository.py # SignalSnapshot, v2 + legacy format, swap guide
│   ├── services/
│   │   ├── __init__.py
│   │   └── signal_service.py    # env-aware fallback, returns SignalSnapshot
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py
│   │   ├── dashboard.py
│   │   └── signals.py           # unpacks SignalSnapshot into template context
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── dashboard.html
│   │   └── signals.html         # source-meta bar + conditional notices
│   └── static/
│       └── css/
│           └── styles.css       # .source-meta, .snapshot-notice styles
├── data/
│   └── signals_snapshot.json    # v2 format with metadata envelope
├── docs/
│   ├── product-brief.md
│   └── roadmap.md
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Environment Variables

| Variable | Default | Effect |
|----------|---------|--------|
| `ENVIRONMENT` | `development` | Controls debug mode, default fallback policy |
| `SIGNAL_SOURCE` | `local_snapshot` | Active signal source: `local_snapshot` or `sentinel_ssh` |
| `ALLOW_MOCK_FALLBACK` | *(derived from ENVIRONMENT)* | `true`/`false` — overrides fallback policy |
| `SENTINEL_SSH_HOST` | *(empty)* | Required when `SIGNAL_SOURCE=sentinel_ssh` |
| `SENTINEL_SSH_USER` | `kkers` | SSH username for Sentinel |
| `SENTINEL_SSH_KEY_PATH` | *(empty)* | Private key path; omit to use SSH agent |
| `SENTINEL_SNAPSHOT_COMMAND` | `python3 /data/ai-trading-bot/snapshot.py` | Command run on Sentinel |

```powershell
# Simulate production behaviour locally
$env:ENVIRONMENT        = "production"
$env:ALLOW_MOCK_FALLBACK = "false"
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Force mock fallback even in production (emergency / demo)
$env:ENVIRONMENT        = "production"
$env:ALLOW_MOCK_FALLBACK = "true"
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Switch to live Sentinel signal source
$env:SIGNAL_SOURCE         = "sentinel_ssh"
$env:SENTINEL_SSH_HOST     = "192.168.1.40"
$env:SENTINEL_SSH_KEY_PATH = "C:/Users/josh/.ssh/id_rsa"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Roadmap Summary

- **Phase 1** ✅ Foundation: FastAPI skeleton, branded homepage, docs
- **Phase 1.5** ✅ Structure: config, base layout, dashboard stub, signal domain model
- **Phase 2** ✅ Signal feed: typed service layer, working `/signals` page
- **Phase 2.5** ✅ Repository layer: `signal_repository.py` loads from `data/signals_snapshot.json`
- **Phase 2.6** ✅ Architecture cleanup: v0.3.0, metadata envelope, env-aware fallback, source UI
- **Phase 2.7** ✅ Sentinel SSH source: `sentinel_ssh` loader, config fields, source dispatcher
- **Phase 3** — Content pipeline: AI-written daily market posts via N8N + LLM
- **Phase 3** — Live signals: set `SIGNAL_SOURCE=sentinel_ssh` + `SENTINEL_SSH_HOST` to go live
- **Phase 4** — Onchain explorer: L/S ratio, OI, netflow charts
- **Phase 5** — Monetisation: auth, Stripe, email digest

See [`docs/roadmap.md`](docs/roadmap.md) for full detail.

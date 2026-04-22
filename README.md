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
| Config | `app/core/config.py` — version, environment, signal source, fallback policy, Sentinel SSH + timeout |
| Domain | `app/domain/signals.py` — typed Signal model |
| Repository | `app/repositories/signal_repository.py` — local snapshot or Sentinel SSH; status-tagged result |
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
same v2 JSON envelope.  Requires:

| Variable | Description |
|----------|-------------|
| `SENTINEL_SSH_HOST` | IP or hostname (e.g. `192.168.1.40`) |
| `SENTINEL_SSH_USER` | SSH username (default: `kkers`) |
| `SENTINEL_SSH_KEY_PATH` | Path to private key (optional — omit to use SSH agent) |
| `SENTINEL_SSH_TIMEOUT` | Subprocess timeout in seconds (default: `18`) |

```powershell
$env:SIGNAL_SOURCE           = "sentinel_ssh"
$env:SENTINEL_SSH_HOST       = "192.168.1.40"
$env:SENTINEL_SSH_KEY_PATH   = "C:/Users/josh/.ssh/id_rsa"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**SSH failure handling** — each failure mode is logged with a distinct message
and returns a safe empty `SignalSnapshot` with `status="error"`:

| Failure | Log message prefix | `error_message` shown in UI |
|---------|-------------------|------------------------------|
| `SENTINEL_SSH_HOST` not set | `config error` | "Config error: SENTINEL_SSH_HOST is not configured" |
| SSH timeout | `timed out after Ns` | "SSH timeout after 18s" |
| Non-zero SSH exit | `SSH error: SSH exited N` | "SSH error: SSH exited 1: ..." |
| Empty stdout | `SSH error: stdout was empty` | "SSH error: SSH succeeded but stdout was empty" |
| Invalid JSON | `invalid JSON from source` | "Invalid JSON from source" |
| Malformed payload | `malformed snapshot payload` | "Malformed snapshot: ..." |

The `/signals` page shows a **red notice** with the error message when the source
fails, and a **yellow notice** when mock fallback is active.

---

## Observability — SignalSnapshot.status

Every `SignalSnapshot` carries a `status` field:

| Value | Meaning | UI indicator |
|-------|---------|-------------|
| `"ok"` | Signals loaded and validated | Green dot in source bar |
| `"empty"` | Source responded but returned no signals | Yellow dot + yellow notice |
| `"error"` | Load or parse failed | Red dot + red notice with reason |
| `"fallback"` | Service substituted mock signals | Yellow dot + yellow notice |

---

## Mock Fallback Behaviour

| Environment | Default | Override |
|-------------|---------|----------|
| `development` | fallback **allowed** — UI never blank during local work | `ALLOW_MOCK_FALLBACK=false` |
| `production` | fallback **disabled** — empty/error snapshot shows honest state | `ALLOW_MOCK_FALLBACK=true` |

In production, SSH failures and empty snapshots surface as empty feeds with
a clear error notice — mock data is never injected silently.

---

## Available Routes

| Route | Description |
|-------|-------------|
| `GET /` | Homepage — hero + feature overview |
| `GET /dashboard` | Dashboard — module status and roadmap view |
| `GET /signals` | Signal feed — source status dot, metadata bar, per-status notices |
| `GET /health` | Basic health check — service identity + signal source config summary |
| `GET /health/signals` | Signal source config detail — timeout, host, key, command |

### `/health` response

```json
{
  "status":      "ok",
  "service":     "AlphaForgeAI",
  "version":     "0.3.1",
  "environment": "development",
  "signals": {
    "source":              "local_snapshot",
    "allow_mock_fallback": true,
    "sentinel_configured": false
  }
}
```

### `/health/signals` response (Sentinel configured)

```json
{
  "source":              "sentinel_ssh",
  "allow_mock_fallback": false,
  "sentinel": {
    "configured":       true,
    "host":             "192.168.1.40",
    "user":             "kkers",
    "key_path_set":     true,
    "timeout_seconds":  18,
    "strict_host_key":  false,
    "command":          "python3 /data/ai-trading-bot/snapshot.py"
  }
}
```

---

## Folder Structure

```
AlphaForgeAI/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py            # v0.3.1 — signal_source, fallback, Sentinel SSH + timeout
│   ├── domain/
│   │   ├── __init__.py
│   │   └── signals.py           # Signal Pydantic model
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── signal_repository.py # SignalSnapshot (status, error_message), loaders, dispatcher
│   ├── services/
│   │   ├── __init__.py
│   │   └── signal_service.py    # env-aware fallback, status="fallback"
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── pages.py             # /, /health, /health/signals
│   │   ├── dashboard.py
│   │   └── signals.py           # snapshot_status + error_message passed to template
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── dashboard.html
│   │   └── signals.html         # status dot, per-status notices (ok/empty/error/fallback)
│   └── static/
│       └── css/
│           └── styles.css       # .source-status-dot, .src-ok/warn/error, .snapshot-notice-error
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
| `SENTINEL_SSH_TIMEOUT` | `18` | Subprocess + ConnectTimeout in seconds |
| `SENTINEL_SSH_STRICT_HOST_KEY` | `false` | Set `true` to enable SSH known-hosts checking |
| `SENTINEL_SNAPSHOT_COMMAND` | `python3 /data/ai-trading-bot/snapshot.py` | Command run on Sentinel |

```powershell
# Local development (default — no env vars needed)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Simulate production (no mock fallback, honest empty/error states)
$env:ENVIRONMENT         = "production"
$env:ALLOW_MOCK_FALLBACK = "false"
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Sentinel SSH source (live model output)
$env:SIGNAL_SOURCE             = "sentinel_ssh"
$env:SENTINEL_SSH_HOST         = "192.168.1.40"
$env:SENTINEL_SSH_KEY_PATH     = "C:/Users/josh/.ssh/id_rsa"
$env:SENTINEL_SSH_TIMEOUT      = "18"
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test SSH failure handling (missing host → config error notice in UI)
$env:SIGNAL_SOURCE     = "sentinel_ssh"
$env:SENTINEL_SSH_HOST = ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Roadmap Summary

- **Phase 1** ✅ Foundation: FastAPI skeleton, branded homepage, docs
- **Phase 1.5** ✅ Structure: config, base layout, dashboard stub, signal domain model
- **Phase 2** ✅ Signal feed: typed service layer, working `/signals` page
- **Phase 2.5** ✅ Repository layer: `signal_repository.py` loads from `data/signals_snapshot.json`
- **Phase 2.6** ✅ Architecture cleanup: v0.3.0, metadata envelope, env-aware fallback, source UI
- **Phase 2.7** ✅ Sentinel SSH source: `sentinel_ssh` loader, config fields, source dispatcher
- **Phase 2.8** ✅ Hardening: status fields, error notices, configurable timeout, health endpoints
- **Phase 3** — Content pipeline: AI-written daily market posts via N8N + LLM
- **Phase 3** — Live signals: set `SIGNAL_SOURCE=sentinel_ssh` + `SENTINEL_SSH_HOST` to go live
- **Phase 4** — Onchain explorer: L/S ratio, OI, netflow charts
- **Phase 5** — Monetisation: auth, Stripe, email digest

See [`docs/roadmap.md`](docs/roadmap.md) for full detail.

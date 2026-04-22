# AlphaForgeAI

**AI-assisted crypto signal and market insight platform.**

Built on a real XGBoost trading system, AlphaForgeAI surfaces quantitative signals, onchain data context, and daily AI-written market explainers — for traders who want edge without the noise.

---

## Project Overview

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Templates | Jinja2 |
| Styling | Vanilla CSS (dark theme) |
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

## Available Routes

| Route | Description |
|-------|-------------|
| `GET /` | Homepage |
| `GET /health` | Health check — returns `{"status": "ok"}` |

---

## Folder Structure

```
AlphaForgeAI/
├── app/
│   ├── main.py              # FastAPI app init, mounts static files, includes routers
│   ├── routes/
│   │   ├── __init__.py
│   │   └── pages.py         # Homepage (/) and health (/health) routes
│   ├── templates/
│   │   └── index.html       # Jinja2 homepage template
│   └── static/
│       └── css/
│           └── styles.css   # Dark theme, branded CSS
├── docs/
│   ├── product-brief.md     # What AlphaForgeAI is and where it's going
│   └── roadmap.md           # Phase-by-phase build plan
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Roadmap Summary

- **Phase 1** — Foundation (current): FastAPI skeleton, branded homepage, docs
- **Phase 2** — Content pipeline: AI-written daily market posts via N8N + LLM
- **Phase 3** — Signal dashboard: live XGBoost signals, read-only public view
- **Phase 4** — Onchain explorer: L/S ratio, OI, netflow charts
- **Phase 5** — Monetisation: auth, Stripe subscriptions, email digest

See [`docs/roadmap.md`](docs/roadmap.md) for full detail.

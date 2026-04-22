from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.core.config import settings
from app.services.signal_service import get_signals

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/signals", response_class=HTMLResponse)
async def signal_feed(request: Request):
    signals = get_signals()
    return templates.TemplateResponse("signals.html", {
        "request":      request,
        "active_page":  "signals",
        "app_version":  settings.app_version,
        "environment":  settings.environment,
        "signals":      signals,
        "total":        len(signals),
        "long_count":   sum(1 for s in signals if s.direction == "LONG"),
        "short_count":  sum(1 for s in signals if s.direction == "SHORT"),
        "flat_count":   sum(1 for s in signals if s.direction == "FLAT"),
    })

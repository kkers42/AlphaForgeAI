from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.core.config import settings
from app.services.confidence_calibration import (
    confidence_css_class,
    confidence_label,
    confidence_percent,
    normalize_percent,
)
from app.services.signal_service import get_signals
from app.services.signal_staleness import evaluate_signal_staleness

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
templates.env.filters["confidence_percent"] = confidence_percent
templates.env.filters["confidence_label"] = confidence_label
templates.env.filters["confidence_css_class"] = confidence_css_class
templates.env.filters["importance_percent"] = normalize_percent


@router.get("/signals", response_class=HTMLResponse)
async def signal_feed(request: Request):
    snapshot = get_signals()
    staleness = evaluate_signal_staleness(snapshot.generated_at)
    signals = []
    if not (staleness.is_stale and staleness.action == "filter"):
        signals = snapshot.signals

    # Format generated_at for display ("2026-04-22T12:00:00Z" → "2026-04-22 12:00 UTC")
    generated_at_display: str | None = None
    if snapshot.generated_at:
        generated_at_display = (
            snapshot.generated_at
            .replace("T", " ")
            .replace("Z", " UTC")
            # Trim seconds if present ("12:00:00 UTC" → "12:00 UTC")
            if "T" in snapshot.generated_at
            else snapshot.generated_at
        )
        # Trim trailing ":00 UTC" seconds for cleaner display
        if generated_at_display and generated_at_display.endswith(":00 UTC"):
            generated_at_display = generated_at_display[:-7] + " UTC"

    return templates.TemplateResponse("signals.html", {
        "request":            request,
        "active_page":        "signals",
        "app_version":        settings.app_version,
        "environment":        settings.environment,
        # signal data
        "signals":            signals,
        "total":              len(signals),
        "long_count":         sum(1 for s in signals if s.direction == "LONG"),
        "short_count":        sum(1 for s in signals if s.direction == "SHORT"),
        "flat_count":         sum(1 for s in signals if s.direction == "FLAT"),
        # snapshot metadata
        "data_source":        snapshot.source,
        "generated_at":       generated_at_display,
        "model_version":      snapshot.model_version,
        "used_mock_fallback": snapshot.used_mock_fallback,
        "signals_stale":      staleness.is_stale,
        "stale_action":       staleness.action,
        "stale_after_hours":  staleness.stale_after_hours,
        # observability
        "snapshot_status":    snapshot.status,
        "error_message":      snapshot.error_message,
    })

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
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
log = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
templates.env.filters["confidence_percent"] = confidence_percent
templates.env.filters["confidence_label"] = confidence_label
templates.env.filters["confidence_css_class"] = confidence_css_class
templates.env.filters["importance_percent"] = normalize_percent


@router.get("/api/signals/snapshot")
async def signals_snapshot():
    """Public JSON endpoint — top signals by confidence for n8n and external consumers."""
    snapshot  = get_signals()
    staleness = evaluate_signal_staleness(snapshot.generated_at)
    signals   = []
    if not (staleness.is_stale and staleness.action == "filter"):
        signals = sorted(snapshot.signals, key=lambda s: getattr(s, "confidence", 0) or 0, reverse=True)

    return JSONResponse({
        "generated_at": snapshot.generated_at,
        "signal_count":  len(signals),
        "is_stale":      staleness.is_stale,
        "signals": [
            {
                "symbol":     s.symbol,
                "direction":  s.direction,
                "confidence": round(s.confidence, 4),
                "regime":     s.regime,
                "timeframe":  s.timeframe,
                "thesis":     s.thesis,
                "confluence": s.confluence,
            }
            for s in signals
        ],
    })


@router.get("/signals", response_class=HTMLResponse)
async def signal_feed(request: Request):
    snapshot  = get_signals()
    staleness = evaluate_signal_staleness(snapshot.generated_at)
    signals   = []
    if not (staleness.is_stale and staleness.action == "filter"):
        signals = snapshot.signals

    # Sort by confidence desc (highest-conviction signals first)
    signals = sorted(signals, key=lambda s: getattr(s, "confidence", 0) or 0, reverse=True)

    # Apply display limit — ?limit=all bypasses the cap
    limit_param   = request.query_params.get("limit", "").strip().lower()
    show_all      = limit_param == "all" or settings.signal_display_limit == 0
    total_signals = len(signals)
    if not show_all and settings.signal_display_limit > 0:
        signals = signals[:settings.signal_display_limit]
    limit_active  = not show_all and total_signals > len(signals)

    log.info(
        "event=signal_feed_render signal_count=%d total=%d limit=%d source=%s status=%s "
        "used_mock_fallback=%s generated_at=%s model_version=%s",
        len(signals),
        total_signals,
        settings.signal_display_limit,
        snapshot.source,
        snapshot.status,
        snapshot.used_mock_fallback,
        snapshot.generated_at or "unknown",
        snapshot.model_version or "unknown",
    )

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

    return templates.TemplateResponse(request, "signals.html", {
        "active_page":        "signals",
        "app_version":        settings.app_version,
        "environment":        settings.environment,
        # signal data
        "signals":            signals,
        "total":              len(signals),
        "total_available":    total_signals,
        "limit_active":       limit_active,
        "display_limit":      settings.signal_display_limit,
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

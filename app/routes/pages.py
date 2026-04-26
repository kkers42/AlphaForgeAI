from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.repositories.signal_repository import get_signals_from_file

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def _signal_engine_health() -> dict:
    """
    Lightweight signal engine health for Cloud Run and uptime monitors.

    This does local file inspection only for the file provider. It never probes
    Sentinel SSH or performs network work.
    """
    provider = settings.signal_provider
    file_path = settings.signal_file_path
    snapshot_path = Path(file_path) if file_path else None
    snapshot_present = bool(snapshot_path and snapshot_path.exists())

    engine: dict = {
        "provider": provider,
        "healthy": True,
        "status": "ok",
        "snapshot": {
            "path": file_path,
            "present": snapshot_present,
            "status": "not_required" if provider == "mock" else "unknown",
        },
        "last_generated_at": None,
        "signal_count": None,
        "schema_version": None,
        "freshness": {
            "status": "unknown",
            "age_seconds": None,
            "warn_after_hours": settings.signal_freshness_warn_hours,
        },
        "refresh_job": {
            "configured": False,
            "status": "not_configured",
        },
        "error": None,
    }

    if provider == "mock":
        return engine

    if provider != "file":
        engine["status"] = "configured"
        engine["snapshot"]["status"] = "not_checked"
        return engine

    snapshot = get_signals_from_file()
    engine["snapshot"]["status"] = snapshot.status
    engine["last_generated_at"] = snapshot.generated_at
    engine["signal_count"] = (
        snapshot.signal_count
        if snapshot.signal_count is not None
        else len(snapshot.signals)
    )
    engine["schema_version"] = snapshot.schema_version

    generated_at = _parse_utc_timestamp(snapshot.generated_at)
    if generated_at:
        age_seconds = int((datetime.now(timezone.utc) - generated_at).total_seconds())
        engine["freshness"]["age_seconds"] = max(age_seconds, 0)
        engine["freshness"]["status"] = (
            "stale"
            if age_seconds > settings.signal_freshness_warn_hours * 3600
            else "fresh"
        )
    elif snapshot_present:
        engine["freshness"]["status"] = "unknown"

    if snapshot.status == "ok" and snapshot.signals:
        return engine

    engine["healthy"] = settings.allow_mock_fallback
    engine["status"] = "degraded" if settings.allow_mock_fallback else "unhealthy"
    engine["error"] = snapshot.error_message
    return engine


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {
        "request":      request,
        "active_page":  "home",
        "app_version":  settings.app_version,
        "environment":  settings.environment,
    })


@router.get("/health", response_class=JSONResponse)
async def health():
    """
    Basic health check.  Fast local checks only — no SSH.

    Returns service identity, version, environment, and a lightweight
    summary of the signal source configuration.
    """
    signal_engine = _signal_engine_health()
    return {
        "status":      "ok" if signal_engine["healthy"] else "unhealthy",
        "service":     settings.app_name,
        "version":     settings.app_version,
        "environment": settings.environment,
        "signals": {
            "provider":            settings.signal_provider,
            "source":              settings.signal_source,
            "file_path_set":       bool(settings.signal_file_path),
            "allow_mock_fallback": settings.allow_mock_fallback,
            "sentinel_configured": settings.sentinel_configured,
        },
        "signal_engine": signal_engine,
    }


@router.get("/health/signals", response_class=JSONResponse)
async def health_signals():
    """
    Signal source configuration health check.  Fast — config only, no SSH.

    Useful for diagnosing which source is active, whether Sentinel is
    configured, and what timeout is in use.  Does not perform a live probe.
    """
    sentinel_info: dict = {
        "configured": settings.sentinel_configured,
    }
    if settings.sentinel_configured:
        sentinel_info.update({
            "host":             settings.sentinel_ssh_host,
            "user":             settings.sentinel_ssh_user,
            "key_path_set":     bool(settings.sentinel_ssh_key_path),
            "timeout_seconds":  settings.sentinel_ssh_timeout_seconds,
            "strict_host_key":  settings.sentinel_ssh_strict_host_key_checking,
            "command":          settings.sentinel_snapshot_command,
        })

    signal_engine = _signal_engine_health()
    return {
        "provider":            settings.signal_provider,
        "file_path_set":       bool(settings.signal_file_path),
        "source":              settings.signal_source,
        "allow_mock_fallback": settings.allow_mock_fallback,
        "engine":              signal_engine,
        "sentinel":            sentinel_info,
    }

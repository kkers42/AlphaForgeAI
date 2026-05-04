import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.core.config import settings

router = APIRouter()
log = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


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
    Basic health check.  Fast — no I/O, no SSH.

    Returns service identity, version, environment, and a lightweight
    summary of the signal source configuration.
    """
    log.info(
        "event=health_check version=%s environment=%s provider=%s",
        settings.app_version,
        settings.environment,
        settings.signal_provider,
    )
    return {
        "status":      "ok",
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
    }


@router.get("/health/signals", response_class=JSONResponse)
async def health_signals():
    """
    Signal source configuration health check.  Fast — config only, no SSH.

    Useful for diagnosing which source is active, whether Sentinel is
    configured, and what timeout is in use.  Does not perform a live probe.
    """
    log.info(
        "event=health_signals_check provider=%s sentinel_configured=%s",
        settings.signal_provider,
        settings.sentinel_configured,
    )
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

    return {
        "provider":            settings.signal_provider,
        "file_path_set":       bool(settings.signal_file_path),
        "source":              settings.signal_source,
        "allow_mock_fallback": settings.allow_mock_fallback,
        "sentinel":            sentinel_info,
    }

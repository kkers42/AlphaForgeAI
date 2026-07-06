"""Whale alert routes — ingest from n8n + serve public API."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.services.gcs_whale_alerts import get_events, ingest_events

router  = APIRouter()
log     = logging.getLogger(__name__)
_bearer = HTTPBearer()

_REQUIRED_FIELDS = {"transaction_hash", "symbol", "amount", "amount_usd", "timestamp", "from_owner_type", "to_owner_type"}


def _require_whale_api_key(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    key = settings.whale_alerts_ingest_api_key
    if not key:
        log.error("event=whale_ingest_rejected reason=api_key_not_configured")
        raise HTTPException(status_code=503, detail="Whale alert ingest endpoint not configured")
    if creds.credentials != key:
        log.warning("event=whale_ingest_rejected reason=invalid_api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/api/whale-alerts/ingest", dependencies=[Depends(_require_whale_api_key)])
async def ingest_whale_alerts(request: Request) -> dict:
    """
    Accept whale alert events from n8n and persist to GCS.
    Caller must supply Authorization: Bearer <WHALE_ALERTS_INGEST_API_KEY>.

    Expected body:
      { "schema_version": 1, "events": [ <event>, ... ] }

    Each event requires: transaction_hash, symbol, amount, amount_usd, timestamp,
                         from_owner_type, to_owner_type
    Optional: blockchain, from_address, to_address, url, alert_type
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    if raw.get("schema_version") != 1:
        raise HTTPException(status_code=422, detail="Missing or invalid schema_version (expected 1)")

    events = raw.get("events", [])
    if not events:
        raise HTTPException(status_code=422, detail="No events in payload")

    valid = [e for e in events if isinstance(e, dict) and _REQUIRED_FIELDS.issubset(e.keys())]
    if not valid:
        raise HTTPException(
            status_code=422,
            detail=f"No valid events (required fields: {', '.join(sorted(_REQUIRED_FIELDS))})",
        )

    added, total = ingest_events(valid, settings.gcs_whale_alerts_bucket)
    log.info("event=whale_alerts_ingested added=%d total=%d", added, total)
    return {"ok": True, "added": added, "total": total, "ts": datetime.now(timezone.utc).isoformat()}


# ── Public API ────────────────────────────────────────────────────────────────

@router.get("/api/whale-alerts")
async def get_whale_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    asset: str = Query(default=None),
) -> dict:
    """Return recent whale alert events as JSON."""
    events = get_events(settings.gcs_whale_alerts_bucket, limit=limit, asset=asset)
    return {
        "total": len(events),
        "events": events,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

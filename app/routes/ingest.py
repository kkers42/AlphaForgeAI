"""Signal ingest endpoint — accepts pushed snapshots from the Sentinel AI bot."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pathlib import Path

from app.core.config import settings
from app.repositories.signal_repository import (
    LATEST_SNAPSHOT_PATH,
    validate_snapshot_payload,
    write_snapshot_atomic,
)

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)
_bearer = HTTPBearer()


def _require_api_key(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    key = settings.signal_ingest_api_key
    if not key:
        log.error("event=ingest_rejected reason=api_key_not_configured")
        raise HTTPException(status_code=503, detail="Ingest endpoint not configured")
    if creds.credentials != key:
        log.warning("event=ingest_rejected reason=invalid_api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/signals/ingest", dependencies=[Depends(_require_api_key)])
async def ingest_signals(request: Request) -> dict:
    """
    Accept a v1 snapshot from the Sentinel AI bot and persist it.

    The caller must supply ``Authorization: Bearer <SIGNAL_INGEST_API_KEY>``.
    The payload must be a valid v1 snapshot envelope (schema_version=1).
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    try:
        snapshot = validate_snapshot_payload(raw, "sentinel_push", require_schema=True)
    except ValueError as exc:
        log.warning("event=ingest_rejected reason=schema_error detail=%s", exc)
        raise HTTPException(status_code=422, detail=str(exc))

    dest = Path(settings.signal_file_path) if settings.signal_file_path else LATEST_SNAPSHOT_PATH
    try:
        write_snapshot_atomic(raw, dest)
    except Exception as exc:
        log.error("event=ingest_write_failed error=%s", exc)
        raise HTTPException(status_code=500, detail="Failed to persist snapshot")

    log.info(
        "event=signal_ingest signal_count=%d model=%s generated_at=%s",
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return {"accepted": True, "signal_count": len(snapshot.signals)}

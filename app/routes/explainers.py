"""Explainer routes — ingest from Engine + serve to dashboard."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.services import gcs_explainers

router = APIRouter(prefix="/api/explainers")
log = logging.getLogger(__name__)
_bearer = HTTPBearer()


def _require_api_key(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    key = settings.explainer_ingest_api_key
    if not key:
        log.error("event=explainer_ingest_rejected reason=api_key_not_configured")
        raise HTTPException(status_code=503, detail="Explainer ingest endpoint not configured")
    if creds.credentials != key:
        log.warning("event=explainer_ingest_rejected reason=invalid_api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/ingest", dependencies=[Depends(_require_api_key)])
async def ingest_explainers(request: Request) -> dict:
    """
    Accept a Phase 3 explainer payload from the AlphaForgeAI Engine and
    persist it to GCS. Caller must supply Authorization: Bearer <EXPLAINER_INGEST_API_KEY>.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    if raw.get("schema_version") != 1:
        raise HTTPException(status_code=422, detail="Missing or invalid schema_version (expected 1)")

    explainers = raw.get("explainers", [])
    if not explainers:
        raise HTTPException(status_code=422, detail="No explainers in payload")

    ok = gcs_explainers.upload_explainers(raw, bucket_name=settings.gcs_explainers_bucket)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to persist explainers to GCS")

    log.info(
        "event=explainer_ingest total=%d tone=%s generated_at=%s",
        len(explainers),
        raw.get("summary", {}).get("tone", "unknown"),
        raw.get("generated_at", "unknown"),
    )
    return {"accepted": True, "explainer_count": len(explainers)}


@router.get("")
async def get_explainers() -> dict:
    """Return the latest cached explainer payload from GCS."""
    payload = gcs_explainers.download_explainers(bucket_name=settings.gcs_explainers_bucket)
    if not payload:
        raise HTTPException(status_code=404, detail="No explainers available yet")
    return payload

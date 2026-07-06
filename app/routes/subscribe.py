"""Email subscription endpoint."""

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.gcs_subscribers import add_subscriber

router = APIRouter(prefix="/api")
log    = logging.getLogger(__name__)


@router.post("/subscribe")
async def subscribe(request: Request, email: str = Form(...)):
    """Accept an email subscription from the landing page CTA."""
    source = request.headers.get("referer", "direct")
    ok, status = add_subscriber(
        email       = email,
        bucket_name = settings.gcs_subscribers_bucket,
        source      = "landing",
    )

    if status == "invalid":
        return JSONResponse({"ok": False, "message": "Please enter a valid email address."}, status_code=400)
    if status == "error":
        return JSONResponse({"ok": False, "message": "Something went wrong. Please try again."}, status_code=500)
    if status == "duplicate":
        return JSONResponse({"ok": True, "message": "You're already on the list!"})

    return JSONResponse({"ok": True, "message": "You're in! We'll be in touch."})

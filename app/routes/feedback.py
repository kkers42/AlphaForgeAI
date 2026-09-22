import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.config import settings

router = APIRouter()
log = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

VALID_ENVIRONMENTS = {"testnet", "live"}
VALID_CATEGORIES = {"bug", "issue", "other"}

_CATEGORY_LABELS = {"bug": "bug", "issue": "issue", "other": "other"}
_ENV_LABELS = {"testnet": "env:testnet", "live": "env:live"}


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_form(request: Request):
    return templates.TemplateResponse(request, "feedback.html", {
        "active_page":  "feedback",
        "app_version":  settings.app_version,
        "environment":  settings.environment,
    })


@router.post("/api/feedback", response_class=JSONResponse)
async def submit_feedback(
    environment: str = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    contact: str = Form(""),
):
    environment = environment.strip().lower()
    category = category.strip().lower()
    title = title.strip()
    description = description.strip()
    contact = contact.strip()

    if environment not in VALID_ENVIRONMENTS:
        return JSONResponse({"ok": False, "message": "Invalid environment."}, status_code=400)
    if category not in VALID_CATEGORIES:
        return JSONResponse({"ok": False, "message": "Invalid category."}, status_code=400)
    if not title or not description:
        return JSONResponse({"ok": False, "message": "Title and description are required."}, status_code=400)

    if not settings.feedback_configured:
        log.error("event=feedback_submit_failed reason=no_github_token")
        return JSONResponse(
            {"ok": False, "message": "Bug reporter isn't configured yet (missing GITHUB_FEEDBACK_TOKEN)."},
            status_code=503,
        )

    issue_title = f"[{environment}] {category}: {title}"
    body_lines = [
        f"**Environment:** {environment}",
        f"**Category:** {category}",
        "",
        description,
    ]
    if contact:
        body_lines += ["", f"**Reporter contact:** {contact}"]
    body_lines += ["", "_Filed via the in-app bug reporter._"]
    issue_body = "\n".join(body_lines)

    labels = [_CATEGORY_LABELS[category], _ENV_LABELS[environment]]

    owner_repo = settings.github_feedback_repo
    url = f"https://api.github.com/repos/{owner_repo}/issues"
    headers = {
        "Authorization": f"Bearer {settings.github_feedback_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers, json={
                "title": issue_title,
                "body": issue_body,
                "labels": labels,
            })
    except httpx.HTTPError as e:
        log.error("event=feedback_github_request_failed error=%s", e)
        return JSONResponse({"ok": False, "message": "Could not reach GitHub. Try again shortly."}, status_code=502)

    if resp.status_code >= 300:
        # Retry once without labels — a label that doesn't exist yet on the repo
        # can cause some GitHub configurations to reject the whole request.
        log.warning("event=feedback_github_create_failed status=%s body=%s", resp.status_code, resp.text[:500])
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp2 = await client.post(url, headers=headers, json={
                    "title": issue_title,
                    "body": issue_body,
                })
        except httpx.HTTPError as e:
            log.error("event=feedback_github_retry_failed error=%s", e)
            return JSONResponse({"ok": False, "message": "Could not reach GitHub. Try again shortly."}, status_code=502)

        if resp2.status_code >= 300:
            log.error("event=feedback_github_create_failed_final status=%s body=%s", resp2.status_code, resp2.text[:500])
            return JSONResponse({"ok": False, "message": "GitHub rejected the report. Please try again later."}, status_code=502)
        resp = resp2

    data = resp.json()
    log.info("event=feedback_submitted environment=%s category=%s issue=%s", environment, category, data.get("html_url"))
    return {"ok": True, "message": "Thanks — filed as a GitHub issue.", "issue_url": data.get("html_url")}

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.core.config import settings

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request":      request,
        "active_page":  "dashboard",
        "app_version":  settings.app_version,
        "environment":  settings.environment,
    })

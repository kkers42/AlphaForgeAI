from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.core.config import settings

router = APIRouter()

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
    return {
        "status":      "ok",
        "service":     settings.app_name,
        "version":     settings.app_version,
        "environment": settings.environment,
    }

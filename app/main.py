from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import settings
from app.routes import ingest, pages, dashboard, signals, explainers, news, blog, subscribe

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title=settings.app_name,
    description="AI-assisted crypto signal and market insight platform",
    version=settings.app_version,
    debug=settings.debug,
)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Route modules
app.include_router(pages.router)
app.include_router(dashboard.router)
app.include_router(signals.router)
app.include_router(ingest.router)
app.include_router(explainers.router)
app.include_router(news.router)
app.include_router(blog.router)
app.include_router(subscribe.router)

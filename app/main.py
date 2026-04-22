from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.routes import pages

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="AlphaForgeAI",
    description="AI-assisted crypto signal and market insight platform",
    version="0.1.0",
)

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Route modules
app.include_router(pages.router)

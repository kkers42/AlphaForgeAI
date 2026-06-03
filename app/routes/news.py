"""News routes — ingest from n8n + serve to frontend."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.services import gcs_news

router   = APIRouter()
log      = logging.getLogger(__name__)
_bearer  = HTTPBearer()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _format_pub_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return iso


templates.env.filters["format_pub_time"] = _format_pub_time


def _require_news_api_key(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    key = settings.news_ingest_api_key
    if not key:
        log.error("event=news_ingest_rejected reason=api_key_not_configured")
        raise HTTPException(status_code=503, detail="News ingest endpoint not configured")
    if creds.credentials != key:
        log.warning("event=news_ingest_rejected reason=invalid_api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/api/news/ingest", dependencies=[Depends(_require_news_api_key)])
async def ingest_news(request: Request) -> dict:
    """
    Accept a news payload from n8n and persist to GCS.
    Caller must supply Authorization: Bearer <NEWS_INGEST_API_KEY>.

    Expected body:
      { "schema_version": 1, "items": [ <article>, ... ] }

    Each article requires: title, source, url, published_at, summary.
    Optional: category, assets (list), sentiment.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    if raw.get("schema_version") != 1:
        raise HTTPException(
            status_code=422,
            detail="Missing or invalid schema_version (expected 1)",
        )

    items = raw.get("items", [])
    if not items:
        raise HTTPException(status_code=422, detail="No items in payload")

    required = {"title", "source", "url", "published_at", "summary"}
    valid = [
        item for item in items
        if isinstance(item, dict) and required.issubset(item.keys())
    ]
    if not valid:
        raise HTTPException(
            status_code=422,
            detail="No valid items (missing required fields: title, source, url, published_at, summary)",
        )

    added, total = gcs_news.ingest_articles(valid, bucket_name=settings.gcs_news_bucket)
    log.info(
        "event=news_ingest received=%d valid=%d added=%d total=%d",
        len(items), len(valid), added, total,
    )
    return {"accepted": True, "received": len(valid), "added": added, "total": total}


# ── API ───────────────────────────────────────────────────────────────────────

@router.get("/api/news")
async def get_news() -> dict:
    """Return the latest news articles from GCS."""
    payload = gcs_news.download_payload(bucket_name=settings.gcs_news_bucket)
    if not payload:
        return {"articles": [], "total": 0, "generated_at": None}
    return payload


# ── HTML page ────────────────────────────────────────────────────────────────

@router.get("/news", response_class=HTMLResponse)
async def news_page(request: Request):
    payload  = gcs_news.download_payload(bucket_name=settings.gcs_news_bucket)
    articles = payload.get("articles", []) if payload else []
    return templates.TemplateResponse(request, "news.html", {
        "active_page":  "news",
        "app_version":  settings.app_version,
        "environment":  settings.environment,
        "articles":     articles,
        "total":        len(articles),
        "generated_at": payload.get("generated_at") if payload else None,
    })


# ── RSS feed ──────────────────────────────────────────────────────────────────

@router.get("/news/rss.xml")
async def news_rss() -> Response:
    """RSS 2.0 feed of the latest news articles."""
    payload  = gcs_news.download_payload(bucket_name=settings.gcs_news_bucket)
    articles = payload.get("articles", []) if payload else []

    now_rfc   = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items_xml = ""
    for a in articles[:50]:
        try:
            dt      = datetime.fromisoformat(a.get("published_at", "").replace("Z", "+00:00"))
            pub_rfc = dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        except Exception:
            pub_rfc = now_rfc

        title = _xml_escape(a.get("title", ""))
        link  = _xml_escape(a.get("url", ""))
        desc  = _xml_escape(a.get("summary", ""))
        src   = _xml_escape(a.get("source", ""))
        items_xml += (
            f"\n    <item>"
            f"\n      <title>{title}</title>"
            f"\n      <link>{link}</link>"
            f"\n      <description>{desc}</description>"
            f"\n      <pubDate>{pub_rfc}</pubDate>"
            f"\n      <author>{src}</author>"
            f"\n      <guid isPermaLink=\"true\">{link}</guid>"
            f"\n    </item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        '  <channel>\n'
        '    <title>AlphaForgeAI Market News</title>\n'
        '    <link>https://alphaforgeai.com/news</link>\n'
        '    <description>Crypto market intelligence and news summaries from AlphaForgeAI.</description>\n'
        '    <language>en</language>\n'
        f'    <lastBuildDate>{now_rfc}</lastBuildDate>\n'
        '    <ttl>240</ttl>'
        f'{items_xml}\n'
        '  </channel>\n'
        '</rss>'
    )
    return Response(content=xml, media_type="application/rss+xml")


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )

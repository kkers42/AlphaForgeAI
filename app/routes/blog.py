"""Blog routes — ingest from external pipeline + serve to frontend."""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.core.config import settings
from app.services import gcs_blog
from app.services.gcs_blog import slugify

router    = APIRouter()
log       = logging.getLogger(__name__)
_bearer   = HTTPBearer()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _format_pub_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return iso


def _markdown_filter(text: str) -> Markup:
    """
    Lightweight markdown → HTML for blog post bodies.
    Handles: ## headings, **bold**, *italic*, `code`, blank-line paragraphs.
    Uses markupsafe.Markup so Jinja2 does NOT double-escape the output.
    """
    if not text:
        return Markup("")
    try:
        import markdown as md_lib  # type: ignore
        html = md_lib.markdown(
            text,
            extensions=["nl2br", "sane_lists"],
        )
        return Markup(html)
    except ImportError:
        pass

    # Fallback: minimal regex renderer (no external dep needed)
    import html as html_mod
    safe = html_mod.escape(text)

    # ## Heading 2
    safe = re.sub(r"(?m)^## (.+)$", r"<h2>\1</h2>", safe)
    # ### Heading 3
    safe = re.sub(r"(?m)^### (.+)$", r"<h3>\1</h3>", safe)
    # **bold**
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    # *italic*
    safe = re.sub(r"\*(.+?)\*", r"<em>\1</em>", safe)
    # `code`
    safe = re.sub(r"`(.+?)`", r"<code>\1</code>", safe)
    # blank lines → paragraph breaks
    safe = re.sub(r"\n\n+", "</p><p>", safe)
    safe = "<p>" + safe + "</p>"
    # clean up p tags around headings
    safe = re.sub(r"<p>(<h[23]>)", r"\1", safe)
    safe = re.sub(r"(</h[23]>)</p>", r"\1", safe)

    return Markup(safe)


templates.env.filters["format_pub_time"] = _format_pub_time
templates.env.filters["markdown"] = _markdown_filter


def _require_blog_api_key(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    key = settings.blog_ingest_api_key
    if not key:
        log.error("event=blog_ingest_rejected reason=api_key_not_configured")
        raise HTTPException(status_code=503, detail="Blog ingest endpoint not configured")
    if creds.credentials != key:
        log.warning("event=blog_ingest_rejected reason=invalid_api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post("/api/blog/ingest", dependencies=[Depends(_require_blog_api_key)])
async def ingest_blog(request: Request) -> dict:
    """
    Accept a blog post payload and persist to GCS.
    Caller must supply Authorization: Bearer <BLOG_INGEST_API_KEY>.

    Expected body (batch):
      { "schema_version": 1, "posts": [ <post>, ... ] }

    Or a single post dict directly (schema_version optional).

    Each post requires: title, published_at, summary, content.
    Optional: sources (list), assets (list), tags (list), author.
    """
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON")

    # Accept single-post dict OR { schema_version, posts: [...] }
    if isinstance(raw, dict) and "posts" not in raw and "title" in raw:
        # Single post submitted directly
        items = [raw]
    else:
        if raw.get("schema_version") != 1:
            raise HTTPException(
                status_code=422,
                detail="Missing or invalid schema_version (expected 1)",
            )
        items = raw.get("posts", [])
        if not items:
            raise HTTPException(status_code=422, detail="No posts in payload")

    required = {"title", "published_at", "summary", "content"}
    valid = [
        item for item in items
        if isinstance(item, dict) and required.issubset(item.keys())
    ]
    if not valid:
        raise HTTPException(
            status_code=422,
            detail="No valid posts (missing required fields: title, published_at, summary, content)",
        )

    # Ensure every post has a slug
    for post in valid:
        if not post.get("slug"):
            post["slug"] = slugify(post["title"], post["published_at"])
        if not post.get("author"):
            post["author"] = "AlphaForgeAI"

    added, total = gcs_blog.ingest_posts(valid, bucket_name=settings.gcs_blog_bucket)
    log.info(
        "event=blog_ingest received=%d valid=%d added=%d total=%d",
        len(items), len(valid), added, total,
    )
    return {"accepted": True, "added": added, "total": total}


# ── API ───────────────────────────────────────────────────────────────────────

@router.get("/api/blog")
async def get_blog() -> dict:
    """Return the latest blog posts from GCS."""
    payload = gcs_blog.download_payload(bucket_name=settings.gcs_blog_bucket)
    if not payload:
        return {"posts": [], "total": 0, "generated_at": None}
    return payload


# ── HTML pages ────────────────────────────────────────────────────────────────

@router.get("/blog", response_class=HTMLResponse)
async def blog_list_page(request: Request):
    payload = gcs_blog.download_payload(bucket_name=settings.gcs_blog_bucket)
    posts   = payload.get("posts", []) if payload else []
    return templates.TemplateResponse(request, "blog_list.html", {
        "active_page":  "blog",
        "app_version":  settings.app_version,
        "environment":  settings.environment,
        "posts":        posts,
        "total":        len(posts),
        "generated_at": payload.get("generated_at") if payload else None,
    })


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post_page(slug: str, request: Request):
    payload = gcs_blog.download_payload(bucket_name=settings.gcs_blog_bucket)
    posts   = payload.get("posts", []) if payload else []
    post    = next((p for p in posts if p.get("slug") == slug), None)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return templates.TemplateResponse(request, "blog_post.html", {
        "active_page": "blog",
        "app_version": settings.app_version,
        "environment": settings.environment,
        "post":        post,
    })

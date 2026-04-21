import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta

from app.auth import is_authenticated
from app.database import get_stats, get_content_pieces, get_logs

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_week_dates():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


@router.get("", response_class=HTMLResponse)
async def overview(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    stats = get_stats()
    week_dates = _get_week_dates()
    week_posts = {}
    for d in week_dates:
        week_posts[d.isoformat()] = get_content_pieces(scheduled_date=d.isoformat())
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "active": "dashboard",
        "stats": stats, "week_dates": week_dates, "week_posts": week_posts,
    })


@router.get("/review", response_class=HTMLResponse)
async def review(request: Request, status: str = "pending", platform: str = "", category: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    content_type = None
    if platform == "facebook":
        content_type = "social_fb"
    elif platform == "instagram":
        content_type = "social_ig"
    pieces = get_content_pieces(status=status or None, content_type=content_type,
                                 category=category or None, limit=200)
    pieces = [p for p in pieces if p["content_type"] != "blog"]
    return templates.TemplateResponse("review.html", {
        "request": request, "active": "review",
        "pieces": pieces, "current_status": status,
        "current_platform": platform, "current_category": category,
    })


@router.get("/batch-review", response_class=HTMLResponse)
async def batch_review(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    pieces = get_content_pieces(status="pending", limit=200)
    pieces = [p for p in pieces if p["content_type"] != "blog"]
    # Parse caption_variants from JSON string to list for template
    for p in pieces:
        if p.get("caption_variants") and isinstance(p["caption_variants"], str):
            try:
                p["caption_variants_parsed"] = json.loads(p["caption_variants"])
            except (json.JSONDecodeError, TypeError):
                p["caption_variants_parsed"] = []
        else:
            p["caption_variants_parsed"] = []
    return templates.TemplateResponse("batch_review.html", {
        "request": request, "active": "review",
        "pieces": pieces, "pieces_json": json.dumps(pieces, default=str),
    })


@router.get("/calendar", response_class=HTMLResponse)
async def calendar(request: Request, month: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    if month:
        year, m = month.split("-")
        first_day = date(int(year), int(m), 1)
    else:
        today = date.today()
        first_day = date(today.year, today.month, 1)

    if first_day.month == 12:
        next_month = date(first_day.year + 1, 1, 1)
    else:
        next_month = date(first_day.year, first_day.month + 1, 1)
    last_day = next_month - timedelta(days=1)

    all_pieces = get_content_pieces(limit=500)
    month_pieces = {}
    for p in all_pieces:
        sd = p.get("scheduled_date", "")
        if sd and sd[:7] == first_day.isoformat()[:7]:
            month_pieces.setdefault(sd, []).append(p)

    prev_month = (first_day - timedelta(days=1)).replace(day=1)

    return templates.TemplateResponse("calendar.html", {
        "request": request, "active": "calendar",
        "first_day": first_day, "last_day": last_day,
        "month_pieces": month_pieces,
        "prev_month": prev_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
    })


@router.get("/blog", response_class=HTMLResponse)
async def blog_review(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    blogs = get_content_pieces(content_type="blog", limit=50)
    return templates.TemplateResponse("blog_review.html", {
        "request": request, "active": "blog", "blogs": blogs,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    from pathlib import Path
    import json
    social_prompt = Path("prompts/social_media.txt").read_text() if Path("prompts/social_media.txt").exists() else ""
    blog_prompt = Path("prompts/blog_post.txt").read_text() if Path("prompts/blog_post.txt").exists() else ""
    topics = json.loads(Path("config/blog_topics.json").read_text()) if Path("config/blog_topics.json").exists() else []
    return templates.TemplateResponse("settings.html", {
        "request": request, "active": "settings",
        "social_prompt": social_prompt, "blog_prompt": blog_prompt, "topics": topics,
    })


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, event_type: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    logs = get_logs(event_type=event_type or None)
    return templates.TemplateResponse("logs.html", {
        "request": request, "active": "logs",
        "logs": logs, "current_type": event_type,
    })

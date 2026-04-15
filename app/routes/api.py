from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import (
    get_content_pieces, update_content_status, get_db, log_event,
)

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="app/templates")


def _auth_check(request: Request) -> bool:
    return is_authenticated(request)


def _render_card(request: Request, content_id: int) -> HTMLResponse:
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    piece = dict(row) if row else {}
    return templates.TemplateResponse("partials/content_card.html", {"request": request, "piece": piece})


@router.post("/content/{content_id}/approve", response_class=HTMLResponse)
async def approve(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    update_content_status(content_id, "approved")
    log_event("approval", f"Content {content_id} approved")
    return _render_card(request, content_id)


@router.post("/content/{content_id}/reject", response_class=HTMLResponse)
async def reject(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    update_content_status(content_id, "rejected")
    log_event("approval", f"Content {content_id} rejected")
    return _render_card(request, content_id)


@router.post("/content/{content_id}/edit", response_class=HTMLResponse)
async def edit_and_approve(request: Request, content_id: int, body: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    update_content_status(content_id, "approved", edited_body=body)
    log_event("approval", f"Content {content_id} edited and approved")
    return _render_card(request, content_id)


@router.post("/content/approve-all", response_class=HTMLResponse)
async def approve_all(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    pieces = get_content_pieces(status="pending")
    for p in pieces:
        if p["content_type"] != "blog":
            update_content_status(p["id"], "approved")
    log_event("approval", f"Bulk approved {len(pieces)} posts")
    approved = get_content_pieces(status="approved", limit=200)
    approved = [p for p in approved if p["content_type"] != "blog"]
    html_parts = []
    for piece in approved:
        resp = templates.TemplateResponse("partials/content_card.html", {"request": request, "piece": piece})
        html_parts.append(resp.body.decode())
    return HTMLResponse("\n".join(html_parts))


@router.post("/content/{content_id}/regenerate-image", response_class=HTMLResponse)
async def regenerate_image(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if row and row["image_prompt"]:
        from app.services.image_generator import generate_image
        generate_image(content_id, row["content_type"], row["image_prompt"])
    return _render_card(request, content_id)


@router.post("/generate/social", response_class=HTMLResponse)
async def trigger_social_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_weekly_social
    from app.services.image_generator import generate_images_for_batch
    try:
        ids = generate_weekly_social()
        pieces = get_content_pieces(limit=200)
        batch_pieces = [p for p in pieces if p["id"] in ids]
        generate_images_for_batch(ids, batch_pieces)
        return HTMLResponse(
            f'<div class="bg-green-50 text-green-700 p-3 rounded">'
            f'Generated {len(ids)} posts! <a href="/dashboard/review" class="underline">Review them now</a></div>'
        )
    except Exception as e:
        log_event("error", f"Manual generation failed: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Error: {str(e)}</div>')


@router.post("/generate/blog", response_class=HTMLResponse)
async def trigger_blog_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_blog_post
    from app.services.image_generator import generate_image
    from app.database import get_db
    try:
        row_id = generate_blog_post()
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_image(row_id, "blog", row["image_prompt"])
            return HTMLResponse(
                f'<div class="bg-green-50 text-green-700 p-3 rounded">'
                f'Blog post generated! <a href="/dashboard/blog" class="underline">Review it now</a></div>'
            )
        return HTMLResponse('<div class="bg-yellow-50 text-yellow-700 p-3 rounded">No unused blog topics remaining.</div>')
    except Exception as e:
        log_event("error", f"Blog generation failed: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Error: {str(e)}</div>')

import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import (
    get_content_pieces, update_content_status, get_db, log_event,
)

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="app/templates")


def _auth_check(request: Request) -> bool:
    return is_authenticated(request)


@router.get("/content/{content_id}/card", response_class=HTMLResponse)
async def get_card(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    return _render_card(request, content_id)


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
async def edit_content(request: Request, content_id: int, body: str = Form(...), action: str = Form("save")):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    if action == "save_approve":
        update_content_status(content_id, "approved", edited_body=body)
        log_event("approval", f"Content {content_id} edited and approved")
    else:
        update_content_status(content_id, "pending", edited_body=body)
        log_event("approval", f"Content {content_id} text edited")
    return _render_card(request, content_id)


@router.post("/content/{content_id}/select-variant", response_class=HTMLResponse)
async def select_variant(request: Request, content_id: int, variant: int = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    if variant not in (0, 1, 2):
        return HTMLResponse("Invalid variant", status_code=400)
    conn = get_db()
    row = conn.execute("SELECT caption_variants FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row or not row["caption_variants"]:
        return _render_card(request, content_id)
    variants = json.loads(row["caption_variants"])
    chosen_caption = variants[variant].get("caption", "")
    update_content_status(content_id, "pending", body=chosen_caption, selected_variant=variant, edited_body=None)
    return _render_card(request, content_id)


@router.post("/content/{content_id}/select-variant-json")
async def select_variant_json(request: Request, content_id: int):
    if not _auth_check(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    variant = body.get("variant", 0)
    if variant not in (0, 1, 2):
        return JSONResponse({"error": "Invalid variant"}, status_code=400)
    conn = get_db()
    row = conn.execute("SELECT caption_variants FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row or not row["caption_variants"]:
        return JSONResponse({"ok": True})
    variants = json.loads(row["caption_variants"])
    chosen_caption = variants[variant].get("caption", "")
    update_content_status(content_id, "pending", body=chosen_caption, selected_variant=variant, edited_body=None)
    return JSONResponse({"ok": True, "caption": chosen_caption})


@router.get("/content/{content_id}/preview", response_class=HTMLResponse)
async def phone_preview(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    piece = dict(row)
    return templates.TemplateResponse("partials/phone_preview.html", {"request": request, "piece": piece})


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
async def regenerate_image(request: Request, content_id: int, image_prompt: str = Form("")):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if row:
        prompt = image_prompt.strip() if image_prompt.strip() else row["image_prompt"]
        if prompt:
            # Save the new prompt if changed
            if image_prompt.strip() and image_prompt.strip() != row["image_prompt"]:
                update_content_status(content_id, row["status"], image_prompt=prompt)
            from app.services.image_generator import generate_image
            generate_image(content_id, row["content_type"], prompt)
    return _render_card(request, content_id)


@router.post("/generate/social", response_class=HTMLResponse)
async def trigger_social_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_weekly_social
    from app.services.image_generator import generate_images_in_background
    try:
        ids = generate_weekly_social()
        pieces = get_content_pieces(limit=200)
        batch_pieces = [p for p in pieces if p["id"] in ids]
        generate_images_in_background(ids, batch_pieces)
        return HTMLResponse(
            f'<div class="bg-green-50 text-green-700 p-3 rounded">'
            f'Generated {len(ids)} posts! Images are generating in the background. '
            f'<a href="/dashboard/review" class="underline">Review them now</a> — refresh to see images as they appear.</div>'
        )
    except Exception as e:
        log_event("error", f"Manual generation failed: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Error: {str(e)}</div>')


@router.post("/generate/blog", response_class=HTMLResponse)
async def trigger_blog_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_blog_post
    from app.services.image_generator import generate_images_in_background
    from app.database import get_db
    try:
        row_id = generate_blog_post()
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_images_in_background([row_id], [dict(row)])
            return HTMLResponse(
                f'<div class="bg-green-50 text-green-700 p-3 rounded">'
                f'Blog post generated! Image is generating in the background. '
                f'<a href="/dashboard/blog" class="underline">Review it now</a></div>'
            )
        return HTMLResponse('<div class="bg-yellow-50 text-yellow-700 p-3 rounded">No unused blog topics remaining.</div>')
    except Exception as e:
        log_event("error", f"Blog generation failed: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Error: {str(e)}</div>')


@router.get("/buffer/test", response_class=HTMLResponse)
async def test_buffer(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.buffer_service import test_connection
    result = test_connection()
    if result["connected"]:
        profiles_html = "".join(
            f'<li class="text-sm">{p["service"]}: {p["formatted_username"]} (ID: {p["id"]})</li>'
            for p in result["profiles"]
        )
        return HTMLResponse(f'<div class="bg-green-50 text-green-700 p-3 rounded"><p class="font-semibold">Connected!</p><ul class="mt-2">{profiles_html}</ul></div>')
    return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Not connected: {result.get("error", "Unknown error")}</div>')


@router.post("/settings/prompt/{prompt_type}", response_class=HTMLResponse)
async def save_prompt(request: Request, prompt_type: str, prompt: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from pathlib import Path
    filename = "social_media.txt" if prompt_type == "social" else "blog_post.txt"
    Path(f"prompts/{filename}").write_text(prompt)
    log_event("system", f"Updated {prompt_type} prompt template")
    return HTMLResponse(f'<div class="bg-green-50 text-green-700 p-3 rounded">Prompt saved successfully!</div>')


@router.post("/settings/topic/add", response_class=HTMLResponse)
async def add_topic(request: Request, topic: str = Form(...), keyword: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    import json
    from pathlib import Path
    topics_path = Path("config/blog_topics.json")
    topics = json.loads(topics_path.read_text()) if topics_path.exists() else []
    topics.append({"topic": topic, "keyword": keyword, "used": False})
    topics_path.write_text(json.dumps(topics, indent=2))
    return HTMLResponse(f'''
    <div class="flex items-center justify-between py-2 border-b">
        <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-gray-300"></span>
            <span class="text-sm">{topic}</span>
            <span class="text-xs text-gray-400">({keyword})</span>
        </div>
    </div>''')


@router.get("/backup/download")
async def download_backup(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from pathlib import Path
    backup_dir = Path("data/backups")
    backups = sorted(backup_dir.glob("content-*.db"))
    if not backups:
        return HTMLResponse("No backups available", status_code=404)
    latest = backups[-1]
    return FileResponse(str(latest), filename=latest.name, media_type="application/octet-stream")


@router.post("/backup/run", response_class=HTMLResponse)
async def run_backup(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.database import backup_database
    try:
        path = backup_database()
        return HTMLResponse(f'<div class="bg-green-50 text-green-700 p-3 rounded">Backup created: {path}</div>')
    except Exception as e:
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Backup failed: {str(e)}</div>')


@router.get("/retry/jobs")
async def get_retry_jobs(request: Request):
    if not _auth_check(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    from app.database import get_failed_jobs
    jobs = get_failed_jobs()
    return JSONResponse(jobs)


@router.post("/retry/{job_id}/run", response_class=HTMLResponse)
async def run_retry(request: Request, job_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.database import get_db
    conn = get_db()
    job = conn.execute("SELECT * FROM failed_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not job:
        return HTMLResponse("Job not found", status_code=404)
    from app.services.retry_queue import _retry_image, _retry_buffer
    from app.database import update_failed_job
    job = dict(job)
    success = False
    if job["job_type"] == "image_generation":
        success = _retry_image(job["content_id"])
    elif job["job_type"] == "buffer_post":
        success = _retry_buffer(job["content_id"])
    if success:
        update_failed_job(job_id, status="completed", attempts=job["attempts"] + 1)
        return HTMLResponse('<div class="bg-green-50 text-green-700 p-3 rounded">Retry succeeded!</div>')
    else:
        update_failed_job(job_id, attempts=job["attempts"] + 1)
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Retry failed. Will try again automatically.</div>')


@router.post("/retry/clear-exhausted", response_class=HTMLResponse)
async def clear_exhausted(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.database import delete_exhausted_jobs
    delete_exhausted_jobs()
    return HTMLResponse('<div class="bg-green-50 text-green-700 p-3 rounded">Exhausted jobs cleared.</div>')

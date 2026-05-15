import json
from datetime import date, datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import (
    get_content_pieces, update_content_status, get_db, log_event,
)


def _approve_with_date(content_id: int, **kwargs):
    """Approve content and assign today's scheduled_date if missing."""
    conn = get_db()
    row = conn.execute("SELECT scheduled_date FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if row and not row["scheduled_date"]:
        kwargs["scheduled_date"] = date.today().isoformat()
    update_content_status(content_id, "approved", **kwargs)

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
    _approve_with_date(content_id)
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
        _approve_with_date(content_id, edited_body=body)
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
            _approve_with_date(p["id"])
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


@router.post("/content/{content_id}/use-asset", response_class=HTMLResponse)
async def use_marketing_asset(request: Request, content_id: int, asset_ref: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import _resolve_asset
    resolved = _resolve_asset(asset_ref)
    if not resolved:
        return HTMLResponse(
            '<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Asset not found. Check the asset ID.</div>'
        )
    update_content_status(
        content_id, "pending",
        image_url=resolved["url"],
        image_local_path=resolved.get("local_path", ""),
        image_prompt=f"[ASSET:{asset_ref}] {resolved['name']}",
    )
    log_event("asset", f"Applied marketing asset {asset_ref} to content {content_id}")
    return _render_card(request, content_id)


@router.get("/assets/list", response_class=HTMLResponse)
async def list_assets_for_picker(request: Request):
    """Return a lightweight HTML list of available assets for the picker UI."""
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.asset_downloader import load_catalog
    catalog = load_catalog()
    html_parts = []
    for cat in catalog.get("categories", []):
        image_assets = [a for a in cat.get("assets", []) if a["type"] == "image"]
        if not image_assets:
            continue
        html_parts.append(f'<div class="mb-3"><p class="text-xs font-bold text-gray-500 mb-1">{cat["name"]}</p>')
        html_parts.append('<div class="grid grid-cols-4 gap-1">')
        for i, a in enumerate(image_assets):
            ref = f"{cat['id']}:{i}"
            src = a.get("url", "")
            html_parts.append(
                f'<div class="cursor-pointer border-2 border-transparent hover:border-teal rounded overflow-hidden aspect-square" '
                f'data-asset-ref="{ref}" title="{a["name"]}">'
                f'<img src="{src}" alt="{a["name"]}" class="w-full h-full object-cover" loading="lazy">'
                f'</div>'
            )
        html_parts.append('</div></div>')
    return HTMLResponse("\n".join(html_parts))


@router.post("/generate/social", response_class=HTMLResponse)
async def trigger_social_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    import threading

    def _generate_in_background():
        from app.services.content_generator import generate_weekly_social
        try:
            ids = generate_weekly_social()
            log_event("generation", f"Background generation complete: {len(ids)} posts (images pipelined)")
        except Exception as e:
            log_event("error", f"Background generation failed: {str(e)}")

    thread = threading.Thread(target=_generate_in_background, daemon=True)
    thread.start()
    return HTMLResponse(
        '<div class="bg-blue-50 text-blue-700 p-3 rounded">'
        'Content generation started! Posts and images are being created in the background. '
        'Refresh in about 30 seconds to see your new content. '
        '<a href="/dashboard/review" class="underline">Go to Review Queue</a></div>'
    )


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
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Blog generation failed. Please try again.</div>')


@router.post("/generate/content", response_class=HTMLResponse)
async def generate_flexible_content(
    request: Request,
    content_type: str = Form(...),
    topic: str = Form(""),
    guidance: str = Form(""),
):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    import anthropic, re, threading
    from app.config import settings
    from app.database import insert_content_piece
    from pathlib import Path

    type_configs = {
        "blog_article": {"label": "Blog Article", "length": "800-1200 words", "format": "HTML"},
        "email_newsletter": {"label": "Email Newsletter", "length": "300-500 words", "format": "HTML"},
        "email_sequence": {"label": "Email Nurture Sequence", "length": "3-5 emails, 200-300 words each", "format": "JSON array of emails with subject and body_html"},
        "campaign_plan": {"label": "Multi-Channel Campaign Plan", "length": "Detailed plan", "format": "HTML with sections"},
        "linkedin_post": {"label": "LinkedIn Post", "length": "3-5 sentences", "format": "plain text"},
        "twitter_post": {"label": "Twitter/X Post", "length": "under 280 characters", "format": "plain text"},
        "facebook_post": {"label": "Facebook Post", "length": "80-150 words", "format": "plain text"},
        "instagram_post": {"label": "Instagram Post", "length": "80-200 words with line breaks", "format": "plain text"},
        "instagram_reel_script": {"label": "Instagram Reel Script", "length": "30-60 second script", "format": "plain text with timing cues"},
        "google_ad": {"label": "Google Ad Copy", "length": "3 headlines (max 30 chars each) + 2 descriptions (max 90 chars each)", "format": "plain text, list each headline and description on its own line with labels like 'Headline 1:', 'Description 1:'"},
        "facebook_ad": {"label": "Facebook/IG Ad Copy", "length": "Primary text + headline + description", "format": "plain text with labels like 'Primary Text:', 'Headline:', 'Description:'"},
    }

    cfg = type_configs.get(content_type)
    if not cfg:
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Unknown content type: {content_type}</div>')

    prompt_path = Path("prompts/social_media.txt")
    system_prompt = prompt_path.read_text() if prompt_path.exists() else ""

    user_message = f"""Generate a {cfg['label']} for White House Chiropractic's Zerona VZ8 service.

Topic/Focus: {topic if topic else 'Choose the best topic based on seasonal relevance and marketing impact'}
Length: {cfg['length']}
Output format: {cfg['format']}

{('Additional guidance: ' + guidance) if guidance else ''}

Return the content directly. If the format is JSON, return valid JSON. If HTML, return clean HTML. If plain text, return the post text followed by relevant hashtags on a new line."""

    def _generate():
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text.strip()

            # Map to content_type for DB
            db_type_map = {
                "blog_article": "blog",
                "email_newsletter": "email",
                "email_sequence": "email_sequence",
                "campaign_plan": "campaign",
                "linkedin_post": "social_li",
                "twitter_post": "social_tw",
                "facebook_post": "social_fb",
                "instagram_post": "social_ig",
                "instagram_reel_script": "social_ig",
                "google_ad": "ad_google",
                "facebook_ad": "ad_fb",
            }

            from datetime import date
            insert_content_piece({
                "content_type": db_type_map.get(content_type, content_type),
                "category": "education",
                "title": f"{cfg['label']}: {topic[:80]}" if topic else cfg['label'],
                "body": text,
                "status": "pending",
                "scheduled_date": date.today().isoformat(),
                "generation_batch": f"asset_{date.today().isoformat()}",
            })
            log_event("generation", f"Generated {cfg['label']}: {topic[:80] if topic else 'auto-topic'}")
        except Exception as e:
            log_event("error", f"Content generation failed ({cfg['label']}): {e}")

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()

    return HTMLResponse(
        f'<div class="text-sm p-3 bg-green-50 border border-green-200 rounded-lg">'
        f'{cfg["label"]} is being generated in the background. '
        f'<a href="/dashboard/review" class="underline font-medium text-green-700">Check the Review Queue</a> in ~30 seconds.</div>'
    )


@router.post("/generate/blog/custom", response_class=HTMLResponse)
async def trigger_custom_blog(request: Request, topic: str = Form(...), keyword: str = Form(""), guidance: str = Form("")):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_blog_post_custom
    from app.services.image_generator import generate_images_in_background
    from app.database import get_db
    try:
        row_id = generate_blog_post_custom(topic, keyword, guidance)
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_images_in_background([row_id], [dict(row)])
            return HTMLResponse(
                f'<div class="bg-green-50 text-green-700 p-3 rounded">'
                f'Blog post generated! <a href="/dashboard/blog" class="underline font-medium">Refresh to review</a></div>'
            )
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Generation failed.</div>')
    except Exception as e:
        log_event("error", f"Custom blog generation failed: {str(e)}")
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Blog generation failed. Please try again.</div>')


@router.get("/blog/suggest-titles", response_class=HTMLResponse)
async def suggest_blog_titles(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    import anthropic
    from app.config import settings
    from pathlib import Path

    # Load existing topics to avoid duplicates
    topics_path = Path("config/blog_topics.json")
    existing = json.loads(topics_path.read_text()) if topics_path.exists() else []
    existing_titles = [t["topic"] for t in existing]

    # Load recent blog posts
    blogs = get_content_pieces(content_type="blog", limit=20)
    recent_titles = [b["title"] for b in blogs if b.get("title")]

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": f"""You are a content strategist for White House Chiropractic in White House, TN. They offer the Zerona VZ8 cold laser body contouring treatment.

Suggest 6 fresh blog post ideas. Each should be SEO-friendly with a target keyword.

AVOID these existing topics:
{json.dumps(existing_titles + recent_titles, indent=2)}

Focus on seasonal relevance, trending health topics, local community angles, and patient education.

Return valid JSON array:
[
  {{"title": "Blog Title Here", "keyword": "target keyword", "description": "One sentence about the angle/hook"}}
]""",
        }],
    )
    import re
    text = response.content[0].text
    cleaned = re.sub(r"```json\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        suggestions = json.loads(cleaned)
    except json.JSONDecodeError:
        return HTMLResponse('<div class="text-red-600 text-sm p-3">Failed to generate suggestions. Try again.</div>')

    html_parts = []
    for s in suggestions:
        title = s.get("title", "")
        keyword = s.get("keyword", "")
        desc = s.get("description", "")
        html_parts.append(
            f'<div class="p-4 border rounded-lg hover:border-teal transition cursor-pointer bg-white" '
            f'onclick="document.getElementById(\'blog-topic\').value=\'{title.replace(chr(39), chr(92)+chr(39))}\'; '
            f'document.getElementById(\'blog-keyword\').value=\'{keyword.replace(chr(39), chr(92)+chr(39))}\'; '
            f'this.classList.add(\'border-teal\', \'bg-teal/5\'); '
            f'document.querySelectorAll(\'[data-suggestion]\').forEach(el => {{ if(el !== this) el.classList.remove(\'border-teal\', \'bg-teal/5\'); }})" '
            f'data-suggestion>'
            f'<p class="font-medium text-sm text-gray-900">{title}</p>'
            f'<p class="text-xs text-teal mt-1">Keyword: {keyword}</p>'
            f'<p class="text-xs text-gray-500 mt-1">{desc}</p>'
            f'</div>'
        )
    return HTMLResponse(
        '<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">' + "\n".join(html_parts) + '</div>'
    )


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
    return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Not connected. Check your WordPress settings.</div>')


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
        log_event("error", f"Backup failed: {str(e)}")
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Backup failed. Please try again.</div>')


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


@router.post("/content/{content_id}/favorite", response_class=HTMLResponse)
async def toggle_favorite(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT is_favorite FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    if not row:
        conn.close()
        return HTMLResponse("Not found", status_code=404)
    new_val = 0 if row["is_favorite"] else 1
    conn.execute("UPDATE content_pieces SET is_favorite = ? WHERE id = ?", (new_val, content_id))
    conn.commit()
    conn.close()
    return _render_card(request, content_id)


@router.post("/content/{content_id}/repurpose", response_class=HTMLResponse)
async def repurpose_content(request: Request, content_id: int,
                            target_platform: str = Form(...),
                            tone: str = Form("warm_confident")):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    piece = dict(row)
    original_body = piece.get("edited_body") or piece["body"]
    source_platform = "Facebook" if "fb" in piece["content_type"] else "Instagram"
    target_label = "Facebook" if target_platform == "social_fb" else "Instagram"

    tone_map = {
        "fun_friendly": "Fun & Friendly — light, playful, use casual language and humor",
        "warm_confident": "Warm & Confident — approachable but authoritative, the brand's natural voice",
        "clinical_authoritative": "Clinical & Authoritative — professional, data-driven, expert positioning",
    }
    tone_instruction = tone_map.get(tone, tone_map["warm_confident"])

    import anthropic
    from app.config import settings
    from app.database import insert_content_piece
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Adapt this {source_platform} post for {target_label}.

Tone: {tone_instruction}

{target_label} guidelines:
{"- 100-250 words, conversational, can use links" if target_platform == "social_fb" else "- 80-200 words, use line breaks for readability, emoji-friendly, hashtag-heavy"}

Original post:
{original_body}

Return ONLY the adapted caption text with hashtags. Nothing else.""",
            }],
        )
        new_body = response.content[0].text.strip()
    except Exception as e:
        log_event("error", f"Repurpose failed for content {content_id}: {str(e)}")
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Repurpose failed. Please try again.</div>')

    new_id = insert_content_piece({
        "content_type": target_platform,
        "category": piece["category"],
        "title": piece.get("title", ""),
        "body": new_body,
        "hashtags": piece.get("hashtags", ""),
        "image_prompt": piece.get("image_prompt", ""),
        "image_url": piece.get("image_url", ""),
        "image_local_path": piece.get("image_local_path", ""),
        "status": "pending",
        "repurposed_from": content_id,
    })
    log_event("generation", f"Repurposed content {content_id} ({source_platform}) as {target_label} content {new_id}")
    return HTMLResponse(
        f'<div class="bg-green-50 text-green-700 p-3 rounded text-sm">'
        f'Repurposed as {target_label} post #{new_id}. '
        f'<a href="/dashboard/review" class="underline font-medium">Review it now</a></div>'
    )


@router.post("/content/{content_id}/rewrite-tone", response_class=HTMLResponse)
async def rewrite_tone(request: Request, content_id: int, tone: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    piece = dict(row)
    original_body = piece.get("edited_body") or piece["body"]

    tone_map = {
        "fun_friendly": "Fun & Friendly — light, playful, use casual language and humor. Think cheerful wellness brand.",
        "warm_confident": "Warm & Confident — approachable but authoritative. This is the brand's natural voice.",
        "clinical_authoritative": "Clinical & Authoritative — professional, data-driven, expert positioning. Think medical practice.",
    }
    tone_instruction = tone_map.get(tone, tone_map["warm_confident"])

    import anthropic
    from app.config import settings
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Rewrite this social media caption in a different tone. Keep the same topic, key message, and approximate length.

New tone: {tone_instruction}

Original caption:
{original_body}

Return ONLY the rewritten caption text with hashtags. Nothing else.""",
            }],
        )
        new_body = response.content[0].text.strip()
    except Exception as e:
        log_event("error", f"Tone rewrite failed for content {content_id}: {str(e)}")
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Rewrite failed. Please try again.</div>')

    update_content_status(content_id, piece["status"], edited_body=new_body)
    log_event("approval", f"Content {content_id} rewritten with tone: {tone}")
    return _render_card(request, content_id)


@router.post("/content/{content_id}/reschedule")
async def reschedule_content(request: Request, content_id: int):
    if not _auth_check(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    new_date = body.get("date", "")
    if not new_date:
        return JSONResponse({"error": "Missing date"}, status_code=400)
    conn = get_db()
    conn.execute("UPDATE content_pieces SET scheduled_date = ?, updated_at = ? WHERE id = ?",
                 (new_date, datetime.now().isoformat(), content_id))
    conn.commit()
    conn.close()
    log_event("approval", f"Content {content_id} rescheduled to {new_date}")
    return JSONResponse({"ok": True})


@router.post("/content/{content_id}/recycle", response_class=HTMLResponse)
async def recycle_content(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    piece = dict(row)
    if piece["status"] not in ("approved", "posted", "queued"):
        return HTMLResponse("Can only recycle approved or posted content", status_code=400)

    # Call Claude to rewrite the caption
    import anthropic
    from app.config import settings
    from app.database import insert_content_piece
    original_body = piece.get("edited_body") or piece["body"]
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"Rewrite this social media caption with a completely fresh angle. Keep the same topic and key message but change the tone, hook, and structure. Return ONLY the new caption text, nothing else.\n\nOriginal caption: {original_body}",
            }],
        )
        new_body = response.content[0].text.strip()
    except Exception as e:
        log_event("error", f"Recycle failed for content {content_id}: {str(e)}")
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Recycle failed. Please try again.</div>')

    new_id = insert_content_piece({
        "content_type": piece["content_type"],
        "category": piece["category"],
        "title": piece.get("title", ""),
        "body": new_body,
        "hashtags": piece.get("hashtags", ""),
        "image_prompt": piece.get("image_prompt", ""),
        "image_url": piece.get("image_url", ""),
        "image_local_path": piece.get("image_local_path", ""),
        "status": "pending",
        "recycled_from": content_id,
    })
    log_event("generation", f"Recycled content {content_id} as new content {new_id}")
    return HTMLResponse(
        f'<div class="bg-green-50 text-green-700 p-3 rounded">'
        f'Recycled! New post created as #{new_id}. '
        f'<a href="/dashboard/review" class="underline">Review it now</a></div>'
    )


@router.post("/content/{content_id}/send-email", response_class=HTMLResponse)
async def send_content_email(request: Request, content_id: int, email: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Content not found</div>')
    piece = dict(row)
    body_text = piece.get("edited_body") or piece["body"]
    title = piece.get("title") or "Zerona Content"
    hashtags = piece.get("hashtags") or ""

    # Build HTML email
    image_html = ""
    if piece.get("image_url") and piece["image_url"] != "/static/css/placeholder.png":
        image_html = f'<img src="{piece["image_url"]}" alt="" style="max-width:100%;border-radius:8px;margin-bottom:16px;">'

    html_body = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#1B2A4A;">{title}</h2>
        {image_html}
        <div style="white-space:pre-line;line-height:1.6;color:#333;">{body_text}</div>
        {f'<p style="color:#0EA5A0;margin-top:16px;">{hashtags}</p>' if hashtags else ''}
        <hr style="margin-top:24px;border:none;border-top:1px solid #eee;">
        <p style="font-size:12px;color:#999;">Sent from Zerona Content Engine</p>
    </div>"""

    # Try Mailgun first, fall back to SMTP
    from app.config import settings
    from app.services.mailgun_service import is_configured as mg_configured, send_single
    if mg_configured():
        result = send_single(email, title, html_body)
        if result["success"]:
            log_event("send", f"Content {content_id} emailed to {email} via Mailgun")
            return _render_card(request, content_id)
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Email delivery failed. Please try again.</div>')

    # SMTP fallback
    if settings.smtp_user:
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart()
            msg["From"] = settings.smtp_user
            msg["To"] = email
            msg["Subject"] = title
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            log_event("send", f"Content {content_id} emailed to {email} via SMTP")
            return _render_card(request, content_id)
        except Exception as e:
            log_event("error", f"SMTP email failed: {e}")
            return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Email delivery failed. Please try again.</div>')

    return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">No email service configured. Set up Mailgun or SMTP in Settings.</div>')


@router.post("/content/{content_id}/send-buffer", response_class=HTMLResponse)
async def send_content_buffer(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Content not found</div>')
    piece = dict(row)
    from app.config import settings
    if not settings.buffer_access_token:
        return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Buffer not configured. Add your Buffer access token in Settings.</div>')
    from app.services.buffer_service import queue_post
    buffer_id = queue_post(piece)
    if buffer_id:
        update_content_status(content_id, "queued", buffer_post_id=buffer_id)
        log_event("send", f"Content {content_id} queued to Buffer (ID: {buffer_id})")
        return _render_card(request, content_id)
    return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">Buffer queue failed. Check your Buffer profile IDs in Settings.</div>')


@router.post("/content/{content_id}/send-wordpress", response_class=HTMLResponse)
async def send_content_wordpress(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.wordpress_service import publish_blog
    result = publish_blog(content_id)
    if result["success"]:
        return _render_card(request, content_id)
    return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded text-sm">WordPress publish failed. Please try again.</div>')


@router.post("/blog/{content_id}/publish", response_class=HTMLResponse)
async def publish_blog_to_wp(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.wordpress_service import publish_blog
    result = publish_blog(content_id)
    if result["success"]:
        return HTMLResponse(
            f'<div class="bg-green-50 text-green-700 p-3 rounded">'
            f'Published! <a href="{result["url"]}" target="_blank" class="underline">View on WordPress</a></div>'
        )
    return HTMLResponse('<div class="bg-red-50 text-red-600 p-3 rounded">Publish failed. Please try again.</div>')


@router.get("/wordpress/test", response_class=HTMLResponse)
async def test_wordpress(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.wordpress_service import test_wp_connection
    result = test_wp_connection()
    if result["connected"]:
        return HTMLResponse(
            f'<div class="bg-green-50 text-green-700 p-3 rounded">'
            f'Connected to WordPress as {result["username"]} at {result["site_url"]}</div>'
        )
    return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Not connected: {result["error"]}</div>')

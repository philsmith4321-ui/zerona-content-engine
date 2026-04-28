import json
import threading
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.services.asset_downloader import load_catalog, get_asset_counts, download_asset, download_category, download_all

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


@router.get("/marketing-assets", response_class=HTMLResponse)
async def marketing_assets_page(request: Request, category: str = "", asset_type: str = "", search: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    catalog = load_catalog()
    counts = get_asset_counts()

    # Filter categories
    categories = catalog.get("categories", [])
    active_category = None

    if category:
        for cat in categories:
            if cat["id"] == category:
                active_category = cat
                break

    # Filter assets within active category
    filtered_assets = []
    if active_category:
        filtered_assets = list(active_category.get("assets", []))
        if asset_type:
            filtered_assets = [a for a in filtered_assets if a["type"] == asset_type]
        if search:
            term = search.lower()
            filtered_assets = [a for a in filtered_assets if term in a["name"].lower()]

    return templates.TemplateResponse("marketing_assets.html", {
        "request": request,
        "active": "marketing_assets",
        "categories": categories,
        "active_category": active_category,
        "filtered_assets": filtered_assets,
        "counts": counts,
        "current_category": category,
        "current_type": asset_type,
        "current_search": search,
    })


@router.post("/api/assets/download/{category_id}/{asset_index}", response_class=HTMLResponse)
async def download_single_asset(request: Request, category_id: str, asset_index: int):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    path = download_asset(category_id, asset_index)
    if path:
        return HTMLResponse(
            f'<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">Downloaded</span>'
        )
    return HTMLResponse(
        f'<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">Failed</span>'
    )


@router.post("/api/assets/download-category/{category_id}", response_class=HTMLResponse)
async def download_category_assets(request: Request, category_id: str):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    results = download_category(category_id)
    return HTMLResponse(
        f'<div class="text-sm p-3 bg-green-50 border border-green-200 rounded-lg">'
        f'Downloaded: {results["downloaded"]} | Skipped: {results["skipped"]} | Failed: {results["failed"]}'
        f'</div>'
    )


@router.post("/api/assets/download-all", response_class=HTMLResponse)
async def download_all_assets(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    results = download_all()
    return HTMLResponse(
        f'<div class="text-sm p-3 bg-green-50 border border-green-200 rounded-lg">'
        f'Downloaded: {results["downloaded"]} | Skipped: {results["skipped"]} | Failed: {results["failed"]}'
        f'</div>'
    )


@router.post("/api/assets/create-post", response_class=HTMLResponse)
async def create_post_from_asset(
    request: Request,
    asset_name: str = Form(...),
    asset_url: str = Form(...),
    category_id: str = Form(""),
    asset_index: str = Form(""),
    platform: str = Form("instagram"),
    content_category: str = Form("education"),
    use_asset_image: str = Form("yes"),
    custom_image_prompt: str = Form(""),
):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    from app.database import insert_content_piece, log_event
    from app.config import settings
    from datetime import date
    import anthropic

    prompt_path = Path("prompts/social_media.txt")
    system_prompt = prompt_path.read_text() if prompt_path.exists() else ""

    user_message = f"""Write a single social media post for {platform.title()} inspired by this marketing asset:

Asset name: {asset_name}
Content category: {content_category}

Write a compelling caption that would pair well with this image. The image is from the official Erchonia Zerona VZ8 marketing materials.

Return valid JSON with this structure:
{{
  "title": "Short hook/title",
  "captions": [
    {{"tone": "professional", "caption": "Polished, authoritative caption..."}},
    {{"tone": "conversational", "caption": "Friendly, casual caption..."}},
    {{"tone": "story_driven", "caption": "Narrative-style caption with a mini story..."}}
  ],
  "hashtags": "#zerona #bodycontouring ...",
  "cta": "Book your free consultation: [link]"
}}"""

    def _generate():
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            import re
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text
            cleaned = re.sub(r"```json\s*", "", text)
            cleaned = re.sub(r"```\s*$", "", cleaned).strip()
            post = json.loads(cleaned)

            captions_list = post.get("captions", [])
            if captions_list:
                default_body = captions_list[0].get("caption", "")
                caption_variants = json.dumps(captions_list)
            else:
                default_body = post.get("caption", "")
                caption_variants = json.dumps([
                    {"tone": "professional", "caption": default_body},
                    {"tone": "conversational", "caption": default_body},
                    {"tone": "story_driven", "caption": default_body},
                ])

            content_type = "social_ig" if platform == "instagram" else "social_fb"

            piece_data = {
                "content_type": content_type,
                "category": content_category,
                "title": post.get("title", asset_name),
                "body": default_body,
                "hashtags": post.get("hashtags", ""),
                "scheduled_date": date.today().isoformat(),
                "status": "pending",
                "generation_batch": f"asset_{date.today().isoformat()}",
                "caption_variants": caption_variants,
                "selected_variant": 0,
            }

            if use_asset_image == "yes":
                asset_ref = f"{category_id}:{asset_index}" if category_id and asset_index else ""
                piece_data["image_url"] = asset_url
                piece_data["image_prompt"] = f"[ASSET:{asset_ref}] {asset_name}" if asset_ref else f"[ASSET] {asset_name}"
            else:
                piece_data["image_prompt"] = custom_image_prompt or f"Professional wellness-themed image related to: {asset_name}"
                # Generate the image in background
                row_id = insert_content_piece(piece_data)
                from app.services.image_generator import generate_image
                generate_image(row_id, content_type, piece_data["image_prompt"])
                log_event("generation", f"Created post from asset '{asset_name}' with custom image", {"asset": asset_name})
                return

            insert_content_piece(piece_data)
            log_event("generation", f"Created post from asset '{asset_name}'", {"asset": asset_name})

        except Exception as e:
            log_event("error", f"Failed to create post from asset '{asset_name}': {e}")

    thread = threading.Thread(target=_generate, daemon=True)
    thread.start()

    return HTMLResponse(
        '<div class="text-sm p-3 bg-green-50 border border-green-200 rounded-lg">'
        'Post is being created in the background! Caption is generating via AI. '
        '<a href="/dashboard/review" class="underline font-medium text-green-700">Check the Review Queue</a> in ~30 seconds.'
        '</div>'
    )

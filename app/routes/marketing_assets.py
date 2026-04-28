import json
from pathlib import Path

from fastapi import APIRouter, Request
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

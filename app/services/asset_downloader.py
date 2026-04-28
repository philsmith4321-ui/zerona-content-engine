import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.database import get_db, log_event

ASSETS_DIR = Path("media/marketing_assets")
CATALOG_PATH = Path("config/marketing_assets.json")


def load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {"categories": []}
    return json.loads(CATALOG_PATH.read_text())


def save_catalog(catalog: dict):
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))


def _filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    return os.path.basename(parsed.path) or "unknown"


def _category_dir(category_id: str) -> Path:
    d = ASSETS_DIR / category_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_asset_counts() -> dict:
    catalog = load_catalog()
    counts = {}
    total = 0
    downloaded = 0
    for cat in catalog.get("categories", []):
        cat_id = cat["id"]
        assets = cat.get("assets", [])
        cat_downloaded = sum(
            1 for a in assets
            if a.get("local_path") and Path(a["local_path"]).exists()
        )
        counts[cat_id] = {"total": len(assets), "downloaded": cat_downloaded}
        total += len(assets)
        downloaded += cat_downloaded
    counts["_summary"] = {"total": total, "downloaded": downloaded}
    return counts


def download_asset(category_id: str, asset_index: int) -> str | None:
    catalog = load_catalog()
    for cat in catalog["categories"]:
        if cat["id"] != category_id:
            continue
        assets = cat.get("assets", [])
        if asset_index < 0 or asset_index >= len(assets):
            return None
        asset = assets[asset_index]
        url = asset["url"]

        # Skip non-downloadable types
        if asset["type"] == "video":
            return None

        filename = _filename_from_url(url)
        dest_dir = _category_dir(category_id)
        dest_path = dest_dir / filename

        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                dest_path.write_bytes(resp.content)

            asset["local_path"] = str(dest_path)
            asset["file_size"] = len(resp.content)
            save_catalog(catalog)

            log_event("asset_download", f"Downloaded {filename} to {dest_path}")
            return str(dest_path)
        except Exception as e:
            log_event("error", f"Failed to download {url}: {e}")
            return None
    return None


def download_category(category_id: str) -> dict:
    catalog = load_catalog()
    results = {"downloaded": 0, "skipped": 0, "failed": 0}
    for cat in catalog["categories"]:
        if cat["id"] != category_id:
            continue
        for i, asset in enumerate(cat.get("assets", [])):
            if asset["type"] == "video":
                results["skipped"] += 1
                continue
            if asset.get("local_path") and Path(asset["local_path"]).exists():
                results["skipped"] += 1
                continue
            path = download_asset(category_id, i)
            if path:
                results["downloaded"] += 1
            else:
                results["failed"] += 1
    return results


def download_all() -> dict:
    catalog = load_catalog()
    total_results = {"downloaded": 0, "skipped": 0, "failed": 0}
    for cat in catalog["categories"]:
        r = download_category(cat["id"])
        for k in total_results:
            total_results[k] += r[k]
    log_event("asset_download", f"Bulk download complete: {total_results}")
    return total_results

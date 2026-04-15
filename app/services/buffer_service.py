import httpx
from datetime import date
from pathlib import Path
from typing import Optional

from app.config import settings
from app.database import get_content_pieces, update_content_status, log_event

BUFFER_API = "https://api.bufferapp.com/1"


def test_connection() -> dict:
    if not settings.buffer_access_token:
        return {"connected": False, "error": "No Buffer access token configured"}
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{BUFFER_API}/profiles.json", params={"access_token": settings.buffer_access_token})
            resp.raise_for_status()
            profiles = resp.json()
            return {
                "connected": True,
                "profiles": [{"id": p["id"], "service": p["service"], "formatted_username": p.get("formatted_username", "")} for p in profiles],
            }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def _get_profile_id(content_type: str) -> Optional[str]:
    if "fb" in content_type:
        return settings.buffer_fb_profile_id
    elif "ig" in content_type:
        return settings.buffer_ig_profile_id
    return None


def queue_post(piece: dict) -> Optional[str]:
    profile_id = _get_profile_id(piece["content_type"])
    if not profile_id:
        log_event("error", f"No Buffer profile ID for {piece['content_type']}")
        return None

    text = piece.get("edited_body") or piece["body"]

    if "ig" in piece["content_type"] and piece.get("hashtags"):
        text += f"\n\n{piece['hashtags']}"

    data = {
        "access_token": settings.buffer_access_token,
        "profile_ids[]": profile_id,
        "text": text,
        "top": "false",
    }

    if piece.get("scheduled_date") and piece.get("scheduled_time"):
        scheduled_dt = f"{piece['scheduled_date']}T{piece['scheduled_time']}:00"
        data["scheduled_at"] = scheduled_dt

    image_path = piece.get("image_local_path")
    if image_path and Path(image_path).exists():
        data["media[photo]"] = piece.get("image_url", "")

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{BUFFER_API}/updates/create.json", data=data)
            resp.raise_for_status()
            result = resp.json()
            buffer_id = result.get("updates", [{}])[0].get("id") if result.get("updates") else result.get("id")
            return buffer_id
    except Exception as e:
        log_event("error", f"Buffer queue failed for content {piece['id']}: {str(e)}")
        return None


def queue_todays_posts() -> int:
    today = date.today().isoformat()
    pieces = get_content_pieces(status="approved", scheduled_date=today)
    count = 0
    for piece in pieces:
        buffer_id = queue_post(piece)
        if buffer_id:
            update_content_status(piece["id"], "queued", buffer_post_id=buffer_id)
            count += 1
        else:
            update_content_status(piece["id"], "failed")
    if count > 0:
        log_event("queue", f"Queued {count} posts to Buffer for {today}")
    return count

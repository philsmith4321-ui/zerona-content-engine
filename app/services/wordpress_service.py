import base64
from pathlib import Path
from typing import Optional

import requests

from app.config import settings
from app.database import get_db, update_content_status, log_event


def _get_auth_headers() -> dict:
    """Build HTTP Basic Auth headers for WordPress Application Passwords."""
    credentials = f"{settings.wp_username}:{settings.wp_app_password}"
    token = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {token}",
    }


def _wp_api_url(path: str) -> str:
    """Build full WordPress REST API URL."""
    base = settings.wp_url.rstrip("/")
    return f"{base}/wp-json/wp/v2/{path.lstrip('/')}"


def test_wp_connection() -> dict:
    """Test WordPress connection by fetching the authenticated user."""
    if not settings.wp_url or not settings.wp_username or not settings.wp_app_password:
        return {"connected": False, "error": "WordPress not configured. Set WP_URL, WP_USERNAME, WP_APP_PASSWORD in .env"}

    try:
        resp = requests.get(
            _wp_api_url("users/me"),
            headers=_get_auth_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"connected": True, "username": data.get("name", ""), "site_url": settings.wp_url}
        else:
            return {"connected": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except requests.RequestException as e:
        return {"connected": False, "error": str(e)}


def _upload_image(image_path: str, title: str) -> Optional[int]:
    """Upload an image to WordPress media library. Returns media ID or None on failure."""
    path = Path(image_path)
    if not path.exists():
        return None

    filename = path.name
    content_type = "image/png" if filename.endswith(".png") else "image/jpeg"

    try:
        headers = _get_auth_headers()
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        headers["Content-Type"] = content_type

        with open(path, "rb") as f:
            resp = requests.post(
                _wp_api_url("media"),
                headers=headers,
                data=f.read(),
                timeout=60,
            )

        if resp.status_code == 201:
            return resp.json().get("id")
        else:
            log_event("warning", f"WordPress image upload failed: HTTP {resp.status_code}")
            return None
    except requests.RequestException as e:
        log_event("warning", f"WordPress image upload error: {str(e)}")
        return None


def publish_blog(content_id: int) -> dict:
    """Publish an approved blog post to WordPress."""
    if not settings.wp_url or not settings.wp_username or not settings.wp_app_password:
        return {"success": False, "error": "WordPress not configured. Set WP_URL, WP_USERNAME, WP_APP_PASSWORD in .env"}

    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()

    if not row:
        return {"success": False, "error": "Content not found"}

    piece = dict(row)

    if piece["content_type"] != "blog":
        return {"success": False, "error": "Only blog posts can be published to WordPress"}

    if piece["status"] != "approved":
        return {"success": False, "error": "Only approved blog posts can be published"}

    # Upload hero image if available
    media_id = None
    image_path = piece.get("image_local_path")
    if image_path:
        media_id = _upload_image(image_path, piece.get("title", "Blog image"))

    # Create the WordPress post
    body_html = piece.get("edited_body") or piece["body"]
    post_data = {
        "title": piece["title"],
        "content": body_html,
        "status": "publish",
        "excerpt": piece.get("hashtags", ""),
    }
    if media_id:
        post_data["featured_media"] = media_id

    try:
        resp = requests.post(
            _wp_api_url("posts"),
            headers=_get_auth_headers(),
            json=post_data,
            timeout=30,
        )

        if resp.status_code == 201:
            wp_data = resp.json()
            wp_url = wp_data.get("link", "")
            wp_post_id = wp_data.get("id", "")

            # Store WP URL in buffer_post_id and update status
            update_content_status(content_id, "posted", buffer_post_id=wp_url)
            log_event("publish", f"Blog {content_id} published to WordPress: {wp_url}")

            return {"success": True, "url": wp_url, "wp_post_id": wp_post_id}
        else:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log_event("error", f"WordPress publish failed for blog {content_id}: {error_msg}")
            return {"success": False, "error": error_msg}

    except requests.RequestException as e:
        error_msg = str(e)
        log_event("error", f"WordPress publish error for blog {content_id}: {error_msg}")
        return {"success": False, "error": error_msg}

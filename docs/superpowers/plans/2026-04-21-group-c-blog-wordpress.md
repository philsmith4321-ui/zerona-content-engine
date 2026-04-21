# Group C: Blog Publishing to WordPress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish approved blog posts from the Zerona Content Engine to a WordPress site via REST API.

**Architecture:** New `wordpress_service.py` handles all WordPress REST API communication (post creation, image upload, connection testing). Two new API endpoints expose publish and test-connection to the UI. Blog review template gets a "Publish to WP" button on approved posts and a "Published" badge with link on posted posts. Settings page gets a WordPress connection test section. Authentication uses WordPress Application Passwords over HTTP Basic Auth.

**Tech Stack:** FastAPI, WordPress REST API (`/wp-json/wp/v2/`), `requests` library, HTMX, Tailwind CSS

---

### Task 1: Add WordPress settings to config

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Add WordPress settings to the Settings class**

In `app/config.py`, add the three WordPress fields after the Buffer settings block (after line 14):

```python
    wp_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""
```

The full `Settings` class should now look like:

```python
class Settings(BaseSettings):
    admin_password: str = "changeme"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    base_url: str = "http://localhost:8000"

    anthropic_api_key: str = ""
    replicate_api_token: str = ""

    buffer_access_token: str = ""
    buffer_fb_profile_id: str = ""
    buffer_ig_profile_id: str = ""

    wp_url: str = ""
    wp_username: str = ""
    wp_app_password: str = ""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notification_email: str = ""

    posts_per_week_fb: int = 4
    posts_per_week_ig: int = 5
    blogs_per_month: int = 2
    generation_day: str = "sunday"
    generation_hour: int = 6

    class Config:
        env_file = ".env"
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat: add WordPress config settings (wp_url, wp_username, wp_app_password)"
```

---

### Task 2: Create WordPress service

**Files:**
- Create: `app/services/wordpress_service.py`

- [ ] **Step 1: Create `app/services/wordpress_service.py`**

```python
import base64
from pathlib import Path

import requests

from app.config import settings
from app.database import get_db, update_content_status, insert_content_piece, log_event


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


def _upload_image(image_path: str, title: str) -> int | None:
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
```

- [ ] **Step 2: Commit**

```bash
git add app/services/wordpress_service.py
git commit -m "feat: add WordPress service for blog publishing and connection testing"
```

---

### Task 3: Add publish and test-connection API endpoints

**Files:**
- Modify: `app/routes/api.py`

- [ ] **Step 1: Add the two WordPress endpoints at the end of `app/routes/api.py`**

```python
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
    return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Publish failed: {result["error"]}</div>')


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
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/api.py
git commit -m "feat: add WordPress publish and test-connection API endpoints"
```

---

### Task 4: Update blog review template with Publish button and Published badge

**Files:**
- Modify: `app/templates/blog_review.html`

- [ ] **Step 1: Replace the action buttons section**

In `app/templates/blog_review.html`, find the existing actions div:

```html
        <div class="flex gap-2 border-t pt-4">
            {% if blog.status == 'pending' %}
            <button hx-post="/api/content/{{ blog.id }}/approve" hx-target="#blog-{{ blog.id }}" hx-swap="outerHTML"
                    class="px-4 py-1.5 bg-green-500 text-white text-sm rounded hover:bg-green-600 transition">Approve</button>
            <button onclick="document.getElementById('edit-blog-{{ blog.id }}').classList.toggle('hidden')"
                    class="px-4 py-1.5 bg-yellow-500 text-white text-sm rounded hover:bg-yellow-600 transition">Edit</button>
            <button hx-post="/api/content/{{ blog.id }}/reject" hx-target="#blog-{{ blog.id }}" hx-swap="outerHTML"
                    class="px-4 py-1.5 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition">Reject</button>
            {% endif %}
        </div>
```

Replace it with:

```html
        <div class="flex gap-2 border-t pt-4 flex-wrap items-center">
            {% if blog.status == 'pending' %}
            <button hx-post="/api/content/{{ blog.id }}/approve" hx-target="#blog-{{ blog.id }}" hx-swap="outerHTML"
                    class="px-4 py-1.5 bg-green-500 text-white text-sm rounded hover:bg-green-600 transition">Approve</button>
            <button onclick="document.getElementById('edit-blog-{{ blog.id }}').classList.toggle('hidden')"
                    class="px-4 py-1.5 bg-yellow-500 text-white text-sm rounded hover:bg-yellow-600 transition">Edit</button>
            <button hx-post="/api/content/{{ blog.id }}/reject" hx-target="#blog-{{ blog.id }}" hx-swap="outerHTML"
                    class="px-4 py-1.5 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition">Reject</button>
            {% endif %}
            {% if blog.status == 'approved' and not blog.buffer_post_id %}
            <div id="wp-publish-{{ blog.id }}">
                <button hx-post="/api/blog/{{ blog.id }}/publish" hx-target="#wp-publish-{{ blog.id }}" hx-swap="innerHTML"
                        hx-disabled-elt="this"
                        class="px-4 py-1.5 bg-indigo-500 text-white text-sm rounded hover:bg-indigo-600 transition disabled:opacity-50">
                    Publish to WP
                </button>
            </div>
            {% endif %}
            {% if blog.buffer_post_id %}
            <span class="text-xs font-semibold px-2 py-1 rounded bg-green-100 text-green-700">Published</span>
            <a href="{{ blog.buffer_post_id }}" target="_blank" class="text-xs text-indigo-600 underline">View on WordPress</a>
            {% endif %}
        </div>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/blog_review.html
git commit -m "feat: add Publish to WP button and Published badge on blog review"
```

---

### Task 5: Add WordPress section to settings page

**Files:**
- Modify: `app/templates/settings.html`

- [ ] **Step 1: Add WordPress section after Database Backups**

In `app/templates/settings.html`, find the closing `</div>` of the Database Backups section (line 33). Add the WordPress section immediately after it:

```html
    <!-- WordPress Connection -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">WordPress</h3>
        <p class="text-sm text-gray-500 mb-3">Publish approved blog posts to WordPress. Configure WP_URL, WP_USERNAME, WP_APP_PASSWORD in your .env file.</p>
        <div id="wp-status">
            <button hx-get="/api/wordpress/test" hx-target="#wp-status" hx-swap="innerHTML"
                    class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">
                Test Connection
            </button>
        </div>
    </div>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/settings.html
git commit -m "feat: add WordPress connection test section to settings page"
```

---

### Task 6: Verify requests library is available

**Files:**
- Check: `requirements.txt`

- [ ] **Step 1: Verify `requests` is in requirements.txt**

```bash
grep -i requests requirements.txt
```

If `requests` is NOT listed, add it:

```bash
echo "requests>=2.31.0" >> requirements.txt
git add requirements.txt
git commit -m "chore: add requests to requirements.txt"
```

If it IS listed (or is a transitive dependency of an existing package), no action needed.

- [ ] **Step 2: Verify import works**

```bash
python3 -c "import requests; print('requests', requests.__version__)"
```

---

### Task 7: Integration test and deploy

- [ ] **Step 1: Verify config loads new fields**

```bash
python3 -c "from app.config import settings; print('wp_url:', repr(settings.wp_url)); print('wp_username:', repr(settings.wp_username))"
```

Expected: prints empty strings (no WP_ vars in local .env).

- [ ] **Step 2: Verify wordpress_service imports cleanly**

```bash
python3 -c "from app.services.wordpress_service import test_wp_connection, publish_blog; print('WordPress service OK')"
```

- [ ] **Step 3: Test connection returns 'not configured' when no credentials**

```bash
python3 -c "from app.services.wordpress_service import test_wp_connection; print(test_wp_connection())"
```

Expected: `{"connected": False, "error": "WordPress not configured. Set WP_URL, WP_USERNAME, WP_APP_PASSWORD in .env"}`

- [ ] **Step 4: Push and deploy to production**

```bash
git push origin main
```

```bash
ssh root@104.131.74.47 "cd /root/zerona-content-engine && git pull origin main"
ssh root@104.131.74.47 "cd /root/zerona-content-engine && docker build -t zerona-content-engine_app:latest ."
ssh root@104.131.74.47 "docker stop zerona-content-engine_app_1 && docker rm zerona-content-engine_app_1"
ssh root@104.131.74.47 "cd /root/zerona-content-engine && docker run -d --name zerona-content-engine_app_1 --restart unless-stopped -p 8000:8000 -v /root/zerona-content-engine/data:/app/data -v /root/zerona-content-engine/media:/app/media -v /root/zerona-content-engine/prompts:/app/prompts -v /root/zerona-content-engine/config:/app/config --env-file /root/zerona-content-engine/.env zerona-content-engine_app:latest"
```

- [ ] **Step 5: Smoke test production**

```bash
ssh root@104.131.74.47 "curl -s http://localhost:8000/health"
ssh root@104.131.74.47 "curl -s -c /tmp/cookies.txt -X POST -d 'password=medicman' http://localhost:8000/login -o /dev/null -w '%{http_code}'"
ssh root@104.131.74.47 "curl -s -b /tmp/cookies.txt -o /dev/null -w '%{http_code}' http://localhost:8000/dashboard/blog"
ssh root@104.131.74.47 "curl -s -b /tmp/cookies.txt -o /dev/null -w '%{http_code}' http://localhost:8000/dashboard/settings"
```

Expected: All return 200 (login returns 303).

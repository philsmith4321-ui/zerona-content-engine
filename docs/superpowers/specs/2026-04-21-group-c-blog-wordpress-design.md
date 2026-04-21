# Group C: Blog Publishing to WordPress

**Date:** 2026-04-21
**Scope:** Publish approved blog posts from Zerona Content Engine to a WordPress site via REST API

---

## 1. WordPress Service

### What it does
Publishes approved blog posts (title, HTML body, hero image, meta description) to a WordPress site using the WordPress REST API with Application Password authentication.

### New file: `app/services/wordpress_service.py`

**`publish_blog(content_id: int) -> dict`**
1. Fetches the content piece from DB (must be `content_type == "blog"` and `status == "approved"`)
2. If hero image exists (`image_local_path`), uploads it to WordPress media library via `POST /wp-json/wp/v2/media`
3. Creates a WordPress post via `POST /wp-json/wp/v2/posts` with:
   - `title`: from `content_pieces.title`
   - `content`: from `edited_body` or `body` (HTML)
   - `status`: `"publish"` (live immediately)
   - `excerpt`: from `hashtags` field (which stores the meta description/target keyword for blog posts)
   - `featured_media`: WordPress media ID from step 2 (if image was uploaded)
4. Stores the WordPress post URL in `buffer_post_id` field (this field is unused for blog posts)
5. Updates content piece status to `"posted"`
6. Logs the event to system_log
7. Returns `{"success": True, "url": wp_post_url, "wp_post_id": id}`

**`test_wp_connection() -> dict`**
- `GET /wp-json/wp/v2/users/me` with auth headers
- Returns `{"connected": True, "site_name": "...", "username": "..."}` or `{"connected": False, "error": "..."}`

### Authentication
Uses HTTP Basic Auth with Application Passwords (built into WordPress 5.6+):
- Header: `Authorization: Basic base64(username:app_password)`
- Uses the `requests` library (already in requirements.txt via other dependencies, but verify)

### Error handling
- Missing credentials (`wp_url` empty): returns `{"success": False, "error": "WordPress not configured"}`
- Image upload failure: logs warning, continues publishing without featured image (non-fatal)
- Post creation failure: returns error dict, does NOT change content status
- Network errors: caught and returned as error dict

---

## 2. Config Changes

### Modified file: `app/config.py`

Add three new settings:
```python
wp_url: str = ""           # e.g., "https://example.com"
wp_username: str = ""       # WordPress username
wp_app_password: str = ""   # Application password from WordPress
```

### `.env` additions
```
WP_URL=https://your-wordpress-site.com
WP_USERNAME=admin
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

---

## 3. API Endpoints

### Modified file: `app/routes/api.py`

**`POST /api/blog/{content_id}/publish`**
- Auth-protected
- Calls `publish_blog(content_id)`
- Returns HTML success message with WordPress link, or error message
- Only works on blog posts with status "approved"

**`GET /api/wordpress/test`**
- Auth-protected
- Calls `test_wp_connection()`
- Returns HTML showing connection status (green success or red error)

---

## 4. UI Changes

### Modified file: `app/templates/blog_review.html`

**On approved blog posts:**
- Add "Publish to WP" button (purple/indigo, HTMX post to `/api/blog/{id}/publish`)
- Button only shows when `status == "approved"` and `buffer_post_id` is empty

**On posted blog posts:**
- Show "Published" badge (green) with link to WordPress post URL (`buffer_post_id`)
- Hide approve/reject/edit buttons
- Show the WordPress URL as a clickable link

### Modified file: `app/templates/settings.html`

Add "WordPress" section after the Buffer section:
- Shows configured WP_URL (or "Not configured" if empty)
- "Test Connection" button (`hx-get="/api/wordpress/test"`)
- Result area for connection test output

---

## 5. Files Summary

### New files
- `app/services/wordpress_service.py` — WordPress REST API client

### Modified files
- `app/config.py` — add `wp_url`, `wp_username`, `wp_app_password`
- `app/routes/api.py` — add publish and test-connection endpoints
- `app/templates/blog_review.html` — add Publish button, Published badge
- `app/templates/settings.html` — add WordPress connection section

### No changes needed
- `app/database.py` — reuses existing `buffer_post_id` field for WordPress URL
- `app/services/scheduler.py` — publishing is manual, not scheduled
- `app/services/content_generator.py` — blog generation unchanged
- `app/services/retry_queue.py` — not needed for manual publish
- `app/templates/base.html` — no new nav items
- `prompts/blog_post.txt` — unchanged

---

## 6. Out of Scope

- Automatic/scheduled publishing (user clicks to publish)
- WordPress category/tag mapping
- Editing posts already published to WordPress (one-way push)
- WordPress draft mode (posts go live immediately)
- Bulk publishing multiple blog posts at once
- Social media cross-posting of blog links (existing Buffer flow handles social separately)

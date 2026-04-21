# Group D: Infrastructure & Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add content library, DB backups, pagination, retry queue, and mobile quick-approve to the Zerona Content Engine.

**Architecture:** Extends the existing FastAPI + SQLite + Jinja2/HTMX stack. New `failed_jobs` table for retry queue. Pagination via SQL OFFSET. Backups via `shutil.copy2` on a scheduler job. Two new templates (library, mobile review). All new features follow existing patterns: HTMX partials, session auth, APScheduler jobs.

**Tech Stack:** FastAPI, SQLite, Jinja2, HTMX, Tailwind CSS (CDN), APScheduler, shutil

---

### Task 1: Extend `get_content_pieces()` with pagination, search, and date range

**Files:**
- Modify: `app/database.py:85-107`

- [ ] **Step 1: Add `offset`, `search`, `date_from`, `date_to` parameters and `get_content_count()` function**

Replace the existing `get_content_pieces` function (lines 85-107) with:

```python
def get_content_pieces(status: Optional[str] = None, content_type: Optional[str] = None,
                       category: Optional[str] = None, scheduled_date: Optional[str] = None,
                       search: Optional[str] = None, date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM content_pieces WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if content_type:
        query += " AND content_type = ?"
        params.append(content_type)
    if category:
        query += " AND category = ?"
        params.append(category)
    if scheduled_date:
        query += " AND scheduled_date = ?"
        params.append(scheduled_date)
    if search:
        query += " AND (title LIKE ? OR body LIKE ? OR edited_body LIKE ? OR hashtags LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if date_from:
        query += " AND scheduled_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND scheduled_date <= ?"
        params.append(date_to)
    query += " ORDER BY scheduled_date ASC, scheduled_time ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_content_count(status: Optional[str] = None, content_type: Optional[str] = None,
                      category: Optional[str] = None, scheduled_date: Optional[str] = None,
                      search: Optional[str] = None, date_from: Optional[str] = None,
                      date_to: Optional[str] = None) -> int:
    conn = get_db()
    query = "SELECT COUNT(*) as cnt FROM content_pieces WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if content_type:
        query += " AND content_type = ?"
        params.append(content_type)
    if category:
        query += " AND category = ?"
        params.append(category)
    if scheduled_date:
        query += " AND scheduled_date = ?"
        params.append(scheduled_date)
    if search:
        query += " AND (title LIKE ? OR body LIKE ? OR edited_body LIKE ? OR hashtags LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if date_from:
        query += " AND scheduled_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND scheduled_date <= ?"
        params.append(date_to)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row["cnt"]
```

- [ ] **Step 2: Verify existing callers still work**

All existing callers pass only `status`, `content_type`, `category`, `scheduled_date`, and `limit` — those all still work because the new params default to `None`/`0`. No callers need updating.

- [ ] **Step 3: Commit**

```bash
git add app/database.py
git commit -m "feat: add pagination, search, and date range to get_content_pieces"
```

---

### Task 2: Add `failed_jobs` table and `backup_database()` function

**Files:**
- Modify: `app/database.py:19-72` (init_db function) and append new functions

- [ ] **Step 1: Add `failed_jobs` CREATE TABLE to `init_db()` and add `backup_database()` + retry helper functions**

In `app/database.py`, add the `failed_jobs` table inside the `executescript` call (after the `system_log` CREATE TABLE, before the closing `"""`):

```sql
        CREATE TABLE IF NOT EXISTS failed_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            content_id INTEGER NOT NULL,
            error_message TEXT,
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            next_retry_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
```

Then add these functions at the end of `app/database.py` (after `get_logs`):

```python
def backup_database() -> str:
    import shutil
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    backup_path = backup_dir / f"content-{timestamp}.db"
    shutil.copy2(str(DB_PATH), str(backup_path))
    # Keep only last 14 backups
    backups = sorted(backup_dir.glob("content-*.db"))
    for old in backups[:-14]:
        old.unlink()
    log_event("backup", f"Database backed up to {backup_path}")
    return str(backup_path)


def get_failed_jobs(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = get_db()
    query = "SELECT fj.*, cp.title as content_title FROM failed_jobs fj LEFT JOIN content_pieces cp ON fj.content_id = cp.id WHERE 1=1"
    params = []
    if status:
        query += " AND fj.status = ?"
        params.append(status)
    query += " ORDER BY fj.created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def enqueue_retry(job_type: str, content_id: int, error_message: str):
    conn = get_db()
    # Check if there's already a pending retry for this content+type
    existing = conn.execute(
        "SELECT id FROM failed_jobs WHERE content_id = ? AND job_type = ? AND status = 'pending'",
        (content_id, job_type),
    ).fetchone()
    if existing:
        conn.close()
        return
    retry_at = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO failed_jobs (job_type, content_id, error_message, next_retry_at) VALUES (?, ?, ?, ?)",
        (job_type, content_id, error_message, retry_at),
    )
    conn.commit()
    conn.close()
    log_event("retry", f"Enqueued {job_type} retry for content {content_id}")


def update_failed_job(job_id: int, **kwargs):
    conn = get_db()
    sets = []
    params = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(val)
    params.append(job_id)
    conn.execute(f"UPDATE failed_jobs SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def delete_exhausted_jobs():
    conn = get_db()
    conn.execute("DELETE FROM failed_jobs WHERE status = 'exhausted'")
    conn.commit()
    conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add app/database.py
git commit -m "feat: add failed_jobs table, backup_database, and retry helpers"
```

---

### Task 3: Create retry queue service

**Files:**
- Create: `app/services/retry_queue.py`

- [ ] **Step 1: Create `app/services/retry_queue.py`**

```python
from datetime import datetime, timedelta

from app.database import (
    get_db, update_failed_job, update_content_status, log_event,
)


# Backoff schedule: attempt 1 = 15 min, attempt 2 = 1 hour, attempt 3 = 4 hours
BACKOFF_MINUTES = [15, 60, 240]


def process_retries():
    """Process all pending retry jobs whose next_retry_at has passed."""
    conn = get_db()
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT * FROM failed_jobs WHERE status = 'pending' AND next_retry_at <= ?",
        (now,),
    ).fetchall()
    conn.close()

    for job in rows:
        job = dict(job)
        success = False

        if job["job_type"] == "image_generation":
            success = _retry_image(job["content_id"])
        elif job["job_type"] == "buffer_post":
            success = _retry_buffer(job["content_id"])

        new_attempts = job["attempts"] + 1

        if success:
            update_failed_job(job["id"], status="completed", attempts=new_attempts)
            log_event("retry", f"Retry succeeded: {job['job_type']} for content {job['content_id']}")
        elif new_attempts >= job["max_attempts"]:
            update_failed_job(job["id"], status="exhausted", attempts=new_attempts)
            update_content_status(job["content_id"], "failed")
            log_event("retry", f"Retry exhausted: {job['job_type']} for content {job['content_id']} after {new_attempts} attempts")
        else:
            backoff = BACKOFF_MINUTES[min(new_attempts, len(BACKOFF_MINUTES) - 1)]
            next_retry = (datetime.now() + timedelta(minutes=backoff)).isoformat()
            update_failed_job(
                job["id"],
                attempts=new_attempts,
                next_retry_at=next_retry,
                error_message=job.get("error_message", ""),
            )
            log_event("retry", f"Retry {new_attempts}/{job['max_attempts']} failed for {job['job_type']} content {job['content_id']}, next retry in {backoff}m")


def _retry_image(content_id: int) -> bool:
    """Retry image generation for a content piece. Returns True on success."""
    from app.database import get_db as _get_db
    conn = _get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row or not row["image_prompt"]:
        return False
    try:
        from app.services.image_generator import generate_image
        result = generate_image(content_id, row["content_type"], row["image_prompt"])
        return result is not None
    except Exception as e:
        log_event("error", f"Retry image gen failed for {content_id}: {str(e)}")
        return False


def _retry_buffer(content_id: int) -> bool:
    """Retry Buffer posting for a content piece. Returns True on success."""
    from app.database import get_db as _get_db
    conn = _get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return False
    try:
        from app.services.buffer_service import queue_post
        piece = dict(row)
        buffer_id = queue_post(piece)
        if buffer_id:
            update_content_status(content_id, "queued", buffer_post_id=buffer_id)
            return True
        return False
    except Exception as e:
        log_event("error", f"Retry buffer post failed for {content_id}: {str(e)}")
        return False
```

- [ ] **Step 2: Commit**

```bash
git add app/services/retry_queue.py
git commit -m "feat: add retry queue service with exponential backoff"
```

---

### Task 4: Integrate retry queue into image generator and buffer service

**Files:**
- Modify: `app/services/image_generator.py:66-69`
- Modify: `app/services/buffer_service.py:83-84`

- [ ] **Step 1: Add retry enqueue to image generator failure path**

In `app/services/image_generator.py`, replace the except block (lines 66-69):

```python
    except Exception as e:
        log_event("error", f"Image generation failed for content {content_id}", {"error": str(e)})
        update_content_status(content_id, status="pending", image_url="/static/css/placeholder.png")
        return None
```

With:

```python
    except Exception as e:
        log_event("error", f"Image generation failed for content {content_id}", {"error": str(e)})
        update_content_status(content_id, status="pending", image_url="/static/css/placeholder.png")
        from app.database import enqueue_retry
        enqueue_retry("image_generation", content_id, str(e))
        return None
```

- [ ] **Step 2: Add retry enqueue to buffer service failure path**

In `app/services/buffer_service.py`, replace line 84:

```python
            update_content_status(piece["id"], "failed")
```

With:

```python
            update_content_status(piece["id"], "failed")
            from app.database import enqueue_retry
            enqueue_retry("buffer_post", piece["id"], "Buffer queue returned no ID")
```

- [ ] **Step 3: Commit**

```bash
git add app/services/image_generator.py app/services/buffer_service.py
git commit -m "feat: integrate retry queue into image gen and buffer failure paths"
```

---

### Task 5: Add backup and retry scheduler jobs

**Files:**
- Modify: `app/services/scheduler.py`

- [ ] **Step 1: Add two new jobs to scheduler**

In `app/services/scheduler.py`, add two new job functions before `init_scheduler()`:

```python
def backup_job():
    try:
        from app.database import backup_database
        backup_database()
    except Exception as e:
        log_event("error", f"Scheduled backup failed: {str(e)}")


def retry_processor_job():
    try:
        from app.services.retry_queue import process_retries
        process_retries()
    except Exception as e:
        log_event("error", f"Retry processor failed: {str(e)}")
```

Then in `init_scheduler()`, add these two jobs before `scheduler.start()`:

```python
    scheduler.add_job(
        backup_job, CronTrigger(hour=2, minute=0),
        id="daily_backup", replace_existing=True,
    )

    scheduler.add_job(
        retry_processor_job, CronTrigger(minute="*/15"),
        id="retry_processor", replace_existing=True,
    )
```

Update the log_event details dict to include the new jobs:

```python
    log_event("system", "Scheduler initialized", {
        "social_gen": f"{gen_day} at {gen_hour}:00",
        "blog_gen": f"1st & 15th at {gen_hour}:00",
        "buffer_queue": "daily at 7:00",
        "backup": "daily at 2:00",
        "retry_processor": "every 15 minutes",
    })
```

- [ ] **Step 2: Commit**

```bash
git add app/services/scheduler.py
git commit -m "feat: add daily backup and retry processor scheduler jobs"
```

---

### Task 6: Add backup and retry API endpoints

**Files:**
- Modify: `app/routes/api.py`

- [ ] **Step 1: Add backup and retry endpoints to `app/routes/api.py`**

Add these imports at the top of the file (after existing imports):

```python
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
```

(Replace the existing `from fastapi.responses import HTMLResponse, JSONResponse` line.)

Add these endpoints at the end of the file:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/api.py
git commit -m "feat: add backup download/run and retry queue API endpoints"
```

---

### Task 7: Add library and mobile-review dashboard routes

**Files:**
- Modify: `app/routes/dashboard.py`

- [ ] **Step 1: Add imports and new routes**

Add `get_content_count` to the database import at the top of `app/routes/dashboard.py`:

```python
from app.database import get_stats, get_content_pieces, get_logs, get_content_count
```

Add these two routes after the existing `logs_page` route:

```python
@router.get("/library", response_class=HTMLResponse)
async def library(request: Request, status: str = "", platform: str = "", category: str = "",
                  search: str = "", date_from: str = "", date_to: str = "", page: int = 1):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    per_page = 25
    content_type = None
    if platform == "facebook":
        content_type = "social_fb"
    elif platform == "instagram":
        content_type = "social_ig"
    offset = (page - 1) * per_page
    pieces = get_content_pieces(
        status=status or None, content_type=content_type,
        category=category or None, search=search or None,
        date_from=date_from or None, date_to=date_to or None,
        limit=per_page, offset=offset,
    )
    total = get_content_count(
        status=status or None, content_type=content_type,
        category=category or None, search=search or None,
        date_from=date_from or None, date_to=date_to or None,
    )
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse("library.html", {
        "request": request, "active": "library",
        "pieces": pieces, "total": total,
        "page": page, "total_pages": total_pages, "per_page": per_page,
        "current_status": status, "current_platform": platform,
        "current_category": category, "current_search": search,
        "current_date_from": date_from, "current_date_to": date_to,
    })


@router.get("/mobile-review", response_class=HTMLResponse)
async def mobile_review(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    pieces = get_content_pieces(status="pending", limit=200)
    pieces = [p for p in pieces if p["content_type"] != "blog"]
    return templates.TemplateResponse("mobile_review.html", {
        "request": request, "active": "review",
        "pieces": pieces, "pieces_json": json.dumps(pieces, default=str),
    })
```

- [ ] **Step 2: Update review route with pagination**

Replace the existing `review` route (lines 43-60) with:

```python
@router.get("/review", response_class=HTMLResponse)
async def review(request: Request, status: str = "pending", platform: str = "", category: str = "", page: int = 1):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    per_page = 25
    content_type = None
    if platform == "facebook":
        content_type = "social_fb"
    elif platform == "instagram":
        content_type = "social_ig"
    offset = (page - 1) * per_page
    pieces = get_content_pieces(status=status or None, content_type=content_type,
                                 category=category or None, limit=per_page, offset=offset)
    pieces = [p for p in pieces if p["content_type"] != "blog"]
    total = get_content_count(status=status or None, content_type=content_type,
                               category=category or None)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse("review.html", {
        "request": request, "active": "review",
        "pieces": pieces, "current_status": status,
        "current_platform": platform, "current_category": category,
        "page": page, "total_pages": total_pages,
    })
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/dashboard.py
git commit -m "feat: add library and mobile-review routes, paginate review queue"
```

---

### Task 8: Add Library link to sidebar nav

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: Add Library nav link in sidebar**

In `app/templates/base.html`, add this line after the Calendar link (after line 27):

```html
                <a href="/dashboard/library" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'library' %}bg-white/10 border-r-2 border-teal{% endif %}">Library</a>
```

Also add it to the mobile nav (after line 46, the Calendar mobile link):

```html
                <a href="/dashboard/library" class="block py-3 text-white">Library</a>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: add Library link to sidebar and mobile nav"
```

---

### Task 9: Create library page template

**Files:**
- Create: `app/templates/library.html`

- [ ] **Step 1: Create `app/templates/library.html`**

```html
{% extends "base.html" %}
{% block title %}Content Library - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Content Library</h2>
        <span class="text-sm text-gray-500">{{ total }} total items</span>
    </div>

    <!-- Filters -->
    <div class="bg-white rounded-lg shadow-sm border p-4 mb-6">
        <form id="library-filters" method="get" action="/dashboard/library" class="flex flex-wrap gap-3 items-end">
            <div>
                <label class="block text-xs text-gray-500 mb-1">Status</label>
                <select name="status" class="border rounded px-3 py-1.5 text-sm">
                    <option value="">All</option>
                    <option value="pending" {% if current_status == 'pending' %}selected{% endif %}>Pending</option>
                    <option value="approved" {% if current_status == 'approved' %}selected{% endif %}>Approved</option>
                    <option value="rejected" {% if current_status == 'rejected' %}selected{% endif %}>Rejected</option>
                    <option value="queued" {% if current_status == 'queued' %}selected{% endif %}>Queued</option>
                    <option value="posted" {% if current_status == 'posted' %}selected{% endif %}>Posted</option>
                    <option value="failed" {% if current_status == 'failed' %}selected{% endif %}>Failed</option>
                </select>
            </div>
            <div>
                <label class="block text-xs text-gray-500 mb-1">Platform</label>
                <select name="platform" class="border rounded px-3 py-1.5 text-sm">
                    <option value="">All</option>
                    <option value="facebook" {% if current_platform == 'facebook' %}selected{% endif %}>Facebook</option>
                    <option value="instagram" {% if current_platform == 'instagram' %}selected{% endif %}>Instagram</option>
                </select>
            </div>
            <div>
                <label class="block text-xs text-gray-500 mb-1">Category</label>
                <select name="category" class="border rounded px-3 py-1.5 text-sm">
                    <option value="">All</option>
                    <option value="education" {% if current_category == 'education' %}selected{% endif %}>Education</option>
                    <option value="social_proof" {% if current_category == 'social_proof' %}selected{% endif %}>Social Proof</option>
                    <option value="behind_scenes" {% if current_category == 'behind_scenes' %}selected{% endif %}>Behind the Scenes</option>
                    <option value="patient_stories" {% if current_category == 'patient_stories' %}selected{% endif %}>Patient Stories</option>
                    <option value="lifestyle" {% if current_category == 'lifestyle' %}selected{% endif %}>Lifestyle</option>
                </select>
            </div>
            <div>
                <label class="block text-xs text-gray-500 mb-1">From</label>
                <input type="date" name="date_from" value="{{ current_date_from }}" class="border rounded px-3 py-1.5 text-sm">
            </div>
            <div>
                <label class="block text-xs text-gray-500 mb-1">To</label>
                <input type="date" name="date_to" value="{{ current_date_to }}" class="border rounded px-3 py-1.5 text-sm">
            </div>
            <div class="flex-1 min-w-[200px]">
                <label class="block text-xs text-gray-500 mb-1">Search</label>
                <input type="text" name="search" value="{{ current_search }}" placeholder="Search captions, titles, hashtags..."
                       class="w-full border rounded px-3 py-1.5 text-sm">
            </div>
            <button type="submit" class="bg-teal text-white px-4 py-1.5 rounded text-sm font-semibold hover:bg-teal/90 transition">
                Filter
            </button>
        </form>
    </div>

    <!-- Content Cards -->
    <div id="library-list" class="space-y-4">
        {% if pieces %}
            {% for piece in pieces %}
                {% include "partials/content_card.html" %}
            {% endfor %}
        {% else %}
            <div class="text-center py-12 text-gray-400">
                <p class="text-lg">No content matches your filters</p>
            </div>
        {% endif %}
    </div>

    <!-- Pagination -->
    {% if total_pages > 1 %}
    <div class="flex justify-center items-center gap-4 mt-8">
        {% if page > 1 %}
        <a href="/dashboard/library?status={{ current_status }}&platform={{ current_platform }}&category={{ current_category }}&search={{ current_search }}&date_from={{ current_date_from }}&date_to={{ current_date_to }}&page={{ page - 1 }}"
           class="bg-white border rounded px-4 py-2 text-sm hover:bg-gray-50 transition">Previous</a>
        {% else %}
        <span class="text-gray-300 px-4 py-2 text-sm">Previous</span>
        {% endif %}
        <span class="text-sm text-gray-600">Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
        <a href="/dashboard/library?status={{ current_status }}&platform={{ current_platform }}&category={{ current_category }}&search={{ current_search }}&date_from={{ current_date_from }}&date_to={{ current_date_to }}&page={{ page + 1 }}"
           class="bg-white border rounded px-4 py-2 text-sm hover:bg-gray-50 transition">Next</a>
        {% else %}
        <span class="text-gray-300 px-4 py-2 text-sm">Next</span>
        {% endif %}
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/library.html
git commit -m "feat: add content library page template with filters and pagination"
```

---

### Task 10: Add pagination to review page template

**Files:**
- Modify: `app/templates/review.html`

- [ ] **Step 1: Add pagination controls and mobile review link**

In `app/templates/review.html`, add a "Mobile Review" link in the button group (after the Batch Review button, before the Approve All button):

```html
            <a href="/dashboard/mobile-review"
               class="bg-gray-500 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-gray-600 transition md:hidden">
                Mobile Review
            </a>
```

Add pagination controls at the bottom, after the closing `</div>` of `#review-list` (before the final `</div>{% endblock %}`):

```html
    <!-- Pagination -->
    {% if total_pages > 1 %}
    <div class="flex justify-center items-center gap-4 mt-8">
        {% if page > 1 %}
        <a href="/dashboard/review?status={{ current_status }}&platform={{ current_platform }}&category={{ current_category }}&page={{ page - 1 }}"
           class="bg-white border rounded px-4 py-2 text-sm hover:bg-gray-50 transition">Previous</a>
        {% else %}
        <span class="text-gray-300 px-4 py-2 text-sm">Previous</span>
        {% endif %}
        <span class="text-sm text-gray-600">Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
        <a href="/dashboard/review?status={{ current_status }}&platform={{ current_platform }}&category={{ current_category }}&page={{ page + 1 }}"
           class="bg-white border rounded px-4 py-2 text-sm hover:bg-gray-50 transition">Next</a>
        {% else %}
        <span class="text-gray-300 px-4 py-2 text-sm">Next</span>
        {% endif %}
    </div>
    {% endif %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/review.html
git commit -m "feat: add pagination controls and mobile review link to review page"
```

---

### Task 11: Add backup section to settings page and retry queue to logs page

**Files:**
- Modify: `app/templates/settings.html`
- Modify: `app/templates/logs.html`

- [ ] **Step 1: Add backup section to settings.html**

In `app/templates/settings.html`, add this section after the Buffer Connection section (after line 16's closing `</div>`):

```html
    <!-- Database Backups -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">Database Backups</h3>
        <p class="text-sm text-gray-500 mb-3">Automatic daily backups at 2:00 AM. Last 14 days retained.</p>
        <div class="flex gap-3">
            <div id="backup-status">
                <button hx-post="/api/backup/run" hx-target="#backup-status" hx-swap="innerHTML"
                        class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">
                    Backup Now
                </button>
            </div>
            <a href="/api/backup/download" class="bg-gray-100 text-gray-700 px-4 py-2 rounded text-sm hover:bg-gray-200 transition">
                Download Latest
            </a>
        </div>
    </div>
```

- [ ] **Step 2: Add retry queue section to logs.html**

In `app/templates/logs.html`, add this section after the Filters div (after line 18's closing `</div>`) and before the log entries table:

```html
    <!-- Retry Queue -->
    <div class="bg-white rounded-lg shadow-sm border overflow-hidden mb-6">
        <div class="flex justify-between items-center px-4 py-3 bg-gray-50 border-b">
            <h3 class="font-semibold text-gray-700 text-sm">Retry Queue</h3>
            <button hx-post="/api/retry/clear-exhausted" hx-target="#retry-status" hx-swap="innerHTML"
                    class="text-xs text-red-500 hover:text-red-700">Clear Exhausted</button>
        </div>
        <div id="retry-status"></div>
        <div id="retry-queue">
            <script>
                fetch('/api/retry/jobs')
                    .then(r => r.json())
                    .then(jobs => {
                        const container = document.getElementById('retry-queue');
                        if (!jobs.length) {
                            container.innerHTML = '<p class="px-4 py-6 text-center text-gray-400 text-sm">No retry jobs</p>';
                            return;
                        }
                        let html = '<table class="w-full text-sm"><thead class="bg-gray-50"><tr>' +
                            '<th class="text-left px-4 py-2 font-semibold text-gray-600">Content</th>' +
                            '<th class="text-left px-4 py-2 font-semibold text-gray-600">Type</th>' +
                            '<th class="text-left px-4 py-2 font-semibold text-gray-600">Attempts</th>' +
                            '<th class="text-left px-4 py-2 font-semibold text-gray-600">Status</th>' +
                            '<th class="text-left px-4 py-2 font-semibold text-gray-600">Error</th>' +
                            '<th class="px-4 py-2"></th>' +
                            '</tr></thead><tbody>';
                        jobs.forEach(j => {
                            const statusColor = j.status === 'exhausted' ? 'bg-red-100 text-red-600' :
                                j.status === 'completed' ? 'bg-green-100 text-green-600' : 'bg-yellow-100 text-yellow-600';
                            html += '<tr class="border-t">' +
                                '<td class="px-4 py-2">' + (j.content_title || 'Content #' + j.content_id) + '</td>' +
                                '<td class="px-4 py-2"><span class="text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-600">' + j.job_type + '</span></td>' +
                                '<td class="px-4 py-2">' + j.attempts + '/' + j.max_attempts + '</td>' +
                                '<td class="px-4 py-2"><span class="text-xs font-semibold px-2 py-0.5 rounded ' + statusColor + '">' + j.status + '</span></td>' +
                                '<td class="px-4 py-2 text-xs text-gray-500 max-w-xs truncate">' + (j.error_message || '') + '</td>' +
                                '<td class="px-4 py-2">' +
                                (j.status === 'pending' ? '<button hx-post="/api/retry/' + j.id + '/run" hx-target="#retry-status" hx-swap="innerHTML" class="text-xs text-teal hover:underline">Retry Now</button>' : '') +
                                '</td></tr>';
                        });
                        html += '</tbody></table>';
                        container.innerHTML = html;
                    });
            </script>
        </div>
    </div>
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/settings.html app/templates/logs.html
git commit -m "feat: add backup section to settings and retry queue to logs page"
```

---

### Task 12: Create mobile quick-approve template

**Files:**
- Create: `app/templates/mobile_review.html`

- [ ] **Step 1: Create `app/templates/mobile_review.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Quick Approve - Zerona</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>tailwind.config = { theme: { extend: { colors: { navy: '#1B2A4A', teal: '#0EA5A0' } } } }</script>
    <script src="/static/js/htmx.min.js"></script>
    <style>
        body { overscroll-behavior: none; }
        .card-enter { animation: slideIn 0.2s ease-out; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(30px); } to { opacity: 1; transform: translateX(0); } }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Top bar -->
    <div class="bg-navy text-white px-4 py-3 flex justify-between items-center sticky top-0 z-50">
        <a href="/dashboard/review" class="text-white text-lg">&larr;</a>
        <span class="text-sm font-semibold" id="progress-text">0 of 0</span>
        <span class="text-xs text-gray-400" id="stats-text"></span>
    </div>

    <!-- Progress bar -->
    <div class="h-1 bg-gray-200">
        <div id="progress-bar" class="h-1 bg-teal transition-all duration-300" style="width:0%"></div>
    </div>

    <!-- Main content -->
    <div id="card-area" class="p-4">
        <div id="post-card" class="card-enter"></div>
        <div id="complete-screen" class="hidden text-center py-16">
            <h2 class="text-2xl font-bold text-navy mb-2">All Done!</h2>
            <p class="text-gray-500 mb-2" id="summary-text"></p>
            <a href="/dashboard" class="inline-block mt-4 bg-teal text-white px-6 py-3 rounded-lg font-semibold">
                Back to Dashboard
            </a>
        </div>
    </div>

    <!-- Action buttons (sticky bottom) -->
    <div id="action-buttons" class="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg p-4">
        <div class="flex gap-3">
            <button onclick="rejectCurrent()" class="flex-1 bg-red-500 text-white py-4 rounded-xl text-lg font-bold active:bg-red-600">
                Reject
            </button>
            <button onclick="approveCurrent()" class="flex-1 bg-green-500 text-white py-4 rounded-xl text-lg font-bold active:bg-green-600">
                Approve
            </button>
        </div>
    </div>

    <script>
        const pieces = {{ pieces_json | safe }};
        let currentIndex = 0;
        let approved = 0, rejected = 0, total = pieces.length;

        function renderCard() {
            if (currentIndex >= total) {
                document.getElementById('post-card').classList.add('hidden');
                document.getElementById('action-buttons').classList.add('hidden');
                document.getElementById('complete-screen').classList.remove('hidden');
                document.getElementById('summary-text').textContent =
                    total + ' posts reviewed: ' + approved + ' approved, ' + rejected + ' rejected, ' + (total - approved - rejected) + ' skipped';
                return;
            }
            const p = pieces[currentIndex];
            const platform = (p.content_type || '').includes('fb') ? 'Facebook' : 'Instagram';
            const platformColor = platform === 'Facebook' ? 'bg-blue-100 text-blue-700' : 'bg-pink-100 text-pink-700';
            const imgSrc = p.image_url || '/static/css/placeholder.png';
            const caption = p.edited_body || p.body || '';
            const hashtags = p.hashtags || '';

            document.getElementById('post-card').innerHTML =
                '<div class="card-enter bg-white rounded-xl shadow-sm border overflow-hidden mb-24">' +
                '  <img src="' + imgSrc + '" class="w-full aspect-square object-cover" onerror="this.src=\'/static/css/placeholder.png\'">' +
                '  <div class="p-4">' +
                '    <div class="flex gap-2 mb-2">' +
                '      <span class="text-xs font-semibold px-2 py-0.5 rounded ' + platformColor + '">' + platform + '</span>' +
                '      <span class="text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-600">' + (p.category || '') + '</span>' +
                '      <span class="text-xs text-gray-400">' + (p.scheduled_date || '') + '</span>' +
                '    </div>' +
                '    <p class="text-sm text-gray-700 leading-relaxed">' + caption + '</p>' +
                '    <p class="text-xs text-indigo-500 mt-2">' + hashtags + '</p>' +
                '  </div>' +
                '</div>';

            document.getElementById('progress-text').textContent = (currentIndex + 1) + ' of ' + total;
            document.getElementById('progress-bar').style.width = ((currentIndex + 1) / total * 100) + '%';
            document.getElementById('stats-text').textContent = approved + '✓ ' + rejected + '✗';
        }

        async function approveCurrent() {
            const p = pieces[currentIndex];
            await fetch('/api/content/' + p.id + '/approve', { method: 'POST' });
            approved++;
            currentIndex++;
            renderCard();
        }

        async function rejectCurrent() {
            const p = pieces[currentIndex];
            await fetch('/api/content/' + p.id + '/reject', { method: 'POST' });
            rejected++;
            currentIndex++;
            renderCard();
        }

        // Touch swipe support
        let touchStartX = 0;
        document.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; });
        document.addEventListener('touchend', e => {
            const diff = e.changedTouches[0].clientX - touchStartX;
            if (Math.abs(diff) > 80) {
                if (diff > 0) approveCurrent();  // swipe right = approve
                else rejectCurrent();             // swipe left = reject
            }
        });

        // Initial render
        if (total > 0) renderCard();
        else {
            document.getElementById('post-card').innerHTML = '<p class="text-center py-16 text-gray-400">No pending posts to review</p>';
            document.getElementById('action-buttons').classList.add('hidden');
        }
    </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/mobile_review.html
git commit -m "feat: add mobile quick-approve page with swipe support"
```

---

### Task 13: Integration test — verify all Group D features

**Files:** None (manual testing)

- [ ] **Step 1: Start the app**

```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Verify DB migration**

Check that `failed_jobs` table was created:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/content.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print([t[0] for t in tables])
conn.close()
"
```

Expected: list includes `failed_jobs`

- [ ] **Step 3: Test library page**

1. Navigate to `/dashboard/library` — should show all content with filter controls
2. Filter by status "approved" — should show only approved posts
3. Search for a keyword — should filter results
4. Check pagination controls appear if > 25 items

- [ ] **Step 4: Test backup**

1. Go to Settings page — should see "Database Backups" section
2. Click "Backup Now" — should show success message
3. Click "Download Latest" — should download a .db file
4. Check `data/backups/` directory has a backup file

- [ ] **Step 5: Test retry queue UI**

1. Go to Logs page — should see "Retry Queue" section
2. If no retry jobs exist, should show "No retry jobs"

- [ ] **Step 6: Test review pagination**

1. Go to Review Queue — should show pagination controls if > 25 posts
2. Click Next/Previous — should paginate

- [ ] **Step 7: Test mobile review**

1. Open `/dashboard/mobile-review` on a phone or mobile browser emulator
2. Should show one post at a time with Approve/Reject buttons
3. Tap Approve — should advance to next post
4. Verify swipe gestures work

- [ ] **Step 8: Verify sidebar nav**

Check that "Library" appears in the sidebar navigation.

---

### Task 14: Deploy to production

- [ ] **Step 1: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Pull and rebuild on production server**

```bash
ssh root@104.131.74.47 "cd /root/zerona-content-engine && git pull origin main"
ssh root@104.131.74.47 "cd /root/zerona-content-engine && docker build -t zerona-content-engine_app:latest ."
ssh root@104.131.74.47 "docker stop zerona-content-engine_app_1 && docker rm zerona-content-engine_app_1"
ssh root@104.131.74.47 "cd /root/zerona-content-engine && docker run -d --name zerona-content-engine_app_1 --restart unless-stopped -p 8000:8000 -v /root/zerona-content-engine/data:/app/data -v /root/zerona-content-engine/media:/app/media -v /root/zerona-content-engine/prompts:/app/prompts -v /root/zerona-content-engine/config:/app/config --env-file /root/zerona-content-engine/.env zerona-content-engine_app:latest"
```

- [ ] **Step 3: Smoke test production**

```bash
curl -s http://104.131.74.47:8000/health
# Login and test new endpoints
curl -s -c /tmp/cookies.txt -X POST -d "password=..." http://104.131.74.47:8000/login
curl -s -b /tmp/cookies.txt -o /dev/null -w "%{http_code}" http://104.131.74.47:8000/dashboard/library
curl -s -b /tmp/cookies.txt -o /dev/null -w "%{http_code}" http://104.131.74.47:8000/dashboard/mobile-review
```

Expected: All return 200.

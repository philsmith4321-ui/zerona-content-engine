# Group D: Infrastructure & Reliability Improvements

**Date:** 2026-04-21
**Scope:** Content library, DB backups, pagination, retry queue, mobile quick-approve

---

## 1. Pagination

### What it does
Adds offset-based pagination to all content listing queries. Currently the app loads 100-500 items at once with no pagination controls.

### Database changes

Update `get_content_pieces()` in `app/database.py`:
- Add `offset: int = 0` parameter
- Add `get_content_count()` function that returns total matching rows for the same filters
- SQL: `SELECT * FROM content_pieces WHERE ... ORDER BY scheduled_date ASC, scheduled_time ASC LIMIT ? OFFSET ?`
- Count: `SELECT COUNT(*) FROM content_pieces WHERE ...` (same filters, no LIMIT/OFFSET)

### Page size
- Default: 25 items per page
- Configurable per-page via query param `?per_page=25`

### UI integration
- All listing pages (review, library) get pagination controls at the bottom
- HTMX-powered: clicking prev/next swaps the content list container without full page reload
- Controls: "Previous" / "Next" buttons + "Page X of Y" indicator
- `hx-get` with updated `?page=N` query param, `hx-target="#content-list"`, `hx-swap="innerHTML"`

### Affected routes
- `GET /dashboard/review` — paginate review queue
- `GET /dashboard/library` — paginate library (see section 2)
- Batch review and calendar are unaffected (batch review loads all pending for carousel, calendar loads by month)

---

## 2. Content Library

### What it does
A new page at `/dashboard/library` showing all content across all statuses. Searchable by keyword, filterable by status, platform, category, and date range. Uses pagination from section 1.

### New route
`GET /dashboard/library`
- Template: `app/templates/library.html`
- Sidebar nav gets a "Library" link (book icon)

### Filters
- **Status**: All / Pending / Approved / Rejected / Queued / Posted / Failed (dropdown)
- **Platform**: All / Facebook / Instagram (dropdown)
- **Category**: All / Education / Social Proof / Behind the Scenes / Patient Stories / Lifestyle (dropdown)
- **Search**: Text input — searches `title`, `body`, `edited_body`, `hashtags` via SQL `LIKE '%term%'`
- **Date range**: Start date / End date inputs — filters on `scheduled_date`

### Database changes
Update `get_content_pieces()` to support:
- `search: Optional[str]` parameter — adds `AND (title LIKE ? OR body LIKE ? OR edited_body LIKE ? OR hashtags LIKE ?)` clause
- `date_from: Optional[str]` and `date_to: Optional[str]` parameters — adds `AND scheduled_date >= ?` / `AND scheduled_date <= ?`

### UI
- Same content card partial (`partials/content_card.html`) for each result
- Filter bar at top (same pattern as review.html but with more options)
- Filters use HTMX: changing any filter fires `hx-get` to reload the content list with new params
- Empty state: "No content matches your filters" message
- Stats row at top: total count for current filters

### Design decisions
- Filters apply via query params (URL is shareable/bookmarkable)
- Search is server-side SQL LIKE (simple, no full-text search needed for this scale)
- No export/download functionality (out of scope)

---

## 3. DB Backups

### What it does
Automated daily SQLite backups with retention policy. Manual download from Settings page.

### Backup mechanism
New function in `app/database.py`:
```
def backup_database() -> str:
    backup_dir = Path("data/backups")
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    backup_path = backup_dir / f"content-{timestamp}.db"
    shutil.copy2("data/content.db", backup_path)
    # Delete backups older than 14 days
    for old in sorted(backup_dir.glob("content-*.db"))[:-14]:
        old.unlink()
    log_event("backup", f"Database backed up to {backup_path}")
    return str(backup_path)
```

### Scheduler job
New job in `app/services/scheduler.py`:
- Runs daily at 2:00 AM Central
- Calls `backup_database()`
- Logs success/failure to system_log

### Settings page integration
Add to `app/templates/settings.html`:
- "Database Backups" section
- Shows last backup date/time (query system_log for latest backup event)
- "Download Latest Backup" button — `GET /api/backup/download`
- "Backup Now" button — `POST /api/backup/run` (triggers immediate backup)

### New endpoints
- `GET /api/backup/download` — returns latest backup file as download (FileResponse)
- `POST /api/backup/run` — triggers backup, returns success message

### Retention
- Keep last 14 daily backups
- Oldest deleted automatically after each backup run
- Backup directory: `data/backups/`

---

## 4. Retry Queue

### What it does
Automatically retries failed image generation and Buffer API posts with exponential backoff. Shows failed jobs in a UI for manual intervention.

### Database changes

New table `failed_jobs`:
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `job_type` TEXT — `image_generation` or `buffer_post`
- `content_id` INTEGER — FK to content_pieces.id
- `error_message` TEXT — last error
- `attempts` INTEGER DEFAULT 0
- `max_attempts` INTEGER DEFAULT 3
- `next_retry_at` TIMESTAMP — when to retry next
- `status` TEXT DEFAULT 'pending' — pending, completed, exhausted
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Migration: CREATE TABLE IF NOT EXISTS in `init_db()`.

### Retry logic

New file `app/services/retry_queue.py`:
- `enqueue_retry(job_type, content_id, error_message)` — inserts into failed_jobs with next_retry_at = now + backoff
- `process_retries()` — queries pending jobs where `next_retry_at <= now`, processes each:
  - `image_generation`: calls `generate_image()` for the content piece
  - `buffer_post`: calls `queue_to_buffer()` for the content piece
  - On success: mark job `completed`, update content piece status
  - On failure: increment attempts, set next_retry_at with backoff, log error
  - If attempts >= max_attempts: mark job `exhausted`, set content piece status to `failed`
- Backoff schedule: attempt 1 = 15 minutes, attempt 2 = 1 hour, attempt 3 = 4 hours

### Integration with existing code

**`app/services/image_generator.py`:**
- In the `except` block of `generate_image()`, call `enqueue_retry("image_generation", content_id, str(e))` instead of silently falling back to placeholder

**`app/services/scheduler.py` (daily_buffer_queue_job):**
- When Buffer API call fails, call `enqueue_retry("buffer_post", content_id, str(e))` instead of just setting status to "failed"

**New scheduler job:**
- `retry_processor_job()` runs every 15 minutes
- Calls `process_retries()`

### UI

Add "Retry Queue" section to logs page (`app/templates/logs.html`):
- Table showing: content title, job type, attempts, last error, next retry time, status
- "Retry Now" button per job — `POST /api/retry/{job_id}/run`
- "Clear Exhausted" button — `POST /api/retry/clear-exhausted` removes exhausted entries

### New endpoints
- `GET /api/retry/jobs` — returns list of retry jobs (JSON, for logs page)
- `POST /api/retry/{job_id}/run` — immediately processes a specific retry job
- `POST /api/retry/clear-exhausted` — deletes exhausted jobs from table

---

## 5. Mobile Quick-Approve

### What it does
A mobile-optimized review page at `/dashboard/mobile-review` for approving/rejecting posts on a phone. One post at a time, large touch targets, minimal UI.

### New route
`GET /dashboard/mobile-review`
- Template: `app/templates/mobile_review.html`
- Entry point: "Mobile Review" link on the review page (visible always, optimized for phone access)

### Layout
Single column, full-width, no sidebar:
- **Top**: Progress bar + "X of Y pending" count
- **Middle**: Post image (full width), caption text, hashtags, platform/category badges
- **Bottom (sticky)**: Two large buttons — "Approve" (green, left half) and "Reject" (red, right half)

### Behavior
- Loads all pending non-blog posts as JSON (same as batch review)
- Client-side navigation between posts
- Approve/Reject fires fetch POST to existing `/api/content/{id}/approve` or `/api/content/{id}/reject`
- Auto-advances to next post after action
- At end: summary screen with counts + "Back to Dashboard" button
- Touch swipe support: swipe left = reject, swipe right = approve (using simple JS touch event handlers)

### Design decisions
- Separate template (not responsive version of batch_review) — mobile review is intentionally stripped down
- No variant picker (uses whatever variant is already selected — mobile is for quick approve/reject only)
- No caption editing (do that on desktop)
- No sidebar nav — just a back arrow to dashboard
- `<meta name="viewport" content="width=device-width, initial-scale=1">` already in base.html

---

## Files to create or modify

### New files
- `app/templates/library.html` — content library page
- `app/templates/mobile_review.html` — mobile quick-approve page
- `app/services/retry_queue.py` — retry queue logic

### Modified files
- `app/database.py` — add failed_jobs table, update get_content_pieces() with offset/search/date params, add get_content_count(), add backup_database()
- `app/services/scheduler.py` — add backup job and retry processor job
- `app/services/image_generator.py` — integrate retry queue on failure
- `app/routes/dashboard.py` — add library and mobile-review routes, paginate review
- `app/routes/api.py` — add backup and retry endpoints
- `app/templates/review.html` — add pagination controls, mobile review link
- `app/templates/settings.html` — add backup section
- `app/templates/logs.html` — add retry queue section
- `app/templates/base.html` — add Library to sidebar nav

### No changes needed
- `app/auth.py` — existing session auth covers new routes
- `app/services/content_generator.py` — generation unchanged
- `app/services/buffer_service.py` — Buffer integration unchanged (retry queue wraps it)
- `app/config.py` — no new config needed
- `app/templates/batch_review.html` — batch review unchanged
- `app/templates/partials/phone_preview.html` — phone preview unchanged
- `app/templates/partials/content_card.html` — content card unchanged

---

## Out of scope
- Full-text search (SQLite FTS) — LIKE is sufficient at current scale
- Export/download content as CSV
- Analytics or engagement tracking (Group A)
- Blog publishing (Group C)
- Backup to cloud storage (S3, etc.) — local file backups only
- Push notifications for mobile

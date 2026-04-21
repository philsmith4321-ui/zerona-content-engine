# Group A: Analytics & Smart Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add analytics dashboard with hashtag analysis, smart post scheduling, and content recycling to the Zerona Content Engine.

**Architecture:** Extends the existing FastAPI + SQLite + Jinja2/HTMX stack. Analytics uses SQL aggregate queries rendered as CSS-only bar charts. Smart scheduling replaces the fixed `_get_week_schedule()` with a gap-filling algorithm. Content recycling calls Claude API to rewrite captions and creates new content_pieces rows. No new dependencies.

**Tech Stack:** FastAPI, SQLite, Jinja2, HTMX, Tailwind CSS (CDN), Anthropic Claude API

---

### Task 1: Add `recycled_from` column and `get_analytics_data()` function

**Files:**
- Modify: `app/database.py`

- [ ] **Step 1: Add `recycled_from` migration to `init_db()`**

In `app/database.py`, find the existing migration block (lines 73-81) and add `recycled_from` to it:

```python
    # Migration: add variant columns (idempotent)
    for col_sql in [
        "ALTER TABLE content_pieces ADD COLUMN caption_variants TEXT",
        "ALTER TABLE content_pieces ADD COLUMN selected_variant INTEGER DEFAULT 0",
        "ALTER TABLE content_pieces ADD COLUMN recycled_from INTEGER",
    ]:
        try:
            conn.execute(col_sql)
        except Exception:
            pass  # Column already exists
```

- [ ] **Step 2: Add `get_analytics_data()` function at the end of `app/database.py`**

```python
def get_analytics_data() -> dict:
    from collections import Counter
    conn = get_db()

    # Status counts
    rows = conn.execute("SELECT status, COUNT(*) as cnt FROM content_pieces GROUP BY status").fetchall()
    status_counts = {r["status"]: r["cnt"] for r in rows}
    total = sum(status_counts.values())

    # This week and this month
    week_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_pieces WHERE scheduled_date >= date('now', 'weekday 0', '-6 days')"
    ).fetchone()["cnt"]
    month_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM content_pieces WHERE strftime('%Y-%m', scheduled_date) = strftime('%Y-%m', 'now')"
    ).fetchone()["cnt"]

    # Approval rate
    approved = status_counts.get("approved", 0) + status_counts.get("queued", 0) + status_counts.get("posted", 0)
    rejected = status_counts.get("rejected", 0)
    approval_rate = round(approved / max(approved + rejected, 1) * 100)

    # Platform breakdown
    platform_rows = conn.execute("SELECT content_type, COUNT(*) as cnt FROM content_pieces WHERE content_type != 'blog' GROUP BY content_type").fetchall()
    platform_counts = {r["content_type"]: r["cnt"] for r in platform_rows}
    platform_total = sum(platform_counts.values())

    # Category breakdown
    cat_rows = conn.execute("SELECT category, COUNT(*) as cnt FROM content_pieces GROUP BY category ORDER BY cnt DESC").fetchall()
    category_counts = [(r["category"], r["cnt"]) for r in cat_rows]

    # Weekly generation history (last 8 weeks)
    week_rows = conn.execute(
        "SELECT strftime('%Y-%W', scheduled_date) as week, MIN(scheduled_date) as week_start, COUNT(*) as cnt "
        "FROM content_pieces WHERE scheduled_date IS NOT NULL "
        "GROUP BY week ORDER BY week DESC LIMIT 8"
    ).fetchall()
    weekly_history = [{"week": r["week"], "week_start": r["week_start"], "count": r["cnt"]} for r in reversed(week_rows)]
    max_week_count = max((w["count"] for w in weekly_history), default=1)

    # Hashtag analytics
    hashtag_rows = conn.execute("SELECT hashtags, status FROM content_pieces WHERE hashtags IS NOT NULL AND hashtags != ''").fetchall()
    hashtag_counter = Counter()
    hashtag_approved = Counter()
    hashtag_rejected = Counter()
    for row in hashtag_rows:
        tags = [t.strip().lower() for t in row["hashtags"].replace(",", " ").split() if t.strip().startswith("#")]
        for tag in tags:
            hashtag_counter[tag] += 1
            if row["status"] in ("approved", "queued", "posted"):
                hashtag_approved[tag] += 1
            elif row["status"] == "rejected":
                hashtag_rejected[tag] += 1
    top_hashtags = []
    for tag, count in hashtag_counter.most_common(20):
        app_count = hashtag_approved.get(tag, 0)
        rej_count = hashtag_rejected.get(tag, 0)
        tag_total = app_count + rej_count
        top_hashtags.append({
            "tag": tag,
            "count": count,
            "approved_pct": round(app_count / max(tag_total, 1) * 100),
            "rejected_pct": round(rej_count / max(tag_total, 1) * 100),
        })

    conn.close()

    return {
        "total": total,
        "status_counts": status_counts,
        "week_count": week_count,
        "month_count": month_count,
        "approval_rate": approval_rate,
        "platform_counts": platform_counts,
        "platform_total": max(platform_total, 1),
        "category_counts": category_counts,
        "weekly_history": weekly_history,
        "max_week_count": max(max_week_count, 1),
        "top_hashtags": top_hashtags,
    }
```

- [ ] **Step 3: Commit**

```bash
git add app/database.py
git commit -m "feat: add recycled_from column and get_analytics_data function"
```

---

### Task 2: Add smart scheduling to content generator

**Files:**
- Modify: `app/services/content_generator.py`

- [ ] **Step 1: Replace `_get_week_schedule()` with smart scheduling version**

Replace the existing `_get_week_schedule` function (lines 38-58) with:

```python
def _get_week_schedule(start_date: date) -> list[dict]:
    """Build the posting schedule for a week, avoiding existing slots."""
    preferred_times = ["09:00", "11:30", "14:00", "16:30", "19:00"]
    days = [0, 1, 2, 3, 4, 5]  # Mon-Sat (skip Sunday)

    # Check what's already scheduled this week
    end_date = start_date + timedelta(days=6)
    existing = get_content_pieces(
        date_from=start_date.isoformat(),
        date_to=end_date.isoformat(),
        limit=200,
    )
    taken_slots = set()
    for p in existing:
        if p.get("scheduled_date") and p.get("scheduled_time"):
            taken_slots.add((p["scheduled_date"], p["scheduled_time"]))

    # Build FB schedule (4 posts) and IG schedule (5 posts)
    fb_days = [0, 2, 4, 5]  # Mon, Wed, Fri, Sat
    ig_days = [0, 1, 2, 4, 5]  # Mon, Tue, Wed, Fri, Sat

    schedule = []
    time_idx = 0
    for day_offset in fb_days:
        post_date = (start_date + timedelta(days=day_offset)).isoformat()
        # Find a free time slot
        assigned_time = None
        for t in preferred_times[time_idx:] + preferred_times[:time_idx]:
            if (post_date, t) not in taken_slots:
                assigned_time = t
                taken_slots.add((post_date, t))
                break
        if not assigned_time:
            assigned_time = preferred_times[time_idx % len(preferred_times)]
        schedule.append({"platform": "facebook", "date": post_date, "time": assigned_time})
        time_idx = (time_idx + 1) % len(preferred_times)

    for day_offset in ig_days:
        post_date = (start_date + timedelta(days=day_offset)).isoformat()
        assigned_time = None
        for t in preferred_times[time_idx:] + preferred_times[:time_idx]:
            if (post_date, t) not in taken_slots:
                assigned_time = t
                taken_slots.add((post_date, t))
                break
        if not assigned_time:
            assigned_time = preferred_times[time_idx % len(preferred_times)]
        schedule.append({"platform": "instagram", "date": post_date, "time": assigned_time})
        time_idx = (time_idx + 1) % len(preferred_times)

    return schedule
```

- [ ] **Step 2: Commit**

```bash
git add app/services/content_generator.py
git commit -m "feat: smart scheduling avoids time slot collisions"
```

---

### Task 3: Add recycle endpoint to API

**Files:**
- Modify: `app/routes/api.py`

- [ ] **Step 1: Add the recycle endpoint at the end of `app/routes/api.py`**

```python
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
    from app.config import settings as app_settings
    from app.database import insert_content_piece
    original_body = piece.get("edited_body") or piece["body"]
    client = anthropic.Anthropic(api_key=app_settings.anthropic_api_key)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"Rewrite this social media caption with a completely fresh angle. Keep the same topic and key message but change the tone, hook, and structure. Return ONLY the new caption text, nothing else.\n\nOriginal caption: {original_body}",
            }],
        )
        new_body = response.content[0].text.strip()
    except Exception as e:
        log_event("error", f"Recycle failed for content {content_id}: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Recycle failed: {str(e)}</div>')

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
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/api.py
git commit -m "feat: add content recycle endpoint with Claude rewrite"
```

---

### Task 4: Add analytics route to dashboard

**Files:**
- Modify: `app/routes/dashboard.py`

- [ ] **Step 1: Add analytics import and route**

Add `get_analytics_data` to the import line at top of `app/routes/dashboard.py`:

```python
from app.database import get_stats, get_content_pieces, get_logs, get_content_count, get_analytics_data
```

Add this route after the existing `logs_page` route and before the `library` route:

```python
@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    data = get_analytics_data()
    return templates.TemplateResponse("analytics.html", {
        "request": request, "active": "analytics",
        **data,
    })
```

- [ ] **Step 2: Commit**

```bash
git add app/routes/dashboard.py
git commit -m "feat: add analytics dashboard route"
```

---

### Task 5: Add Analytics link to sidebar nav

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: Add Analytics to desktop sidebar**

In `app/templates/base.html`, find the Library link (line 28):
```html
                <a href="/dashboard/library" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'library' %}bg-white/10 border-r-2 border-teal{% endif %}">Library</a>
```

Add this line AFTER it:
```html
                <a href="/dashboard/analytics" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'analytics' %}bg-white/10 border-r-2 border-teal{% endif %}">Analytics</a>
```

- [ ] **Step 2: Add Analytics to mobile nav**

Find the Library mobile link (line 48):
```html
                <a href="/dashboard/library" class="block py-3 text-white">Library</a>
```

Add this line AFTER it:
```html
                <a href="/dashboard/analytics" class="block py-3 text-white">Analytics</a>
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: add Analytics link to sidebar and mobile nav"
```

---

### Task 6: Create analytics page template

**Files:**
- Create: `app/templates/analytics.html`

- [ ] **Step 1: Create `app/templates/analytics.html`**

```html
{% extends "base.html" %}
{% block title %}Analytics - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <h2 class="text-2xl font-bold text-navy mb-6">Analytics</h2>

    <!-- Summary Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-lg shadow-sm border p-4">
            <p class="text-xs text-gray-500 uppercase">Total Posts</p>
            <p class="text-2xl font-bold text-navy">{{ total }}</p>
        </div>
        <div class="bg-white rounded-lg shadow-sm border p-4">
            <p class="text-xs text-gray-500 uppercase">This Week</p>
            <p class="text-2xl font-bold text-teal">{{ week_count }}</p>
        </div>
        <div class="bg-white rounded-lg shadow-sm border p-4">
            <p class="text-xs text-gray-500 uppercase">This Month</p>
            <p class="text-2xl font-bold text-navy">{{ month_count }}</p>
        </div>
        <div class="bg-white rounded-lg shadow-sm border p-4">
            <p class="text-xs text-gray-500 uppercase">Approval Rate</p>
            <p class="text-2xl font-bold text-green-600">{{ approval_rate }}%</p>
        </div>
    </div>

    <div class="grid md:grid-cols-2 gap-6 mb-8">
        <!-- Platform Breakdown -->
        <div class="bg-white rounded-lg shadow-sm border p-6">
            <h3 class="text-sm font-semibold text-navy mb-4">Platform Breakdown</h3>
            {% for ptype, count in platform_counts.items() %}
            <div class="mb-3">
                <div class="flex justify-between text-sm mb-1">
                    <span class="font-medium {% if 'fb' in ptype %}text-blue-600{% else %}text-pink-600{% endif %}">
                        {{ ptype|replace('social_', '')|upper }}
                    </span>
                    <span class="text-gray-500">{{ count }} ({{ (count / platform_total * 100)|round|int }}%)</span>
                </div>
                <div class="h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div class="h-full rounded-full {% if 'fb' in ptype %}bg-blue-500{% else %}bg-pink-500{% endif %}"
                         style="width: {{ (count / platform_total * 100)|round|int }}%"></div>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Category Breakdown -->
        <div class="bg-white rounded-lg shadow-sm border p-6">
            <h3 class="text-sm font-semibold text-navy mb-4">Category Breakdown</h3>
            {% for cat_name, cat_count in category_counts %}
            <div class="flex justify-between items-center py-1.5 border-b last:border-0">
                <span class="text-sm text-gray-700 capitalize">{{ cat_name|replace('_', ' ') }}</span>
                <span class="text-sm font-semibold text-navy">{{ cat_count }}</span>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Approval Funnel -->
    <div class="bg-white rounded-lg shadow-sm border p-6 mb-8">
        <h3 class="text-sm font-semibold text-navy mb-4">Content Funnel</h3>
        <div class="flex items-center gap-2 flex-wrap">
            {% set funnel_stages = [
                ('Generated', total, 'bg-gray-500'),
                ('Approved', status_counts.get('approved', 0) + status_counts.get('queued', 0) + status_counts.get('posted', 0), 'bg-green-500'),
                ('Queued', status_counts.get('queued', 0) + status_counts.get('posted', 0), 'bg-blue-500'),
                ('Posted', status_counts.get('posted', 0), 'bg-emerald-500'),
            ] %}
            {% for label, count, color in funnel_stages %}
            <div class="flex-1 min-w-[100px]">
                <div class="text-center mb-1">
                    <span class="text-lg font-bold text-navy">{{ count }}</span>
                    <p class="text-xs text-gray-500">{{ label }}</p>
                </div>
                <div class="h-4 {{ color }} rounded-full" style="width: {{ (count / max(total, 1) * 100)|round|int }}%; min-width: 8px;"></div>
            </div>
            {% if not loop.last %}
            <span class="text-gray-300 text-lg">&rarr;</span>
            {% endif %}
            {% endfor %}
        </div>
    </div>

    <!-- Weekly Generation History -->
    <div class="bg-white rounded-lg shadow-sm border p-6 mb-8">
        <h3 class="text-sm font-semibold text-navy mb-4">Weekly Generation History</h3>
        {% if weekly_history %}
        <div class="flex items-end gap-2" style="height: 160px;">
            {% for week in weekly_history %}
            <div class="flex-1 flex flex-col items-center justify-end h-full">
                <span class="text-xs font-semibold text-navy mb-1">{{ week.count }}</span>
                <div class="w-full bg-teal rounded-t" style="height: {{ (week.count / max_week_count * 100)|round|int }}%; min-height: 4px;"></div>
                <span class="text-xs text-gray-400 mt-1">{{ week.week_start[5:] }}</span>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p class="text-center text-gray-400 py-8">No generation data yet</p>
        {% endif %}
    </div>

    <!-- Top Hashtags -->
    <div class="bg-white rounded-lg shadow-sm border p-6">
        <h3 class="text-sm font-semibold text-navy mb-4">Top Hashtags</h3>
        {% if top_hashtags %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="text-left px-4 py-2 font-semibold text-gray-600">Hashtag</th>
                        <th class="text-left px-4 py-2 font-semibold text-gray-600">Used</th>
                        <th class="text-left px-4 py-2 font-semibold text-gray-600">Approved %</th>
                        <th class="text-left px-4 py-2 font-semibold text-gray-600">Rejected %</th>
                    </tr>
                </thead>
                <tbody>
                    {% for h in top_hashtags %}
                    <tr class="border-t">
                        <td class="px-4 py-2 font-medium text-indigo-600">{{ h.tag }}</td>
                        <td class="px-4 py-2">{{ h.count }}</td>
                        <td class="px-4 py-2">
                            <span class="text-green-600 font-semibold">{{ h.approved_pct }}%</span>
                        </td>
                        <td class="px-4 py-2">
                            <span class="text-red-500">{{ h.rejected_pct }}%</span>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-center text-gray-400 py-8">No hashtag data yet</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/analytics.html
git commit -m "feat: add analytics dashboard page with charts and hashtag table"
```

---

### Task 7: Add Recycle button and Recycled badge to content cards

**Files:**
- Modify: `app/templates/partials/content_card.html`

- [ ] **Step 1: Add Recycled badge to the badges row**

In `app/templates/partials/content_card.html`, find the scheduled date span (line 38):

```html
                <span class="text-xs text-gray-400">{{ piece.scheduled_date }} {{ piece.scheduled_time or '' }}</span>
```

Add this AFTER it:

```html
                {% if piece.recycled_from %}
                <span class="text-xs font-semibold px-2 py-0.5 rounded bg-purple-100 text-purple-700">Recycled</span>
                {% endif %}
```

- [ ] **Step 2: Add Recycle button to the actions row**

Find the Reject button block (lines 76-82):

```html
        {% if piece.status != 'rejected' %}
        <button hx-post="/api/content/{{ piece.id }}/reject" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
                hx-disabled-elt="this"
                class="px-4 py-1.5 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition disabled:opacity-50">
            Reject
        </button>
        {% endif %}
```

Add this AFTER the `{% endif %}` on line 82:

```html
        {% if piece.status in ('approved', 'posted', 'queued') %}
        <button hx-post="/api/content/{{ piece.id }}/recycle" hx-target="#card-{{ piece.id }}" hx-swap="afterend"
                hx-disabled-elt="this"
                class="px-4 py-1.5 bg-purple-500 text-white text-sm rounded hover:bg-purple-600 transition disabled:opacity-50">
            Recycle
        </button>
        {% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/partials/content_card.html
git commit -m "feat: add Recycle button and Recycled badge to content cards"
```

---

### Task 8: Integration test — verify all Group A features

**Files:** None (manual testing)

- [ ] **Step 1: Start the app**

```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Verify DB migration**

Check that `recycled_from` column exists:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/content.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(content_pieces)').fetchall()]
print('recycled_from exists:', 'recycled_from' in cols)
conn.close()
"
```

- [ ] **Step 3: Test analytics page**

1. Navigate to `/dashboard/analytics`
2. Verify summary cards show correct counts
3. Check platform and category breakdowns display
4. Verify weekly history chart renders
5. Check top hashtags table appears

- [ ] **Step 4: Test sidebar nav**

Verify "Analytics" link appears in the sidebar between Library and Blog Posts.

- [ ] **Step 5: Test recycle button**

1. Go to Review Queue, filter by "approved" status
2. Verify "Recycle" button appears on approved cards
3. Click Recycle — should show success message with new post ID
4. Go to Review Queue (pending) — recycled post should appear with "Recycled" badge

- [ ] **Step 6: Verify smart scheduling**

The smart scheduling integrates into content generation. Verify the `_get_week_schedule` function is correctly defined by checking the import works:
```bash
python3 -c "from app.services.content_generator import _get_week_schedule; print('OK')"
```

---

### Task 9: Deploy to production

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
curl -s -c /tmp/cookies.txt -X POST -d "password=..." http://104.131.74.47:8000/login
curl -s -b /tmp/cookies.txt -o /dev/null -w "%{http_code}" http://104.131.74.47:8000/dashboard/analytics
```

Expected: All return 200.

# Content Generation UX Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add phone mockup previews, 3 caption variants per social post, and a swipe-style batch approve carousel to the Zerona Content Engine.

**Architecture:** Database gets two new columns for variant storage. Claude prompt updated to return 3 tonal variants per post. New API endpoints for preview and variant selection. New batch review page with client-side carousel navigation and keyboard shortcuts.

**Tech Stack:** FastAPI, SQLite, Jinja2, HTMX, Tailwind CSS (CDN), Anthropic Claude API

---

### Task 1: Database Migration — Add Variant Columns

**Files:**
- Modify: `app/database.py:19-60`

- [ ] **Step 1: Add migration columns to init_db()**

In `app/database.py`, add ALTER TABLE statements after the CREATE TABLE block inside `init_db()`. SQLite doesn't support IF NOT EXISTS on ALTER TABLE, so wrap each in a try/except to handle the "duplicate column" error gracefully.

```python
def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS content_pieces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT,
            body TEXT NOT NULL,
            hashtags TEXT,
            image_prompt TEXT,
            image_url TEXT,
            image_local_path TEXT,
            scheduled_date DATE,
            scheduled_time TIME,
            status TEXT DEFAULT 'pending',
            buffer_post_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_body TEXT,
            rejection_reason TEXT,
            generation_batch TEXT
        );

        CREATE TABLE IF NOT EXISTS content_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start DATE NOT NULL,
            planned_posts INTEGER DEFAULT 0,
            approved_posts INTEGER DEFAULT 0,
            posted_posts INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS system_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Migration: add variant columns (idempotent)
    for col_sql in [
        "ALTER TABLE content_pieces ADD COLUMN caption_variants TEXT",
        "ALTER TABLE content_pieces ADD COLUMN selected_variant INTEGER DEFAULT 0",
    ]:
        try:
            conn.execute(col_sql)
        except Exception:
            pass  # Column already exists

    conn.commit()
    conn.close()
```

- [ ] **Step 2: Verify migration works**

Run: `cd /Users/philipsmith/zerona-content-engine && python -c "from app.database import init_db; init_db(); print('OK')"`

Expected: `OK` — no errors, columns added (or already exist).

- [ ] **Step 3: Verify existing data is intact**

Run: `cd /Users/philipsmith/zerona-content-engine && python -c "from app.database import get_content_pieces; pieces = get_content_pieces(limit=5); print(f'{len(pieces)} pieces, keys: {list(pieces[0].keys()) if pieces else \"empty\"}')"`

Expected: Shows existing pieces with `caption_variants` and `selected_variant` in the key list (values will be None for existing rows).

- [ ] **Step 4: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/database.py
git commit -m "feat: add caption_variants and selected_variant columns to content_pieces"
```

---

### Task 2: Update Social Media Prompt for 3 Variants

**Files:**
- Modify: `prompts/social_media.txt`

- [ ] **Step 1: Update the output format section of the prompt**

Replace the OUTPUT FORMAT section at the end of `prompts/social_media.txt` (starting from line 53 `OUTPUT FORMAT:` through the end of the file) with:

```
OUTPUT FORMAT: Return valid JSON array with this structure for each post:
{
  "platform": "facebook" | "instagram",
  "category": "education" | "social_proof" | "behind_scenes" | "patient_stories" | "lifestyle",
  "title": "Short hook/title",
  "captions": [
    {"tone": "professional", "caption": "Polished, authoritative caption..."},
    {"tone": "conversational", "caption": "Friendly, casual caption..."},
    {"tone": "story_driven", "caption": "Narrative-style caption with a mini story..."}
  ],
  "hashtags": "#zerona #bodycontouring ...",
  "image_prompt": "Detailed image generation prompt...",
  "suggested_time": "10:00 AM",
  "cta": "Book your free consultation: [link]"
}

IMPORTANT: Each post MUST include exactly 3 captions in the "captions" array — one for each tone. All three should convey the same core message but with different voice/style. The "professional" tone is polished and authoritative. The "conversational" tone is casual and friendly. The "story_driven" tone uses a mini narrative or scenario.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add prompts/social_media.txt
git commit -m "feat: update social prompt to generate 3 caption variants per post"
```

---

### Task 3: Update Content Generator to Store Variants

**Files:**
- Modify: `app/services/content_generator.py:109-128`

- [ ] **Step 1: Update the post insertion loop in generate_weekly_social()**

Replace the `ids = []` loop (lines 109-128) with code that parses the new `captions` array format and stores variants:

```python
    ids = []
    for i, post in enumerate(posts):
        slot = schedule[i] if i < len(schedule) else schedule[-1]
        content_type = f"social_{slot['platform'][:2]}"

        # Handle both old format (single "caption") and new format ("captions" array)
        captions_list = post.get("captions", [])
        if captions_list and isinstance(captions_list, list):
            # New 3-variant format
            default_body = captions_list[0].get("caption", "")
            caption_variants = json.dumps(captions_list)
        else:
            # Fallback: single caption (old format or parsing error)
            default_body = post.get("caption", "")
            caption_variants = json.dumps([
                {"tone": "professional", "caption": default_body},
                {"tone": "conversational", "caption": default_body},
                {"tone": "story_driven", "caption": default_body},
            ])

        row_id = insert_content_piece({
            "content_type": content_type,
            "category": post.get("category", "education"),
            "title": post.get("title", ""),
            "body": default_body,
            "hashtags": post.get("hashtags", ""),
            "image_prompt": post.get("image_prompt", ""),
            "scheduled_date": slot["date"],
            "scheduled_time": slot["time"],
            "status": "pending",
            "generation_batch": batch_id,
            "caption_variants": caption_variants,
            "selected_variant": 0,
        })
        ids.append(row_id)
```

- [ ] **Step 2: Verify the generator still works with a dry run**

Run: `cd /Users/philipsmith/zerona-content-engine && python -c "from app.services.content_generator import _parse_json_response; print('import OK')"`

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/services/content_generator.py
git commit -m "feat: store 3 caption variants per social post in content generator"
```

---

### Task 4: Add Select-Variant and Preview API Endpoints

**Files:**
- Modify: `app/routes/api.py`

- [ ] **Step 1: Add the import for json at the top of api.py**

Add `import json` to the imports at the top of `app/routes/api.py`:

```python
import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import (
    get_content_pieces, update_content_status, get_db, log_event,
)
```

- [ ] **Step 2: Add the select-variant endpoint**

Add this endpoint after the existing `edit_content` endpoint (after line 61):

```python
@router.post("/content/{content_id}/select-variant", response_class=HTMLResponse)
async def select_variant(request: Request, content_id: int, variant: int = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    if variant not in (0, 1, 2):
        return HTMLResponse("Invalid variant", status_code=400)
    conn = get_db()
    row = conn.execute("SELECT caption_variants FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row or not row["caption_variants"]:
        return _render_card(request, content_id)
    variants = json.loads(row["caption_variants"])
    chosen_caption = variants[variant].get("caption", "")
    update_content_status(content_id, "pending", body=chosen_caption, selected_variant=variant, edited_body=None)
    return _render_card(request, content_id)
```

- [ ] **Step 3: Add the JSON select-variant endpoint for the carousel**

Add this endpoint right after the HTML one:

```python
@router.post("/content/{content_id}/select-variant-json")
async def select_variant_json(request: Request, content_id: int):
    if not _auth_check(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    body = await request.json()
    variant = body.get("variant", 0)
    if variant not in (0, 1, 2):
        return JSONResponse({"error": "Invalid variant"}, status_code=400)
    conn = get_db()
    row = conn.execute("SELECT caption_variants FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row or not row["caption_variants"]:
        return JSONResponse({"ok": True})
    variants = json.loads(row["caption_variants"])
    chosen_caption = variants[variant].get("caption", "")
    update_content_status(content_id, "pending", body=chosen_caption, selected_variant=variant, edited_body=None)
    return JSONResponse({"ok": True, "caption": chosen_caption})
```

- [ ] **Step 4: Add the preview endpoint**

Add this endpoint after the select-variant endpoints:

```python
@router.get("/content/{content_id}/preview", response_class=HTMLResponse)
async def phone_preview(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if not row:
        return HTMLResponse("Not found", status_code=404)
    piece = dict(row)
    return templates.TemplateResponse("partials/phone_preview.html", {"request": request, "piece": piece})
```

- [ ] **Step 5: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/api.py
git commit -m "feat: add select-variant and phone-preview API endpoints"
```

---

### Task 5: Create Phone Preview Partial Template

**Files:**
- Create: `app/templates/partials/phone_preview.html`

- [ ] **Step 1: Create the phone preview template**

```html
<div class="flex justify-center py-4">
    <div style="width:260px;border:4px solid #1f2937;border-radius:28px;padding:8px;background:#000;">
        <div style="background:white;border-radius:20px;overflow:hidden;">
            <!-- Profile header -->
            <div style="padding:8px 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #f3f4f6;">
                <div style="width:28px;height:28px;background:#0EA5A0;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:9px;font-weight:bold;">WH</div>
                <span style="font-size:11px;font-weight:600;color:#1f2937;">White House Chiro</span>
            </div>
            <!-- Image -->
            {% if piece.image_url and piece.image_url != '/static/css/placeholder.png' %}
            <img src="{{ piece.image_url }}" alt=""
                 style="width:100%;{% if 'ig' in piece.content_type %}aspect-ratio:1/1;{% else %}aspect-ratio:1.9/1;{% endif %}object-fit:cover;">
            {% else %}
            <div style="width:100%;{% if 'ig' in piece.content_type %}aspect-ratio:1/1;{% else %}aspect-ratio:1.9/1;{% endif %}background:linear-gradient(135deg,#0EA5A0,#1B2A4A);display:flex;align-items:center;justify-content:center;color:white;font-size:12px;">
                Image preview
            </div>
            {% endif %}
            <!-- Caption -->
            <div style="padding:10px 12px;">
                <p style="font-size:11px;color:#374151;margin:0;line-height:1.4;white-space:pre-line;">{{ (piece.edited_body or piece.body)[:300] }}{% if (piece.edited_body or piece.body)|length > 300 %}...{% endif %}</p>
                {% if piece.hashtags %}
                <p style="font-size:10px;color:#6366f1;margin-top:6px;">{{ piece.hashtags[:100] }}</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/templates/partials/phone_preview.html
git commit -m "feat: add phone mockup preview partial template"
```

---

### Task 6: Add Variant Picker and Preview Toggle to Content Cards

**Files:**
- Modify: `app/templates/partials/content_card.html`

- [ ] **Step 1: Replace the full content_card.html template**

Replace the entire contents of `app/templates/partials/content_card.html`:

```html
<div class="content-card bg-white rounded-lg shadow-sm p-4 border" id="card-{{ piece.id }}">
    <div class="flex gap-4">
        <!-- Image -->
        <div class="w-32 h-32 flex-shrink-0 rounded overflow-hidden bg-gray-100">
            {% if piece.image_url and piece.image_url != '/static/css/placeholder.png' %}
            <img src="{{ piece.image_url }}" alt="" class="w-full h-full object-cover cursor-pointer"
                 onclick="document.getElementById('lightbox-{{ piece.id }}').classList.remove('hidden')">
            {% else %}
            <div class="w-full h-full flex items-center justify-center text-gray-400 text-xs">No image</div>
            {% endif %}
        </div>

        <!-- Lightbox -->
        {% if piece.image_url and piece.image_url != '/static/css/placeholder.png' %}
        <div id="lightbox-{{ piece.id }}" class="hidden fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-8"
             onclick="this.classList.add('hidden')">
            <img src="{{ piece.image_url }}" alt="" class="max-w-full max-h-full rounded-lg shadow-2xl">
        </div>
        {% endif %}

        <!-- Content -->
        <div class="flex-1 min-w-0">
            <div class="flex gap-2 mb-2 flex-wrap">
                <span class="text-xs font-semibold px-2 py-0.5 rounded
                    {% if 'fb' in piece.content_type %}bg-blue-100 text-blue-700{% else %}bg-pink-100 text-pink-700{% endif %}">
                    {{ piece.content_type|replace('social_', '')|upper }}
                </span>
                <span class="text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                    {{ piece.category }}
                </span>
                <span class="text-xs font-semibold px-2 py-0.5 rounded
                    {% if piece.status == 'pending' %}bg-yellow-100 text-yellow-700
                    {% elif piece.status == 'approved' %}bg-green-100 text-green-700
                    {% elif piece.status == 'rejected' %}bg-red-100 text-red-700
                    {% else %}bg-gray-100 text-gray-600{% endif %}">
                    {{ piece.status|upper }}
                </span>
                <span class="text-xs text-gray-400">{{ piece.scheduled_date }} {{ piece.scheduled_time or '' }}</span>
            </div>

            {% if piece.title %}
            <p class="font-semibold text-navy text-sm mb-1">{{ piece.title }}</p>
            {% endif %}

            <div id="body-{{ piece.id }}">
                <p class="text-sm text-gray-700 whitespace-pre-line">{{ piece.edited_body or piece.body }}</p>
            </div>

            {% if piece.hashtags %}
            <p class="text-xs text-teal mt-2">{{ piece.hashtags }}</p>
            {% endif %}
        </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-2 mt-3 pt-3 border-t flex-wrap items-center">
        {% if piece.status != 'approved' %}
        <button hx-post="/api/content/{{ piece.id }}/approve" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
                hx-disabled-elt="this"
                class="px-4 py-1.5 bg-green-500 text-white text-sm rounded hover:bg-green-600 transition disabled:opacity-50">
            Approve
        </button>
        {% endif %}
        <button onclick="document.getElementById('edit-{{ piece.id }}').classList.toggle('hidden')"
                class="px-4 py-1.5 bg-yellow-500 text-white text-sm rounded hover:bg-yellow-600 transition">
            Edit Text
        </button>
        <button onclick="document.getElementById('preview-{{ piece.id }}').classList.toggle('hidden')"
                class="px-4 py-1.5 bg-gray-500 text-white text-sm rounded hover:bg-gray-600 transition">
            Preview
        </button>
        <button onclick="document.getElementById('regen-{{ piece.id }}').classList.toggle('hidden')"
                class="px-4 py-1.5 bg-indigo-500 text-white text-sm rounded hover:bg-indigo-600 transition">
            New Image
        </button>
        {% if piece.status != 'rejected' %}
        <button hx-post="/api/content/{{ piece.id }}/reject" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
                hx-disabled-elt="this"
                class="px-4 py-1.5 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition disabled:opacity-50">
            Reject
        </button>
        {% endif %}
    </div>

    <!-- Phone Preview (hidden) -->
    <div id="preview-{{ piece.id }}" class="hidden mt-3 pt-3 border-t"
         hx-get="/api/content/{{ piece.id }}/preview" hx-trigger="intersect once" hx-swap="innerHTML">
    </div>

    <!-- Variant Picker Cards -->
    {% if piece.caption_variants %}
    <div class="mt-3 pt-3 border-t">
        <p class="text-xs font-semibold text-gray-500 mb-2">Caption Variants — click to select</p>
        <div class="space-y-2" id="variants-{{ piece.id }}">
            <script>
                (function() {
                    var variants = {{ piece.caption_variants | safe }};
                    var selected = {{ piece.selected_variant or 0 }};
                    var container = document.getElementById('variants-{{ piece.id }}');
                    var toneLabels = {"professional": "Professional", "conversational": "Conversational", "story_driven": "Story-driven"};
                    variants.forEach(function(v, idx) {
                        var div = document.createElement('div');
                        var isSelected = idx === selected;
                        div.className = 'p-3 rounded-lg border-2 cursor-pointer transition ' +
                            (isSelected ? 'border-teal bg-teal/5' : 'border-gray-200 hover:border-gray-300');
                        div.innerHTML = '<div class="flex justify-between items-center mb-1">' +
                            '<span class="text-xs font-semibold ' + (isSelected ? 'text-teal' : 'text-gray-500') + '">' +
                            (toneLabels[v.tone] || v.tone).toUpperCase() + '</span>' +
                            (isSelected ? '<span class="text-xs bg-teal text-white px-2 py-0.5 rounded">Selected</span>' : '') +
                            '</div>' +
                            '<p class="text-sm text-gray-700">' + v.caption.substring(0, 200) + (v.caption.length > 200 ? '...' : '') + '</p>';
                        div.onclick = function() {
                            var form = new FormData();
                            form.append('variant', idx);
                            fetch('/api/content/{{ piece.id }}/select-variant', {method:'POST', body: form})
                                .then(function(r) { return r.text(); })
                                .then(function(html) {
                                    document.getElementById('card-{{ piece.id }}').outerHTML = html;
                                });
                        };
                        container.appendChild(div);
                    });
                })();
            </script>
        </div>
    </div>
    {% endif %}

    <!-- Edit Text Form (hidden) -->
    <div id="edit-{{ piece.id }}" class="hidden mt-3 pt-3 border-t">
        <label class="block text-xs font-semibold text-gray-500 mb-1">Edit Caption</label>
        <form hx-post="/api/content/{{ piece.id }}/edit" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML">
            <textarea name="body" rows="5" class="w-full border rounded p-2 text-sm mb-2">{{ piece.edited_body or piece.body }}</textarea>
            <div class="flex gap-2">
                <button type="submit" name="action" value="save" class="px-4 py-1.5 bg-teal text-white text-sm rounded hover:bg-teal/90 transition">
                    Save Edit
                </button>
                <button type="submit" name="action" value="save_approve" class="px-4 py-1.5 bg-green-500 text-white text-sm rounded hover:bg-green-600 transition">
                    Save & Approve
                </button>
            </div>
        </form>
    </div>

    <!-- Regenerate Image Form (hidden) -->
    <div id="regen-{{ piece.id }}" class="hidden mt-3 pt-3 border-t">
        <label class="block text-xs font-semibold text-gray-500 mb-1">Image Prompt</label>
        <form hx-post="/api/content/{{ piece.id }}/regenerate-image" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
              hx-indicator="#regen-spinner-{{ piece.id }}">
            <textarea name="image_prompt" rows="3" class="w-full border rounded p-2 text-sm mb-2" placeholder="Leave blank to use the original prompt">{{ piece.image_prompt }}</textarea>
            <button type="submit" hx-disabled-elt="this"
                    class="px-4 py-1.5 bg-indigo-500 text-white text-sm rounded hover:bg-indigo-600 transition disabled:opacity-50">
                Generate New Image
            </button>
            <span id="regen-spinner-{{ piece.id }}" class="htmx-indicator ml-2 text-gray-500 text-sm">
                <svg class="inline w-4 h-4 animate-spin mr-1" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" class="opacity-25"></circle><path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="4" class="opacity-75" stroke-linecap="round"></path></svg>
                Generating image...
            </span>
        </form>
    </div>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/templates/partials/content_card.html
git commit -m "feat: add variant picker and preview toggle to content cards"
```

---

### Task 7: Add Batch Review Button to Review Page

**Files:**
- Modify: `app/templates/review.html`

- [ ] **Step 1: Add the Batch Review button next to Approve All Pending**

Replace the header div (lines 5-11) in `app/templates/review.html`:

```html
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Review Queue</h2>
        <div class="flex gap-2">
            {% if pieces and current_status == 'pending' %}
            <a href="/dashboard/batch-review"
               class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
                Batch Review
            </a>
            {% endif %}
            <button hx-post="/api/content/approve-all" hx-target="#review-list" hx-swap="innerHTML"
                    class="bg-green-500 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-green-600 transition">
                Approve All Pending
            </button>
        </div>
    </div>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/templates/review.html
git commit -m "feat: add batch review button to review queue page"
```

---

### Task 8: Add Batch Review Route

**Files:**
- Modify: `app/routes/dashboard.py`

- [ ] **Step 1: Add the batch-review route**

Add `import json` to the top imports of `app/routes/dashboard.py`, then add this route after the existing `review` route (after line 58):

```python
@router.get("/batch-review", response_class=HTMLResponse)
async def batch_review(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    pieces = get_content_pieces(status="pending", limit=200)
    pieces = [p for p in pieces if p["content_type"] != "blog"]
    # Parse caption_variants from JSON string to list for template
    for p in pieces:
        if p.get("caption_variants") and isinstance(p["caption_variants"], str):
            try:
                p["caption_variants_parsed"] = json.loads(p["caption_variants"])
            except (json.JSONDecodeError, TypeError):
                p["caption_variants_parsed"] = []
        else:
            p["caption_variants_parsed"] = []
    return templates.TemplateResponse("batch_review.html", {
        "request": request, "active": "review",
        "pieces": pieces, "pieces_json": json.dumps(pieces, default=str),
    })
```

- [ ] **Step 2: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/routes/dashboard.py
git commit -m "feat: add batch-review dashboard route"
```

---

### Task 9: Create Batch Review Carousel Template

**Files:**
- Create: `app/templates/batch_review.html`

- [ ] **Step 1: Create the batch review carousel page**

```html
{% extends "base.html" %}
{% block title %}Batch Review - Zerona Content Engine{% endblock %}
{% block content %}
<div id="batch-app">
    <!-- Top bar -->
    <div class="bg-navy text-white px-6 py-4 rounded-t-xl flex justify-between items-center mb-0">
        <div class="flex items-center gap-4">
            <a href="/dashboard/review" class="text-gray-400 hover:text-white text-sm">&larr; Back</a>
            <span class="text-lg font-bold">Batch Review</span>
        </div>
        <span id="progress-text" class="text-sm text-gray-300"></span>
    </div>

    <!-- Progress dots -->
    <div class="bg-navy/90 px-6 py-2 flex gap-1.5 flex-wrap rounded-b-xl mb-6" id="progress-dots"></div>

    <!-- Empty state -->
    <div id="empty-state" class="hidden text-center py-16">
        <p class="text-xl text-gray-500 mb-2">No pending posts to review</p>
        <a href="/dashboard/review" class="text-teal hover:underline">Back to Review Queue</a>
    </div>

    <!-- Main review area -->
    <div id="review-area" class="bg-white rounded-xl shadow-sm border p-6">
        <div class="flex gap-8">
            <!-- Left: Phone preview -->
            <div class="flex-shrink-0" id="phone-preview-area">
                <!-- Filled by JS -->
            </div>

            <!-- Right: Controls -->
            <div class="flex-1 min-w-0">
                <!-- Badges -->
                <div class="flex gap-2 mb-4 flex-wrap" id="badges-area"></div>

                <!-- Variant picker -->
                <div class="mb-4" id="variant-picker">
                    <p class="text-xs font-semibold text-gray-500 mb-2">Caption variant:</p>
                    <div class="flex gap-2" id="variant-buttons"></div>
                </div>

                <!-- Variant preview cards -->
                <div class="space-y-2 mb-4" id="variant-cards"></div>

                <!-- Editable caption -->
                <div class="mb-4">
                    <label class="text-xs font-semibold text-gray-500 mb-1 block">Caption (editable)</label>
                    <textarea id="caption-editor" rows="5"
                              class="w-full border rounded-lg p-3 text-sm resize-none focus:ring-2 focus:ring-teal focus:border-teal"></textarea>
                </div>

                <!-- Action buttons -->
                <div class="flex gap-3 items-center">
                    <button onclick="approveAndNext()"
                            class="flex-1 bg-green-500 text-white px-6 py-3 rounded-lg text-sm font-semibold hover:bg-green-600 transition">
                        Approve & Next &rarr;
                    </button>
                    <button onclick="rejectAndNext()"
                            class="bg-red-500 text-white px-4 py-3 rounded-lg text-sm hover:bg-red-600 transition">
                        Reject
                    </button>
                    <button onclick="skipToNext()"
                            class="bg-gray-400 text-white px-4 py-3 rounded-lg text-sm hover:bg-gray-500 transition">
                        Skip
                    </button>
                </div>

                <!-- Keyboard hints -->
                <p class="text-xs text-gray-400 mt-3">
                    <kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs">A</kbd> approve
                    <kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs ml-2">R</kbd> reject
                    <kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs ml-2">S</kbd> skip
                    <kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs ml-2">&larr;</kbd><kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs">&rarr;</kbd> navigate
                    <kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs ml-2">1-3</kbd> variant
                    <kbd class="bg-gray-100 px-1.5 py-0.5 rounded text-xs ml-2">E</kbd> edit
                </p>
            </div>
        </div>
    </div>

    <!-- Summary (hidden until done) -->
    <div id="summary" class="hidden bg-white rounded-xl shadow-sm border p-8 text-center">
        <h3 class="text-2xl font-bold text-navy mb-4">Review Complete</h3>
        <div id="summary-stats" class="text-lg text-gray-600 mb-6"></div>
        <a href="/dashboard/review" class="bg-teal text-white px-6 py-3 rounded-lg font-semibold hover:bg-teal/90 transition">
            Back to Review Queue
        </a>
    </div>
</div>

<script>
(function() {
    var posts = {{ pieces_json | safe }};
    var currentIndex = 0;
    var results = {}; // id -> 'approved' | 'rejected' | 'skipped'
    var selectedVariants = {}; // id -> variant index

    if (posts.length === 0) {
        document.getElementById('empty-state').classList.remove('hidden');
        document.getElementById('review-area').classList.add('hidden');
        return;
    }

    function getVariants(post) {
        var cv = post.caption_variants_parsed || [];
        if (cv.length === 0 && post.caption_variants) {
            try { cv = JSON.parse(post.caption_variants); } catch(e) { cv = []; }
        }
        return cv;
    }

    function renderPost() {
        var post = posts[currentIndex];
        if (!post) { showSummary(); return; }

        var variants = getVariants(post);
        var selVar = selectedVariants[post.id] !== undefined ? selectedVariants[post.id] : (post.selected_variant || 0);
        var caption = post.edited_body || post.body;
        if (variants.length > selVar) {
            caption = variants[selVar].caption || caption;
        }

        // Progress
        document.getElementById('progress-text').textContent = (currentIndex + 1) + ' of ' + posts.length + ' posts';
        renderDots();

        // Badges
        var platform = post.content_type.replace('social_', '').toUpperCase();
        var platformClass = post.content_type.includes('fb') ? 'bg-blue-100 text-blue-700' : 'bg-pink-100 text-pink-700';
        document.getElementById('badges-area').innerHTML =
            '<span class="text-xs font-semibold px-2 py-0.5 rounded ' + platformClass + '">' + platform + '</span>' +
            '<span class="text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-600">' + (post.category || '') + '</span>' +
            '<span class="text-xs text-gray-400">' + (post.scheduled_date || '') + ' ' + (post.scheduled_time || '') + '</span>';

        // Phone preview
        var imgHtml = '';
        if (post.image_url && post.image_url !== '/static/css/placeholder.png') {
            var aspect = post.content_type.includes('ig') ? 'aspect-ratio:1/1;' : 'aspect-ratio:1.9/1;';
            imgHtml = '<img src="' + post.image_url + '" style="width:100%;' + aspect + 'object-fit:cover;">';
        } else {
            var aspect = post.content_type.includes('ig') ? 'aspect-ratio:1/1;' : 'aspect-ratio:1.9/1;';
            imgHtml = '<div style="width:100%;' + aspect + 'background:linear-gradient(135deg,#0EA5A0,#1B2A4A);display:flex;align-items:center;justify-content:center;color:white;font-size:12px;">Image preview</div>';
        }
        var hashHtml = post.hashtags ? '<p style="font-size:10px;color:#6366f1;margin-top:6px;">' + post.hashtags.substring(0, 100) + '</p>' : '';
        document.getElementById('phone-preview-area').innerHTML =
            '<div style="width:240px;border:4px solid #1f2937;border-radius:28px;padding:8px;background:#000;">' +
                '<div style="background:white;border-radius:20px;overflow:hidden;">' +
                    '<div style="padding:8px 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #f3f4f6;">' +
                        '<div style="width:24px;height:24px;background:#0EA5A0;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:8px;font-weight:bold;">WH</div>' +
                        '<span style="font-size:10px;font-weight:600;">White House Chiro</span>' +
                    '</div>' +
                    imgHtml +
                    '<div style="padding:10px 12px;">' +
                        '<p style="font-size:10px;color:#374151;margin:0;line-height:1.4;white-space:pre-line;">' + caption.substring(0, 250) + '</p>' +
                        hashHtml +
                    '</div>' +
                '</div>' +
            '</div>';

        // Variant buttons
        var toneLabels = {professional: 'A — Professional', conversational: 'B — Conversational', story_driven: 'C — Story-driven'};
        var btnsHtml = '';
        if (variants.length > 0) {
            variants.forEach(function(v, idx) {
                var active = idx === selVar;
                btnsHtml += '<button onclick="selectVariant(' + idx + ')" class="px-3 py-1.5 rounded text-sm font-medium transition ' +
                    (active ? 'bg-teal text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200') + '">' +
                    (toneLabels[v.tone] || ('Variant ' + (idx+1))) + '</button>';
            });
            document.getElementById('variant-picker').classList.remove('hidden');
        } else {
            document.getElementById('variant-picker').classList.add('hidden');
        }
        document.getElementById('variant-buttons').innerHTML = btnsHtml;

        // Variant preview cards
        var cardsHtml = '';
        if (variants.length > 0) {
            variants.forEach(function(v, idx) {
                var active = idx === selVar;
                cardsHtml += '<div onclick="selectVariant(' + idx + ')" class="p-3 rounded-lg border-2 cursor-pointer transition text-sm ' +
                    (active ? 'border-teal bg-teal/5' : 'border-gray-200 hover:border-gray-300') + '">' +
                    '<span class="text-xs font-semibold ' + (active ? 'text-teal' : 'text-gray-500') + '">' +
                    (toneLabels[v.tone] || v.tone).toUpperCase() + '</span>' +
                    (active ? ' <span class="text-xs bg-teal text-white px-2 py-0.5 rounded ml-1">Selected</span>' : '') +
                    '<p class="text-gray-700 mt-1">' + v.caption.substring(0, 200) + (v.caption.length > 200 ? '...' : '') + '</p></div>';
            });
        }
        document.getElementById('variant-cards').innerHTML = cardsHtml;

        // Caption editor
        document.getElementById('caption-editor').value = caption;
    }

    function renderDots() {
        var html = '';
        posts.forEach(function(p, idx) {
            var color = '#4b5563'; // gray = pending
            if (results[p.id] === 'approved') color = '#22c55e';
            else if (results[p.id] === 'rejected') color = '#ef4444';
            if (idx === currentIndex) color = '#0EA5A0';
            html += '<div style="width:10px;height:10px;border-radius:50%;background:' + color + ';' +
                (idx === currentIndex ? 'box-shadow:0 0 0 2px white;' : '') + '"></div>';
        });
        document.getElementById('progress-dots').innerHTML = html;
    }

    window.selectVariant = function(idx) {
        var post = posts[currentIndex];
        selectedVariants[post.id] = idx;
        // Save to server
        fetch('/api/content/' + post.id + '/select-variant-json', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({variant: idx})
        });
        renderPost();
    };

    function doAction(action) {
        var post = posts[currentIndex];
        var editedCaption = document.getElementById('caption-editor').value;

        // Save edited caption if changed
        var variants = getVariants(post);
        var selVar = selectedVariants[post.id] !== undefined ? selectedVariants[post.id] : (post.selected_variant || 0);
        var originalCaption = variants.length > selVar ? variants[selVar].caption : (post.edited_body || post.body);
        if (editedCaption !== originalCaption) {
            var formData = new FormData();
            formData.append('body', editedCaption);
            formData.append('action', 'save');
            fetch('/api/content/' + post.id + '/edit', {method: 'POST', body: formData});
        }

        if (action === 'approve') {
            fetch('/api/content/' + post.id + '/approve', {method: 'POST'});
            results[post.id] = 'approved';
        } else if (action === 'reject') {
            fetch('/api/content/' + post.id + '/reject', {method: 'POST'});
            results[post.id] = 'rejected';
        } else {
            results[post.id] = 'skipped';
        }

        currentIndex++;
        if (currentIndex >= posts.length) {
            showSummary();
        } else {
            renderPost();
        }
    }

    window.approveAndNext = function() { doAction('approve'); };
    window.rejectAndNext = function() { doAction('reject'); };
    window.skipToNext = function() { doAction('skip'); };

    function showSummary() {
        document.getElementById('review-area').classList.add('hidden');
        document.getElementById('summary').classList.remove('hidden');
        var approved = 0, rejected = 0, skipped = 0;
        Object.values(results).forEach(function(r) {
            if (r === 'approved') approved++;
            else if (r === 'rejected') rejected++;
            else skipped++;
        });
        // Count posts that were never acted on as skipped
        var untouched = posts.length - Object.keys(results).length;
        skipped += untouched;
        document.getElementById('summary-stats').innerHTML =
            posts.length + ' posts reviewed: ' +
            '<span class="text-green-600 font-semibold">' + approved + ' approved</span>, ' +
            '<span class="text-red-600 font-semibold">' + rejected + ' rejected</span>, ' +
            '<span class="text-gray-500">' + skipped + ' skipped</span>';
    }

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        var editor = document.getElementById('caption-editor');
        if (document.activeElement === editor) {
            if (e.key === 'Escape') { editor.blur(); e.preventDefault(); }
            return;
        }
        switch(e.key) {
            case 'a': case 'A': approveAndNext(); e.preventDefault(); break;
            case 'r': case 'R': rejectAndNext(); e.preventDefault(); break;
            case 's': case 'S': skipToNext(); e.preventDefault(); break;
            case 'e': case 'E': editor.focus(); e.preventDefault(); break;
            case 'ArrowRight': if (currentIndex < posts.length - 1) { currentIndex++; renderPost(); } e.preventDefault(); break;
            case 'ArrowLeft': if (currentIndex > 0) { currentIndex--; renderPost(); } e.preventDefault(); break;
            case '1': if (getVariants(posts[currentIndex]).length > 0) selectVariant(0); e.preventDefault(); break;
            case '2': if (getVariants(posts[currentIndex]).length > 1) selectVariant(1); e.preventDefault(); break;
            case '3': if (getVariants(posts[currentIndex]).length > 2) selectVariant(2); e.preventDefault(); break;
        }
    });

    // Initial render
    renderPost();
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add app/templates/batch_review.html
git commit -m "feat: add batch review carousel page with keyboard shortcuts"
```

---

### Task 10: Integration Test — Full Workflow

**Files:** None (manual testing)

- [ ] **Step 1: Start the app locally**

Run: `cd /Users/philipsmith/zerona-content-engine && python -m uvicorn app.main:app --reload --port 8000`

- [ ] **Step 2: Verify database migration**

Visit `http://localhost:8000/dashboard` and check no errors.

- [ ] **Step 3: Generate test posts with variants**

Click "Generate This Week's Posts Now" on the Overview page. Wait for generation to complete. Check the Review Queue — posts should now show caption variant cards below each post.

- [ ] **Step 4: Test variant selection**

On a content card, click a different variant (B or C). The card should refresh with the new caption.

- [ ] **Step 5: Test phone preview**

Click the "Preview" button on a content card. A phone-frame preview should appear below the card showing the image and caption.

- [ ] **Step 6: Test batch review carousel**

Click "Batch Review" button on the Review Queue page. The carousel should load with all pending posts. Test:
- Arrow keys to navigate
- 1/2/3 to switch variants
- A to approve and advance
- R to reject and advance
- S to skip
- E to focus editor, Escape to unfocus
- Progress dots update colors
- Summary appears at the end

- [ ] **Step 7: Final commit**

```bash
cd /Users/philipsmith/zerona-content-engine
git add -A
git commit -m "feat: complete content UX improvements — variants, preview, batch carousel"
```

---

### Task 11: Deploy to Production

**Files:** None (deployment)

- [ ] **Step 1: Deploy to the DigitalOcean droplet**

```bash
cd /Users/philipsmith/zerona-content-engine
ssh root@104.131.74.47 "cd /var/www/zerona-content-engine && git pull origin main && docker-compose down && docker-compose up -d --build"
```

If git is not set up on the server, use scp:

```bash
rsync -az --exclude 'data' --exclude '.git' --exclude '__pycache__' --exclude '.env' \
  /Users/philipsmith/zerona-content-engine/ root@104.131.74.47:/var/www/zerona-content-engine/
ssh root@104.131.74.47 "cd /var/www/zerona-content-engine && docker-compose down && docker-compose up -d --build"
```

- [ ] **Step 2: Verify the app is running**

Visit `http://104.131.74.47:8000/login` and log in. Navigate to Review Queue and confirm the new features are visible.

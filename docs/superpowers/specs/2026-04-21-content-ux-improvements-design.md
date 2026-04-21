# Group B: Content Generation UX Improvements

**Date:** 2026-04-21
**Scope:** Phone mockup previews, 3 caption variants, swipe-style batch approve carousel

---

## 1. Phone Mockup Preview

### What it does
Adds a toggleable phone-frame preview to each content card in the Review Queue. When toggled, the post's image and caption are displayed inside a simple phone-shaped border so the user can see roughly how it will look on a mobile device.

### Implementation

**New partial template:** `app/templates/partials/phone_preview.html`
- Renders a phone-shaped div (rounded rect border, black bezel) containing:
  - Small profile header (White House Chiro avatar + name)
  - Post image (full width inside frame)
  - Caption text below image
  - Hashtags in accent color
- Accepts `image_url`, `caption`, `hashtags`, and `platform` (fb/ig) as template variables
- Instagram frame is square (1:1 aspect); Facebook frame is landscape (roughly 1.9:1)

**Toggle mechanism:**
- Each content card in `review.html` gets a "Preview" button
- HTMX: `hx-get="/api/content/{id}/preview"` swaps in the phone preview partial
- Clicking again collapses it (simple toggle via HTMX `hx-swap="innerHTML"`)

**New endpoint:** `GET /api/content/{id}/preview`
- Returns rendered `phone_preview.html` partial for the given content piece
- Auth-protected (session required)

### Design decisions
- Simple phone frame only — no platform-specific UI elements (like buttons, comment sections)
- Preview is inline on the card, not a modal
- No new database changes needed

---

## 2. Three Caption Variants

### What it does
Instead of generating one caption per post, Claude generates three tonal variants: Professional, Conversational, and Story-driven. The user picks their favorite during review. The selected variant becomes the post body.

### Database changes

Add two columns to `content_pieces`:
- `caption_variants TEXT` — JSON string containing an array of 3 objects: `[{"tone": "Professional", "caption": "..."}, {"tone": "Conversational", "caption": "..."}, {"tone": "Story-driven", "caption": "..."}]`
- `selected_variant INTEGER DEFAULT 0` — index (0, 1, or 2) of the chosen variant

Migration: ALTER TABLE in `database.py`'s `init_db()` function (SQLite ALTER TABLE ADD COLUMN, with IF NOT EXISTS guard).

### Content generation changes

**Social media prompt (`prompts/social_media.txt`):**
- Modify the output format to return 3 `caption` values per post instead of 1
- Each variant gets a `tone` field: `"professional"`, `"conversational"`, `"story_driven"`
- The `image_prompt`, `hashtags`, and `CTA` remain shared across all 3 variants

**`app/services/content_generator.py`:**
- Parse the 3 variants from Claude's response
- Store as JSON in `caption_variants` column
- Set `body` to variant 0 (Professional) as the default selection
- Set `selected_variant` to 0

### New endpoint

`POST /api/content/{id}/select-variant`
- Body: `{"variant": 0|1|2}`
- Updates `selected_variant` and copies the chosen caption into `body`
- Returns updated card partial via HTMX

### UI integration

**Review queue (`review.html`):**
- Below the caption text, show 3 clickable variant cards (bordered boxes)
- Selected variant has teal border + "Selected" badge
- Clicking a variant fires HTMX POST to `/api/content/{id}/select-variant`
- Card re-renders with the new selection

**Batch review carousel** (see section 3) also includes the variant picker.

### Editing behavior
- If the user edits a caption after selecting a variant, the edit is saved to `edited_body` (existing field)
- `edited_body` takes precedence over `body` when posting to Buffer (existing behavior)

---

## 3. Swipe-Style Batch Approve Carousel

### What it does
A new full-screen page for reviewing all pending posts in sequence. Shows one post at a time with phone preview on the left, variant picker + editable caption + action buttons on the right. Keyboard shortcuts for speed.

### New page

**Route:** `GET /dashboard/batch-review`
**Template:** `app/templates/batch_review.html`

### Layout

**Top bar:**
- "Batch Review" title
- Progress indicator: "3 of 9 posts"
- Dot indicators: green = approved, red = rejected, teal = current, gray = pending

**Main area (split layout):**
- Left side: Phone mockup preview (reuses `phone_preview.html` partial)
- Right side:
  - Platform badge, category badge, scheduled date/time
  - Variant picker (3 buttons: A / B / C, highlighted selection)
  - Editable textarea with the selected caption
  - Action buttons: "Approve & Next" (green, primary), "Reject" (red), "Skip" (gray)
  - Keyboard shortcut hints

### Keyboard shortcuts
- `ArrowRight` / `ArrowLeft` — navigate between posts
- `a` — approve current post and advance to next
- `r` — reject current post and advance to next
- `s` — skip (advance without action)
- `1` / `2` / `3` — select variant A / B / C
- `e` — focus the caption textarea for editing

Implemented via a `<script>` block on `batch_review.html` listening for `keydown` events. Shortcuts are disabled when the textarea is focused (except Escape to unfocus).

### Data flow
- Page loads all pending posts as a JSON array embedded in a `<script>` tag
- Navigation is client-side (swap visible content, no page reload per post)
- Actions (approve, reject, select-variant, edit) use HTMX/fetch to call existing API endpoints
- After each action, the progress dots update client-side

### Navigation behavior
- "Approve & Next" approves the post and auto-advances to the next pending post
- "Reject" rejects and auto-advances
- "Skip" advances without changing status
- At the end of the queue, show a summary: "9 posts reviewed: 7 approved, 1 rejected, 1 skipped" with a "Back to Dashboard" button

### Entry point
- New "Batch Review" button on the Review Queue page (next to "Approve All Pending")
- Only visible when there are pending posts
- Sidebar nav does NOT get a new entry (accessed from Review page)

---

## Files to create or modify

### New files
- `app/templates/batch_review.html` — carousel page
- `app/templates/partials/phone_preview.html` — phone frame partial

### Modified files
- `app/database.py` — add `caption_variants` and `selected_variant` columns
- `app/services/content_generator.py` — generate 3 variants per post
- `prompts/social_media.txt` — update output format for 3 variants
- `app/routes/api.py` — add `select-variant` and `preview` endpoints
- `app/routes/dashboard.py` — add `batch-review` route
- `app/templates/review.html` — add variant picker, preview toggle, batch review button
- `app/templates/partials/content_card.html` — add preview toggle button

### No changes needed
- `app/auth.py` — existing session auth covers new routes
- `app/services/buffer_service.py` — already reads `edited_body || body`, no change needed
- `app/services/image_generator.py` — image generation unchanged
- `app/services/scheduler.py` — no scheduling changes
- `app/config.py` — no new config needed

---

## Out of scope for this spec
- Blog post variants (blog generation unchanged — only social posts get 3 variants)
- Platform-accurate mockups (just simple phone frame)
- Analytics or engagement tracking
- Content library, pagination, retry queue (Group D)

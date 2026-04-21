# Group A: Analytics & Smart Features

**Date:** 2026-04-21
**Scope:** Analytics dashboard, smart scheduling, content recycling, hashtag analytics

---

## 1. Analytics Dashboard

### What it does
A new page at `/dashboard/analytics` showing content performance statistics. All data derived from the `content_pieces` table — no external analytics service.

### New route
`GET /dashboard/analytics`
- Template: `app/templates/analytics.html`
- Sidebar nav gets an "Analytics" link (between Library and Blog Posts)

### Sections

**Summary cards (top row):**
- Total posts (all time)
- Posts this week (by `scheduled_date`)
- Posts this month
- Approval rate (approved / (approved + rejected) as percentage)

**Platform breakdown:**
- Two-column display: Facebook count/percentage, Instagram count/percentage
- Simple horizontal bar showing relative proportion (CSS width percentage)

**Category breakdown:**
- Table showing each category with post count
- Sorted by count descending

**Generation history:**
- Bar chart showing posts generated per week, last 8 weeks
- CSS-only bars (div with background color, width proportional to max week)
- X-axis: week labels (e.g., "Apr 7"), Y-axis: count

**Approval funnel:**
- Visual showing: Generated → Approved → Queued → Posted with counts at each stage
- Simple horizontal bars with count labels

### Database changes

New function in `app/database.py`:

`get_analytics_data() -> dict` — runs multiple aggregate queries:
- `SELECT status, COUNT(*) FROM content_pieces GROUP BY status`
- `SELECT content_type, COUNT(*) FROM content_pieces GROUP BY content_type`
- `SELECT category, COUNT(*) FROM content_pieces GROUP BY category`
- `SELECT strftime('%Y-%W', scheduled_date) as week, COUNT(*) FROM content_pieces GROUP BY week ORDER BY week DESC LIMIT 8`
- Count for current week: `WHERE scheduled_date >= date('now', 'weekday 0', '-6 days')`
- Count for current month: `WHERE strftime('%Y-%m', scheduled_date) = strftime('%Y-%m', 'now')`

Returns a dict with all aggregated data ready for the template.

### Design decisions
- No JavaScript chart library — CSS-only bars are sufficient and zero-dependency
- Single SQL function returns all analytics to minimize DB round trips
- No date range picker (shows all-time stats + recent 8 weeks)
- No caching — queries are fast on SQLite at this scale

---

## 2. Smart Scheduling

### What it does
When generating weekly social posts, auto-distributes them across the week with varied time slots instead of clustering on one day. Fills gaps in the existing schedule.

### Implementation

New function in `app/services/content_generator.py`:

`_distribute_schedule(num_posts: int, week_start: date) -> list[tuple[str, str]]`
- Queries existing posts scheduled for that week
- Defines preferred time slots: 9:00, 11:30, 14:00, 16:30, 19:00
- Distributes posts across Mon-Sat, skipping Sunday
- Avoids slots already taken by existing posts
- Returns list of `(date_str, time_str)` tuples

### Changes to generation flow
- In `generate_weekly_social()`, after creating post data but before inserting, call `_distribute_schedule()` to assign `scheduled_date` and `scheduled_time`
- Currently posts are generated with a fixed schedule — this replaces that with intelligent distribution

### Settings page
No new settings needed — the schedule distribution is automatic. The existing generation day/hour setting controls WHEN generation runs, not when posts are scheduled.

### Design decisions
- Distribution is deterministic (fills gaps left-to-right)
- No ML or external API — simple slot-filling algorithm
- Preferred times are hardcoded (common social media posting times)
- If more posts than available slots, wraps around and doubles up

---

## 3. Content Recycling

### What it does
Allows reusing approved/posted content by generating a fresh caption from Claude while keeping the same image, category, and hashtags.

### Database changes
Add column to `content_pieces`:
- `recycled_from INTEGER` — ID of the original content piece (NULL for original content)

Migration: ALTER TABLE in `init_db()` with IF NOT EXISTS guard.

### New endpoint
`POST /api/content/{id}/recycle`
- Auth-protected
- Fetches the original content piece
- Calls Claude with a "rewrite this caption with a fresh angle" prompt
- Creates a new `content_pieces` row with:
  - Same `content_type`, `category`, `hashtags`, `image_url`, `image_local_path`, `image_prompt`
  - New `body` from Claude's rewrite
  - `status = 'pending'`
  - `recycled_from = original_id`
  - `scheduled_date` and `scheduled_time` = NULL (user assigns during review)
- Returns the new card via HTMX or a success message

### Recycle prompt
Stored inline in the recycle endpoint (not a separate prompt file — it's short):
```
Rewrite this social media caption with a completely fresh angle. Keep the same topic and key message but change the tone, hook, and structure. Original caption: {body}
```

### UI integration
- "Recycle" button appears on content cards with status `approved` or `posted`
- Button: `hx-post="/api/content/{id}/recycle"` with a loading indicator
- Recycled posts show a small "Recycled" badge (purple) in their content card
- The badge links show `recycled_from` info: "Recycled from #{original_id}"

### Design decisions
- One recycle per click (not batch)
- Keeps original image (no re-generation)
- New post is fully independent after creation (editing the recycled post doesn't affect original)
- No limit on how many times a post can be recycled
- Caption variants (Group B feature) are NOT generated for recycled posts — just one fresh caption

---

## 4. Hashtag Analytics

### What it does
Shows hashtag usage statistics as a section within the Analytics page (not a separate page).

### Implementation
Add to `get_analytics_data()` in `app/database.py`:
- Query all `hashtags` fields from `content_pieces` where hashtags is not NULL
- Parse each hashtag string (space or comma separated, starting with #)
- Count occurrences of each unique hashtag
- Return top 20 by usage count
- Also group by status: count hashtags that appear in approved vs rejected posts

### Analytics template section
**Top Hashtags table:**
- Columns: Hashtag, Usage Count, Approved %, Rejected %
- Sorted by usage count descending
- Top 20 only
- Color-coded: green percentage for high approval rate, red for high rejection

### Design decisions
- Server-side parsing (Python splits hashtag strings, counts in a dict)
- No hashtag suggestions or auto-complete — just reporting
- Counts are per-post (a hashtag used in 5 posts = count of 5, regardless of how many times it appears in each post's hashtag field)

---

## Files to create or modify

### New files
- `app/templates/analytics.html` — analytics dashboard page

### Modified files
- `app/database.py` — add `recycled_from` column, add `get_analytics_data()`
- `app/services/content_generator.py` — add `_distribute_schedule()`, update generation flow
- `app/routes/dashboard.py` — add analytics route
- `app/routes/api.py` — add recycle endpoint
- `app/templates/base.html` — add Analytics to sidebar nav
- `app/templates/partials/content_card.html` — add Recycle button, Recycled badge

### No changes needed
- `app/auth.py` — existing session auth covers new routes
- `app/services/buffer_service.py` — unchanged
- `app/services/image_generator.py` — unchanged (recycling reuses existing images)
- `app/services/scheduler.py` — unchanged (smart scheduling is in content_generator)
- `app/services/retry_queue.py` — unchanged
- `prompts/social_media.txt` — unchanged (recycle uses inline prompt)

---

## Out of scope
- External analytics (Google Analytics, social platform insights)
- A/B testing of content variants
- Engagement metrics (likes, shares — would need social platform API integration)
- Automated recycling schedule
- Blog post recycling (social posts only)

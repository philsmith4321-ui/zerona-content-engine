# Zerona Content Engine — Design Specification

## Overview

Fully automated content generation and scheduling system for White House Chiropractic's Zerona Z6 cold laser body contouring service. Generates social media posts and blog articles via Claude API, creates matching images via Replicate Flux, queues to Buffer, with a web-based approval dashboard.

Production application on a DigitalOcean droplet ($6-12/month).

## Tech Stack

- **Backend:** Python 3.12+ / FastAPI
- **Database:** SQLite
- **Task Scheduling:** APScheduler (in-process)
- **AI Content:** Anthropic Claude API (claude-sonnet-4-20250514)
- **AI Images:** Replicate API / Flux Schnell (black-forest-labs/flux-schnell)
- **Social Scheduling:** Buffer API v1
- **Frontend:** Jinja2 templates + HTMX + Tailwind CSS (CDN)
- **Auth:** Single admin password (bcrypt hashed), session cookie
- **Deployment:** Docker + docker-compose on DigitalOcean

## Architecture

```
CRON SCHEDULER (APScheduler)
  ├── Weekly: Generate social posts (Sunday 6 AM CT)
  ├── Bi-weekly: Generate blog post (1st & 15th, 6 AM CT)
  ├── Daily: Queue approved posts to Buffer (7 AM CT)
  └── Daily: Send email digest of pending reviews
         │
    ┌────┴────┐
    │         │
Claude API  Replicate API
    │         │
    └────┬────┘
         │
     SQLite DB
         │
    ┌────┴────┐
    │         │
Dashboard   Buffer API
(HTMX)     (auto-queue)
```

## Database Schema

### content_pieces
- id, content_type (social_fb/social_ig/blog), category, title, body, hashtags
- image_prompt, image_url, image_local_path
- scheduled_date, scheduled_time, status (pending/approved/rejected/queued/posted/failed)
- buffer_post_id, edited_body, rejection_reason, generation_batch
- created_at, updated_at

### content_calendar
- id, week_start, planned_posts, approved_posts, posted_posts, created_at

### system_log
- id, event_type, message, details (JSON), created_at

## Content Generation

### Social Media (Weekly)
- 9 posts/week: 4 Facebook (Mon/Wed/Fri/Sat) + 5 Instagram (Mon/Tue/Wed/Fri/Sat)
- Rotates content pillars: Education 30%, Social Proof 25%, Behind Scenes 20%, Patient Stories 15%, Lifestyle 10%
- Passes last 2 weeks of generated captions as context to avoid repetition
- Prompt template stored in `prompts/social_media.txt` (editable via dashboard)
- Output: JSON array with platform, category, title, caption, hashtags, image_prompt, suggested_time, CTA

### Blog Posts (Bi-weekly)
- Pulls next unused topic from `config/blog_topics.json` (24 pre-loaded topics)
- 800-1,200 words, SEO-optimized with target keyword
- Output: JSON with title, meta_description, body_html, target_keyword, image_prompt, social caption

### Image Generation
- Flux Schnell via Replicate
- Sizes: 1024x1024 (Instagram), 1200x630 (Facebook), 1200x628 (blog hero)
- Saved locally to `media/images/`
- Retry button on dashboard for failed generations

### JSON Parsing Resilience
- Strip markdown code fences before parsing
- On parse failure, retry once with explicit "raw JSON only" instruction

## Brand Voice & Compliance

- Warm, confident, approachable — never clinical or body-shaming
- Forbidden words: "fix," "problem areas," "get rid of," "stubborn fat," "melt," "blast"
- Preferred words: feel confident, enhance, refresh, sculpt, contour, transform, non-invasive
- No before/after imagery, no specific weight loss claims
- Inch loss claims must reference clinical trials with "results may vary"
- Local community pride — White House, TN

## Dashboard (6 Pages)

### Auth
- Single password from env var, bcrypt hashed for comparison
- Session cookie after login

### 1. Overview (`/dashboard`)
- Stats bar: Pending / Approved / Queued / Published counts
- This week's content calendar grid
- Manual "Generate This Week's Posts Now" button

### 2. Review Queue (`/dashboard/review`)
- Card layout: image thumbnail, platform/category badges, editable caption, hashtags, schedule
- Actions: Approve / Edit & Approve / Reject
- Bulk "Approve All" button
- Filter by platform, category, status

### 3. Calendar (`/dashboard/calendar`)
- Month view, color-coded by status
- Click day to see posts

### 4. Blog Review (`/dashboard/blog`)
- Full rendered article preview
- Edit title/body/meta description
- Approve/Reject + social promotion preview

### 5. Settings (`/dashboard/settings`)
- Buffer connection test helper
- Prompt template editor
- Blog topic queue manager
- Content pillar distribution settings
- Email notification settings
- Next scheduled generation info

### 6. Logs (`/dashboard/logs`)
- Filterable system event log
- API costs per generation batch

### Design
- Navy (#1B2A4A) primary, Teal (#0EA5A0) accent
- Dark sidebar, light content area
- Mobile-responsive
- Tailwind CSS via CDN + HTMX for interactions

## API Integrations

### Anthropic Claude
- Model: claude-sonnet-4-20250514
- Anthropic Python SDK
- Prompts from `prompts/` directory
- Rate limiting + exponential backoff

### Replicate (Flux Schnell)
- `replicate` Python package
- Images saved locally, served via FastAPI static files
- Placeholder on failure + regenerate button

### Buffer v1
- GET /profiles.json — list profiles
- POST /updates/create.json — schedule post
- POST /updates/{id}/update.json — update post
- Access token auth
- Check queue capacity before scheduling
- Connection test helper in settings

### Email (SMTP)
- Basic SMTP setup (Gmail app password or similar)
- Notifications: new batch ready, content queued, errors
- Configurable recipient

## File Structure

```
zerona-content-engine/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
├── app/
│   ├── main.py
│   ├── config.py (pydantic-settings)
│   ├── database.py
│   ├── auth.py
│   ├── services/
│   │   ├── content_generator.py
│   │   ├── image_generator.py
│   │   ├── buffer_service.py
│   │   ├── email_service.py
│   │   └── scheduler.py
│   ├── routes/
│   │   ├── dashboard.py
│   │   ├── api.py
│   │   └── auth_routes.py
│   ├── templates/
│   │   ├── base.html, login.html, dashboard.html
│   │   ├── review.html, calendar.html, blog_review.html
│   │   ├── settings.html, logs.html
│   │   └── partials/ (content_card, stats_bar, calendar_day)
│   └── static/ (css/style.css, js/htmx.min.js)
├── media/images/
├── prompts/ (social_media.txt, blog_post.txt)
├── config/ (blog_topics.json)
└── data/ (content.db)
```

## Deployment

- Docker container on DigitalOcean droplet ($6/month)
- Volumes: data/, media/, prompts/, config/
- All times in America/Chicago timezone
- Optional: domain + Caddy/nginx reverse proxy with SSL

## Graceful Degradation

- External API failures: log error, send notification, retry on next scheduled run
- Never crash the app on API errors
- Buffer capacity checks before scheduling

## Build Priority

1. Project scaffolding (files, Docker, FastAPI, SQLite, config)
2. Claude API integration (content generation service)
3. Image generation (Replicate/Flux)
4. Dashboard UI (login, review queue, approve/reject/edit)
5. Scheduler (APScheduler jobs)
6. Buffer integration (queue with images)
7. Calendar view
8. Blog generation
9. Settings page (prompt editor, topic manager)
10. Email notifications
11. Logging and monitoring page

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# Project: Zerona Content Engine
FastAPI / Jinja2 / Tailwind CSS / HTMX — AI-powered content management for White House Chiropractic

---

# Memories #

- **Client:** White House Chiropractic in White House, TN — promoting Zerona VZ8 cold laser body contouring treatment.
- All AI content generation uses the Anthropic SDK (Claude Haiku/Sonnet). Replicate Flux Schnell for image generation.
- Data is stored in SQLite (`data/content.db`) with WAL mode. Migrations tracked in `migrations/` directory.
- Login is password-based via `ADMIN_PASSWORD` in `.env`. Session tokens are HMAC-signed with 24h expiry.
- Never commit `.env` — it contains `ANTHROPIC_API_KEY`, `REPLICATE_API_TOKEN`, `ADMIN_PASSWORD`, and integration credentials.
- After any app changes, always deploy to the droplet and rebuild the Docker image.

---

# Decisions #

- **FastAPI + Jinja2 + HTMX** — server-rendered HTML with HTMX for interactivity, no SPA framework.
- **Tailwind CSS via CDN** — loaded from `cdn.tailwindcss.com` in `base.html`. CSP must allow this origin.
- **SQLite** — single file database, WAL mode for concurrent reads. Simple and sufficient for this use case.
- **Single Docker container** — no multi-service compose. App runs Uvicorn on port 8000, mapped to 8080 on host.
- **No test framework** — no tests exist in this project currently.
- **Self-signed SSL** — production uses a self-signed certificate on nginx. Clients must accept `-k` / `--insecure`.

---

# Preferences #

- All routes require authentication via `_auth_check(request)` helper (except webhooks and public referral links)
- Content status workflow: `pending` → `approved` / `rejected` → `queued` → `posted`
- Content types: `social_fb`, `social_ig`, `blog`, `ad_fb`, `ad_google`, `email_sequence`
- Use HTMX (`hx-post`, `hx-target`, `hx-swap`) for interactive UI updates
- Templates use Jinja2 `{% include %}` for reusable partials (e.g., `partials/content_card.html`)
- Database migrations are idempotent — `init_db()` adds columns via ALTER TABLE, numbered migrations in `migrations/`

---

# Architecture #

## Directory layout
```
app/
  main.py              ← FastAPI app, middleware (security headers, CSRF, gzip)
  auth.py              ← Session token creation/validation, password verification
  config.py            ← Pydantic settings from .env
  database.py          ← Content DB schema + queries
  campaign_db.py       ← Email campaign tables
  ghl_db.py            ← GoHighLevel/referral tables
  routes/
    api.py             ← Content CRUD, generation, favorites, repurpose, tone, send
    dashboard.py       ← UI pages (overview, review, calendar, library, settings, logs)
    auth_routes.py     ← Login/logout with rate limiting
    campaign_api.py    ← Email campaign API + CSV upload
    campaigns.py       ← Campaign UI pages
    referral_api.py    ← Referral management API
    referral_public.py ← Public referral redirect + tracking
    referrals.py       ← Referral UI pages
    marketing_assets.py ← Asset catalog management
    webhooks.py        ← External webhook handlers
    ghl_webhooks.py    ← GoHighLevel webhook handlers
  services/
    content_generator.py ← AI content generation orchestration
    image_generator.py   ← Replicate image generation
    buffer_service.py    ← Buffer social media posting
    wordpress_service.py ← WordPress blog publishing
    campaign_service.py  ← Email campaign execution
    email_service.py     ← Transactional email
    mailgun_service.py   ← Mailgun API integration
    asset_downloader.py  ← Marketing asset download + catalog
    scheduler.py         ← APScheduler for recurring tasks
  templates/           ← Jinja2 HTML templates
    base.html          ← Base layout with Tailwind CDN + HTMX
    partials/          ← Reusable template fragments
  static/              ← CSS overrides + HTMX JS
data/                  ← SQLite database + generated content
media/                 ← Generated images + marketing assets
prompts/               ← AI system prompts (social_media.txt, etc.)
config/                ← Blog topics and other config JSON
migrations/            ← Numbered SQL migration files
```

## Data flow
```
Browser → FastAPI Route → Jinja2 Template → HTML Response
HTMX Request → API Route → Database → HTML Fragment Response
                  ↓
          Anthropic SDK (content generation)
          Replicate API (image generation)
          Buffer API (social posting)
          WordPress API (blog publishing)
          Mailgun API (email campaigns)
```

## Key constraints
- `database.py` owns the content DB schema — all migrations must be idempotent
- Security middleware in `main.py` adds headers to every response (CSP, X-Frame-Options, etc.)
- CSRF protection via Origin/Referer check — webhook endpoints are exempt
- Rate limiting on login (5 attempts per 15 min per IP)
- Session tokens are revoked server-side on logout

---

# Workflows #

## Adding a new route
1. Add route function in the appropriate `app/routes/*.py` file
2. Ensure `_auth_check(request)` is called at the top (unless public)
3. For UI pages: create template in `app/templates/`, extend `base.html`
4. For API endpoints: return `HTMLResponse` fragments for HTMX consumption
5. Deploy: SCP changed files, rebuild Docker image

## Common commands
- `docker compose up -d --build` — build and run locally
- `docker compose logs -f app`   — view app logs
- `docker compose restart app`   — restart without rebuild (won't pick up code changes)

## Deployment
1. SCP changed files to the droplet:
   ```bash
   scp <files> root@159.89.91.177:/root/zerona-content-engine/<path>
   ```
2. Rebuild and restart on server:
   ```bash
   ssh root@159.89.91.177 "cd /root/zerona-content-engine && docker compose up -d --build"
   ```
3. Verify: `curl -sk https://159.89.91.177/health`

**IMPORTANT:** The `data/` directory on the server contains the production SQLite database. Never overwrite it with local data.

---

# Deployment Details #

- **DigitalOcean droplet:** 159.89.91.177 (SSH: `ssh root@159.89.91.177`)
- **App code on server:** `/root/zerona-content-engine`
- **Stack:** Docker container (FastAPI + Uvicorn on :8000, mapped to :8080), nginx on host with self-signed SSL
- **Access:** https://159.89.91.177 (self-signed cert, no nginx basic auth)
- **Health check:** `curl -sk https://159.89.91.177/health`
- **No git on server** — deploy via SCP then `docker compose up -d --build`

---

# Constraints #

- Never commit `.env` — contains API keys and admin password
- Never overwrite `data/content.db` on the server — it contains production content
- Never skip `_auth_check()` on non-public routes
- Never add new pip dependencies without discussing first
- Never hardcode API keys — always read from `app.config.settings`
- CSP must include `https://cdn.tailwindcss.com` in `script-src` (Tailwind loaded via CDN)

## Billing & Authentication Policy
**Effective May 11, 2026** — All Claude Code usage runs through Philip Smith's Claude Max subscription. Never authenticate via `ANTHROPIC_API_KEY` or Console API credits. If `/status` shows API credit billing, stop and run `claude logout` → `claude login` → choose the claude.ai option.

# Zerona Content Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully automated content generation and scheduling system for White House Chiropractic's Zerona Z6 service with AI content/image generation, Buffer scheduling, and an HTMX approval dashboard.

**Architecture:** FastAPI backend with SQLite database, APScheduler for cron jobs, Claude API for content generation, Replicate Flux for images, Buffer API for social scheduling. Server-rendered HTMX dashboard with Tailwind CSS.

**Tech Stack:** Python 3.12+, FastAPI, SQLite, APScheduler, Anthropic SDK, Replicate SDK, HTMX, Tailwind CSS (CDN), Jinja2, Docker

---

### Task 1: Project Scaffolding & Configuration

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.gitignore`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2==3.1.4
python-multipart==0.0.9
pydantic-settings==2.5.2
anthropic==0.34.2
replicate==0.36.1
httpx==0.27.2
apscheduler==3.10.4
bcrypt==4.2.0
python-jose[cryptography]==3.3.0
aiofiles==24.1.0
aiosqlite==0.20.0
```

- [ ] **Step 2: Create .env.example**

```
ADMIN_PASSWORD=changeme
APP_PORT=8000
APP_HOST=0.0.0.0
BASE_URL=http://localhost:8000

ANTHROPIC_API_KEY=sk-ant-...
REPLICATE_API_TOKEN=r8_...

BUFFER_ACCESS_TOKEN=
BUFFER_FB_PROFILE_ID=
BUFFER_IG_PROFILE_ID=

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
NOTIFICATION_EMAIL=

POSTS_PER_WEEK_FB=4
POSTS_PER_WEEK_IG=5
BLOGS_PER_MONTH=2
GENERATION_DAY=sunday
GENERATION_HOUR=6
```

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings


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


settings = Settings()
```

- [ ] **Step 4: Create app/__init__.py**

Empty file.

- [ ] **Step 5: Create app/main.py (minimal)**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/media/images /app/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Create docker-compose.yml**

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./media:/app/media
      - ./prompts:/app/prompts
      - ./config:/app/config
    env_file:
      - .env
    restart: unless-stopped
```

- [ ] **Step 8: Create .gitignore**

```
__pycache__/
*.pyc
.env
data/
media/images/
.venv/
*.egg-info/
```

- [ ] **Step 9: Create directory structure and verify**

```bash
mkdir -p app/services app/routes app/templates/partials app/static/css app/static/js media/images prompts config data
touch app/services/__init__.py app/routes/__init__.py
python -c "from app.config import settings; print(settings.app_port)"
```

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "feat: project scaffolding with FastAPI, config, Docker"
```

---

### Task 2: Database Setup

**Files:**
- Create: `app/database.py`

- [ ] **Step 1: Create app/database.py**

```python
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/content.db")


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
    conn.close()


def log_event(event_type: str, message: str, details: dict | None = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO system_log (event_type, message, details) VALUES (?, ?, ?)",
        (event_type, message, json.dumps(details) if details else None),
    )
    conn.commit()
    conn.close()


def get_content_pieces(status: str | None = None, content_type: str | None = None,
                       category: str | None = None, scheduled_date: str | None = None,
                       limit: int = 100) -> list[dict]:
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
    query += " ORDER BY scheduled_date ASC, scheduled_time ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_content_status(content_id: int, status: str, **kwargs):
    conn = get_db()
    sets = ["status = ?", "updated_at = ?"]
    params = [status, datetime.now().isoformat()]
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(val)
    params.append(content_id)
    conn.execute(f"UPDATE content_pieces SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def insert_content_piece(data: dict) -> int:
    conn = get_db()
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    cursor = conn.execute(
        f"INSERT INTO content_pieces ({cols}) VALUES ({placeholders})",
        list(data.values()),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_stats() -> dict:
    conn = get_db()
    stats = {}
    for status in ["pending", "approved", "queued", "posted"]:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM content_pieces WHERE status = ?", (status,)
        ).fetchone()
        stats[status] = row["cnt"]
    conn.close()
    return stats


def get_logs(event_type: str | None = None, limit: int = 100) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM system_log WHERE 1=1"
    params = []
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] **Step 2: Wire up database init in main.py**

Add to `app/main.py`:

```python
from app.database import init_db

@app.on_event("startup")
def startup():
    init_db()
```

- [ ] **Step 3: Test database creation**

```bash
python -c "from app.database import init_db, get_stats; init_db(); print(get_stats())"
```

Expected: `{'pending': 0, 'approved': 0, 'queued': 0, 'posted': 0}`

- [ ] **Step 4: Commit**

```bash
git add app/database.py app/main.py && git commit -m "feat: SQLite database with schema and query helpers"
```

---

### Task 3: Auth System

**Files:**
- Create: `app/auth.py`
- Create: `app/routes/auth_routes.py`
- Create: `app/templates/login.html`

- [ ] **Step 1: Create app/auth.py**

```python
import bcrypt
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from app.config import settings

_sessions: dict[str, bool] = {}


def verify_password(plain: str) -> bool:
    return plain == settings.admin_password


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = True
    return token


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("session")
    return token is not None and _sessions.get(token, False)


def require_auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})
```

- [ ] **Step 2: Create app/routes/auth_routes.py**

```python
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.auth import verify_password, create_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if verify_password(password):
        token = create_session()
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie("session", token, httponly=True, samesite="lax")
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"})


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
```

- [ ] **Step 3: Create app/templates/login.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zerona Content Engine - Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: { extend: { colors: { navy: '#1B2A4A', teal: '#0EA5A0' } } }
        }
    </script>
</head>
<body class="bg-navy min-h-screen flex items-center justify-center">
    <div class="bg-white rounded-lg shadow-xl p-8 w-full max-w-sm">
        <h1 class="text-2xl font-bold text-navy mb-6 text-center">Zerona Content Engine</h1>
        {% if error %}
        <div class="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{{ error }}</div>
        {% endif %}
        <form method="POST" action="/login">
            <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input type="password" name="password" required
                   class="w-full border border-gray-300 rounded px-3 py-2 mb-4 focus:outline-none focus:ring-2 focus:ring-teal">
            <button type="submit"
                    class="w-full bg-teal text-white font-semibold py-2 rounded hover:bg-teal/90 transition">
                Sign In
            </button>
        </form>
    </div>
</body>
</html>
```

- [ ] **Step 4: Register auth routes in main.py**

Update `app/main.py` to include:

```python
from app.routes.auth_routes import router as auth_router
app.include_router(auth_router)
```

- [ ] **Step 5: Commit**

```bash
git add app/auth.py app/routes/auth_routes.py app/templates/login.html app/main.py
git commit -m "feat: admin auth with login page"
```

---

### Task 4: Prompt Templates & Blog Topics

**Files:**
- Create: `prompts/social_media.txt`
- Create: `prompts/blog_post.txt`
- Create: `config/blog_topics.json`

- [ ] **Step 1: Create prompts/social_media.txt**

Full social media prompt from the spec (the large prompt with brand voice, key facts, content pillars, compliance rules, and JSON output format).

- [ ] **Step 2: Create prompts/blog_post.txt**

Full blog post prompt from the spec.

- [ ] **Step 3: Create config/blog_topics.json**

The 24-topic JSON array from the spec.

- [ ] **Step 4: Commit**

```bash
git add prompts/ config/ && git commit -m "feat: prompt templates and blog topic queue"
```

---

### Task 5: Content Generation Service (Claude API)

**Files:**
- Create: `app/services/content_generator.py`

- [ ] **Step 1: Create app/services/content_generator.py**

```python
import json
import re
from datetime import date, timedelta
from pathlib import Path

import anthropic

from app.config import settings
from app.database import get_db, insert_content_piece, log_event, get_content_pieces


def _load_prompt(name: str) -> str:
    path = Path(f"prompts/{name}")
    return path.read_text()


def _parse_json_response(text: str) -> list | dict:
    cleaned = re.sub(r"```json\s*", "", text)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def _get_recent_captions(days: int = 14) -> str:
    pieces = get_content_pieces(limit=50)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    recent = [p for p in pieces if p.get("scheduled_date", "") >= cutoff]
    if not recent:
        return "No recent posts."
    lines = []
    for p in recent[:20]:
        body = p.get("edited_body") or p.get("body", "")
        lines.append(f"- [{p['content_type']}] {body[:150]}")
    return "\n".join(lines)


def _get_week_schedule(start_date: date) -> list[dict]:
    """Build the posting schedule for a week starting from start_date (Monday)."""
    fb_days = [0, 2, 4, 5]  # Mon, Wed, Fri, Sat
    ig_days = [0, 1, 2, 4, 5]  # Mon, Tue, Wed, Fri, Sat
    fb_times = ["10:00", "12:00", "15:00", "11:00"]
    ig_times = ["11:00", "13:00", "17:00", "12:00", "10:00"]

    schedule = []
    for i, day_offset in enumerate(fb_days):
        schedule.append({
            "platform": "facebook",
            "date": (start_date + timedelta(days=day_offset)).isoformat(),
            "time": fb_times[i],
        })
    for i, day_offset in enumerate(ig_days):
        schedule.append({
            "platform": "instagram",
            "date": (start_date + timedelta(days=day_offset)).isoformat(),
            "time": ig_times[i],
        })
    return schedule


def generate_weekly_social(target_week_start: date | None = None) -> list[int]:
    """Generate a week of social media posts. Returns list of content_piece IDs."""
    if target_week_start is None:
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        target_week_start = today + timedelta(days=days_until_monday)

    prompt_template = _load_prompt("social_media.txt")
    recent = _get_recent_captions()
    schedule = _get_week_schedule(target_week_start)

    batch_id = f"social_{target_week_start.isoformat()}"

    user_message = f"""Generate social media content for the week of {target_week_start.isoformat()}.

Posting schedule this week:
{json.dumps(schedule, indent=2)}

Recent posts (avoid repeating similar content):
{recent}

Generate exactly {len(schedule)} posts — one for each slot in the schedule. Return a JSON array."""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[{"role": "user", "content": user_message}],
        )
        posts = _parse_json_response(response.content[0].text)
    except json.JSONDecodeError:
        # Retry with explicit JSON instruction
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "I'll provide the content as a raw JSON array:"},
            ],
        )
        posts = _parse_json_response(response.content[0].text)

    ids = []
    for i, post in enumerate(posts):
        slot = schedule[i] if i < len(schedule) else schedule[-1]
        content_type = f"social_{slot['platform'][:2]}"
        row_id = insert_content_piece({
            "content_type": content_type,
            "category": post.get("category", "education"),
            "title": post.get("title", ""),
            "body": post.get("caption", ""),
            "hashtags": post.get("hashtags", ""),
            "image_prompt": post.get("image_prompt", ""),
            "scheduled_date": slot["date"],
            "scheduled_time": slot["time"],
            "status": "pending",
            "generation_batch": batch_id,
        })
        ids.append(row_id)

    log_event("generation", f"Generated {len(ids)} social posts for week of {target_week_start}", {"batch": batch_id, "count": len(ids)})
    return ids


def generate_blog_post() -> int | None:
    """Generate the next blog post from the topic queue. Returns content_piece ID."""
    topics_path = Path("config/blog_topics.json")
    topics = json.loads(topics_path.read_text())

    next_topic = None
    topic_index = -1
    for i, t in enumerate(topics):
        if not t.get("used", False):
            next_topic = t
            topic_index = i
            break

    if next_topic is None:
        log_event("error", "No unused blog topics remaining")
        return None

    prompt_template = _load_prompt("blog_post.txt")

    user_message = f"""Write a blog post about: {next_topic['topic']}
Target keyword: {next_topic['keyword']}"""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[{"role": "user", "content": user_message}],
        )
        blog = _parse_json_response(response.content[0].text)
    except json.JSONDecodeError:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=prompt_template,
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "Here is the blog post as raw JSON:"},
            ],
        )
        blog = _parse_json_response(response.content[0].text)

    row_id = insert_content_piece({
        "content_type": "blog",
        "category": "education",
        "title": blog.get("title", next_topic["topic"]),
        "body": blog.get("body_html", ""),
        "hashtags": blog.get("target_keyword", ""),
        "image_prompt": blog.get("image_prompt", ""),
        "scheduled_date": date.today().isoformat(),
        "status": "pending",
        "generation_batch": f"blog_{date.today().isoformat()}",
    })

    # Mark topic as used
    topics[topic_index]["used"] = True
    topics_path.write_text(json.dumps(topics, indent=2))

    log_event("generation", f"Generated blog post: {blog.get('title', '')}", {"topic": next_topic["topic"]})
    return row_id
```

- [ ] **Step 2: Commit**

```bash
git add app/services/content_generator.py && git commit -m "feat: Claude API content generation for social and blog"
```

---

### Task 6: Image Generation Service (Replicate/Flux)

**Files:**
- Create: `app/services/image_generator.py`

- [ ] **Step 1: Create app/services/image_generator.py**

```python
import httpx
import replicate
from pathlib import Path
from datetime import date

from app.config import settings
from app.database import update_content_status, log_event


SIZES = {
    "social_ig": {"width": 1024, "height": 1024},
    "social_fb": {"width": 1200, "height": 630},
    "blog": {"width": 1200, "height": 628},
}


def generate_image(content_id: int, content_type: str, image_prompt: str) -> str | None:
    """Generate an image via Replicate Flux Schnell. Returns local file path or None."""
    size = SIZES.get(content_type, SIZES["social_ig"])
    images_dir = Path("media/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date.today().isoformat()}_{content_id}.png"
    local_path = images_dir / filename

    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": image_prompt,
                "width": size["width"],
                "height": size["height"],
                "num_outputs": 1,
            },
        )

        image_url = output[0] if isinstance(output, list) else str(output)

        # Download image locally
        with httpx.Client(timeout=60) as client:
            resp = client.get(image_url)
            resp.raise_for_status()
            local_path.write_bytes(resp.content)

        update_content_status(
            content_id,
            status="pending",
            image_url=f"/media/images/{filename}",
            image_local_path=str(local_path),
        )

        log_event("generation", f"Image generated for content {content_id}", {"filename": filename})
        return str(local_path)

    except Exception as e:
        log_event("error", f"Image generation failed for content {content_id}", {"error": str(e)})
        update_content_status(content_id, status="pending", image_url="/static/css/placeholder.png")
        return None


def generate_images_for_batch(content_ids: list[int], pieces: list[dict]):
    """Generate images for a batch of content pieces."""
    for piece in pieces:
        if piece["id"] in content_ids and piece.get("image_prompt"):
            generate_image(piece["id"], piece["content_type"], piece["image_prompt"])
```

- [ ] **Step 2: Commit**

```bash
git add app/services/image_generator.py && git commit -m "feat: Replicate Flux image generation service"
```

---

### Task 7: Base Template & Dashboard Layout

**Files:**
- Create: `app/templates/base.html`
- Create: `app/static/css/style.css`

- [ ] **Step 1: Download HTMX**

```bash
curl -o app/static/js/htmx.min.js https://unpkg.com/htmx.org@2.0.2/dist/htmx.min.js
```

- [ ] **Step 2: Create app/templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Zerona Content Engine{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: { extend: { colors: { navy: '#1B2A4A', teal: '#0EA5A0' } } }
        }
    </script>
    <script src="/static/js/htmx.min.js"></script>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="flex min-h-screen">
        <!-- Sidebar -->
        <aside class="w-64 bg-navy text-white flex-shrink-0 hidden md:block">
            <div class="p-6">
                <h1 class="text-lg font-bold">Zerona Engine</h1>
                <p class="text-gray-400 text-xs mt-1">Content Management</p>
            </div>
            <nav class="mt-4">
                <a href="/dashboard" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'dashboard' %}bg-white/10 border-r-2 border-teal{% endif %}">Overview</a>
                <a href="/dashboard/review" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'review' %}bg-white/10 border-r-2 border-teal{% endif %}">Review Queue</a>
                <a href="/dashboard/calendar" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'calendar' %}bg-white/10 border-r-2 border-teal{% endif %}">Calendar</a>
                <a href="/dashboard/blog" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'blog' %}bg-white/10 border-r-2 border-teal{% endif %}">Blog Posts</a>
                <a href="/dashboard/settings" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'settings' %}bg-white/10 border-r-2 border-teal{% endif %}">Settings</a>
                <a href="/dashboard/logs" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'logs' %}bg-white/10 border-r-2 border-teal{% endif %}">Logs</a>
            </nav>
            <div class="absolute bottom-0 w-64 p-4 border-t border-white/10">
                <a href="/logout" class="text-sm text-gray-400 hover:text-white">Sign Out</a>
            </div>
        </aside>

        <!-- Mobile header -->
        <div class="md:hidden fixed top-0 left-0 right-0 bg-navy text-white p-4 z-50 flex justify-between items-center">
            <h1 class="text-lg font-bold">Zerona Engine</h1>
            <button onclick="document.getElementById('mobile-nav').classList.toggle('hidden')" class="text-white">Menu</button>
        </div>
        <div id="mobile-nav" class="hidden md:hidden fixed inset-0 bg-navy z-40 pt-16">
            <nav class="p-4">
                <a href="/dashboard" class="block py-3 text-white">Overview</a>
                <a href="/dashboard/review" class="block py-3 text-white">Review Queue</a>
                <a href="/dashboard/calendar" class="block py-3 text-white">Calendar</a>
                <a href="/dashboard/blog" class="block py-3 text-white">Blog Posts</a>
                <a href="/dashboard/settings" class="block py-3 text-white">Settings</a>
                <a href="/dashboard/logs" class="block py-3 text-white">Logs</a>
                <a href="/logout" class="block py-3 text-gray-400">Sign Out</a>
            </nav>
        </div>

        <!-- Main content -->
        <main class="flex-1 md:p-8 p-4 md:pt-8 pt-20">
            {% block content %}{% endblock %}
        </main>
    </div>
</body>
</html>
```

- [ ] **Step 3: Create app/static/css/style.css**

```css
/* Custom overrides */
.status-pending { background-color: #9CA3AF; }
.status-approved { background-color: #10B981; }
.status-queued { background-color: #3B82F6; }
.status-posted { background-color: #059669; }
.status-rejected { background-color: #EF4444; }
.status-failed { background-color: #F59E0B; }

.content-card { transition: all 0.2s ease; }
.content-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline-block; }
```

- [ ] **Step 4: Commit**

```bash
git add app/templates/base.html app/static/ && git commit -m "feat: base template with sidebar nav, HTMX, Tailwind"
```

---

### Task 8: Dashboard Overview Page

**Files:**
- Create: `app/routes/dashboard.py`
- Create: `app/templates/dashboard.html`
- Create: `app/templates/partials/stats_bar.html`

- [ ] **Step 1: Create app/routes/dashboard.py**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date, timedelta

from app.auth import is_authenticated
from app.database import get_stats, get_content_pieces, get_logs

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _get_week_dates():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


@router.get("", response_class=HTMLResponse)
async def overview(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    stats = get_stats()
    week_dates = _get_week_dates()
    week_posts = {}
    for d in week_dates:
        week_posts[d.isoformat()] = get_content_pieces(scheduled_date=d.isoformat())
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "active": "dashboard",
        "stats": stats, "week_dates": week_dates, "week_posts": week_posts,
    })


@router.get("/review", response_class=HTMLResponse)
async def review(request: Request, status: str = "pending", platform: str = "", category: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    content_type = None
    if platform == "facebook":
        content_type = "social_fb"
    elif platform == "instagram":
        content_type = "social_ig"
    pieces = get_content_pieces(status=status or None, content_type=content_type,
                                 category=category or None, limit=200)
    # Exclude blogs from social review
    pieces = [p for p in pieces if p["content_type"] != "blog"]
    return templates.TemplateResponse("review.html", {
        "request": request, "active": "review",
        "pieces": pieces, "current_status": status,
        "current_platform": platform, "current_category": category,
    })


@router.get("/calendar", response_class=HTMLResponse)
async def calendar(request: Request, month: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    if month:
        year, m = month.split("-")
        first_day = date(int(year), int(m), 1)
    else:
        today = date.today()
        first_day = date(today.year, today.month, 1)

    # Build calendar grid
    if first_day.month == 12:
        next_month = date(first_day.year + 1, 1, 1)
    else:
        next_month = date(first_day.year, first_day.month + 1, 1)
    last_day = next_month - timedelta(days=1)

    # Get all content for this month
    all_pieces = get_content_pieces(limit=500)
    month_pieces = {}
    for p in all_pieces:
        sd = p.get("scheduled_date", "")
        if sd and sd[:7] == first_day.isoformat()[:7]:
            month_pieces.setdefault(sd, []).append(p)

    prev_month = (first_day - timedelta(days=1)).replace(day=1)

    return templates.TemplateResponse("calendar.html", {
        "request": request, "active": "calendar",
        "first_day": first_day, "last_day": last_day,
        "month_pieces": month_pieces,
        "prev_month": prev_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
    })


@router.get("/blog", response_class=HTMLResponse)
async def blog_review(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    blogs = get_content_pieces(content_type="blog", limit=50)
    return templates.TemplateResponse("blog_review.html", {
        "request": request, "active": "blog", "blogs": blogs,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    from pathlib import Path
    import json
    social_prompt = Path("prompts/social_media.txt").read_text() if Path("prompts/social_media.txt").exists() else ""
    blog_prompt = Path("prompts/blog_post.txt").read_text() if Path("prompts/blog_post.txt").exists() else ""
    topics = json.loads(Path("config/blog_topics.json").read_text()) if Path("config/blog_topics.json").exists() else []
    return templates.TemplateResponse("settings.html", {
        "request": request, "active": "settings",
        "social_prompt": social_prompt, "blog_prompt": blog_prompt, "topics": topics,
    })


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, event_type: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    logs = get_logs(event_type=event_type or None)
    return templates.TemplateResponse("logs.html", {
        "request": request, "active": "logs",
        "logs": logs, "current_type": event_type,
    })
```

- [ ] **Step 2: Create app/templates/dashboard.html**

```html
{% extends "base.html" %}
{% block title %}Dashboard - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <h2 class="text-2xl font-bold text-navy mb-4">Overview</h2>

    <!-- Stats Bar -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-gray-400">
            <p class="text-sm text-gray-500">Pending Review</p>
            <p class="text-3xl font-bold text-navy">{{ stats.pending }}</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-green-500">
            <p class="text-sm text-gray-500">Approved</p>
            <p class="text-3xl font-bold text-navy">{{ stats.approved }}</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-blue-500">
            <p class="text-sm text-gray-500">Queued</p>
            <p class="text-3xl font-bold text-navy">{{ stats.queued }}</p>
        </div>
        <div class="bg-white rounded-lg p-4 shadow-sm border-l-4 border-emerald-600">
            <p class="text-sm text-gray-500">Posted</p>
            <p class="text-3xl font-bold text-navy">{{ stats.posted }}</p>
        </div>
    </div>

    <!-- Manual Generate Button -->
    <div class="mb-8">
        <button hx-post="/api/generate/social" hx-swap="outerHTML"
                class="bg-teal text-white px-6 py-2 rounded font-semibold hover:bg-teal/90 transition">
            Generate This Week's Posts Now
        </button>
        <span class="htmx-indicator ml-2 text-gray-500">Generating...</span>
    </div>

    <!-- Week Calendar -->
    <h3 class="text-lg font-semibold text-navy mb-3">This Week</h3>
    <div class="grid grid-cols-7 gap-2">
        {% for d in week_dates %}
        <div class="bg-white rounded-lg p-3 shadow-sm min-h-[120px]">
            <p class="text-xs font-semibold text-gray-500 mb-2">
                {{ d.strftime('%a %m/%d') }}
            </p>
            {% for post in week_posts.get(d.isoformat(), []) %}
            <div class="text-xs mb-1 px-2 py-1 rounded
                {% if post.status == 'pending' %}bg-gray-100 text-gray-600
                {% elif post.status == 'approved' %}bg-green-100 text-green-700
                {% elif post.status == 'queued' %}bg-blue-100 text-blue-700
                {% elif post.status == 'posted' %}bg-emerald-100 text-emerald-700
                {% elif post.status == 'rejected' %}bg-red-100 text-red-600
                {% endif %}">
                {{ post.content_type|replace('social_', '')|upper }}
                {% if post.title %}- {{ post.title[:20] }}{% endif %}
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Register dashboard routes in main.py**

Add to `app/main.py`:

```python
from app.routes.dashboard import router as dashboard_router
app.include_router(dashboard_router)
```

- [ ] **Step 4: Commit**

```bash
git add app/routes/dashboard.py app/templates/dashboard.html app/main.py
git commit -m "feat: dashboard overview with stats and week calendar"
```

---

### Task 9: Review Queue Page & API Endpoints

**Files:**
- Create: `app/templates/review.html`
- Create: `app/templates/partials/content_card.html`
- Create: `app/routes/api.py`

- [ ] **Step 1: Create app/templates/partials/content_card.html**

```html
<div class="content-card bg-white rounded-lg shadow-sm p-4 border" id="card-{{ piece.id }}">
    <div class="flex gap-4">
        <!-- Image -->
        <div class="w-32 h-32 flex-shrink-0 rounded overflow-hidden bg-gray-100">
            {% if piece.image_url %}
            <img src="{{ piece.image_url }}" alt="" class="w-full h-full object-cover">
            {% else %}
            <div class="w-full h-full flex items-center justify-center text-gray-400 text-xs">No image</div>
            {% endif %}
        </div>

        <!-- Content -->
        <div class="flex-1 min-w-0">
            <div class="flex gap-2 mb-2">
                <span class="text-xs font-semibold px-2 py-0.5 rounded
                    {% if 'fb' in piece.content_type %}bg-blue-100 text-blue-700{% else %}bg-pink-100 text-pink-700{% endif %}">
                    {{ piece.content_type|replace('social_', '')|upper }}
                </span>
                <span class="text-xs font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                    {{ piece.category }}
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
    <div class="flex gap-2 mt-3 pt-3 border-t">
        <button hx-post="/api/content/{{ piece.id }}/approve" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
                class="px-4 py-1.5 bg-green-500 text-white text-sm rounded hover:bg-green-600 transition">
            Approve
        </button>
        <button onclick="document.getElementById('edit-{{ piece.id }}').classList.toggle('hidden')"
                class="px-4 py-1.5 bg-yellow-500 text-white text-sm rounded hover:bg-yellow-600 transition">
            Edit
        </button>
        <button hx-post="/api/content/{{ piece.id }}/reject" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
                class="px-4 py-1.5 bg-red-500 text-white text-sm rounded hover:bg-red-600 transition">
            Reject
        </button>
        {% if not piece.image_url or piece.image_url == '/static/css/placeholder.png' %}
        <button hx-post="/api/content/{{ piece.id }}/regenerate-image" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML"
                class="px-4 py-1.5 bg-gray-500 text-white text-sm rounded hover:bg-gray-600 transition">
            Regenerate Image
        </button>
        {% endif %}
    </div>

    <!-- Edit Form (hidden) -->
    <div id="edit-{{ piece.id }}" class="hidden mt-3 pt-3 border-t">
        <form hx-post="/api/content/{{ piece.id }}/edit" hx-target="#card-{{ piece.id }}" hx-swap="outerHTML">
            <textarea name="body" rows="4" class="w-full border rounded p-2 text-sm mb-2">{{ piece.edited_body or piece.body }}</textarea>
            <button type="submit" class="px-4 py-1.5 bg-teal text-white text-sm rounded hover:bg-teal/90 transition">
                Save & Approve
            </button>
        </form>
    </div>
</div>
```

- [ ] **Step 2: Create app/templates/review.html**

```html
{% extends "base.html" %}
{% block title %}Review Queue - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Review Queue</h2>
        <button hx-post="/api/content/approve-all" hx-target="#review-list" hx-swap="innerHTML"
                class="bg-green-500 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-green-600 transition">
            Approve All Pending
        </button>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-6 flex-wrap">
        <select onchange="window.location.href='/dashboard/review?status='+this.value+'&platform={{ current_platform }}&category={{ current_category }}'"
                class="border rounded px-3 py-1.5 text-sm">
            <option value="pending" {% if current_status == 'pending' %}selected{% endif %}>Pending</option>
            <option value="approved" {% if current_status == 'approved' %}selected{% endif %}>Approved</option>
            <option value="rejected" {% if current_status == 'rejected' %}selected{% endif %}>Rejected</option>
            <option value="queued" {% if current_status == 'queued' %}selected{% endif %}>Queued</option>
            <option value="" {% if not current_status %}selected{% endif %}>All</option>
        </select>
        <select onchange="window.location.href='/dashboard/review?status={{ current_status }}&platform='+this.value+'&category={{ current_category }}'"
                class="border rounded px-3 py-1.5 text-sm">
            <option value="" {% if not current_platform %}selected{% endif %}>All Platforms</option>
            <option value="facebook" {% if current_platform == 'facebook' %}selected{% endif %}>Facebook</option>
            <option value="instagram" {% if current_platform == 'instagram' %}selected{% endif %}>Instagram</option>
        </select>
        <select onchange="window.location.href='/dashboard/review?status={{ current_status }}&platform={{ current_platform }}&category='+this.value"
                class="border rounded px-3 py-1.5 text-sm">
            <option value="" {% if not current_category %}selected{% endif %}>All Categories</option>
            <option value="education" {% if current_category == 'education' %}selected{% endif %}>Education</option>
            <option value="social_proof" {% if current_category == 'social_proof' %}selected{% endif %}>Social Proof</option>
            <option value="behind_scenes" {% if current_category == 'behind_scenes' %}selected{% endif %}>Behind the Scenes</option>
            <option value="patient_stories" {% if current_category == 'patient_stories' %}selected{% endif %}>Patient Stories</option>
            <option value="lifestyle" {% if current_category == 'lifestyle' %}selected{% endif %}>Lifestyle</option>
        </select>
    </div>

    <!-- Content Cards -->
    <div id="review-list" class="space-y-4">
        {% if pieces %}
            {% for piece in pieces %}
                {% include "partials/content_card.html" %}
            {% endfor %}
        {% else %}
            <div class="text-center py-12 text-gray-400">
                <p class="text-lg">No content to review</p>
                <p class="text-sm mt-1">Generate some posts from the Overview page</p>
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Create app/routes/api.py**

```python
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.database import (
    get_content_pieces, update_content_status, get_db, log_event,
)

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="app/templates")


def _auth_check(request: Request) -> bool:
    return is_authenticated(request)


def _render_card(request: Request, content_id: int) -> HTMLResponse:
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    piece = dict(row) if row else {}
    return templates.TemplateResponse("partials/content_card.html", {"request": request, "piece": piece})


@router.post("/content/{content_id}/approve", response_class=HTMLResponse)
async def approve(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    update_content_status(content_id, "approved")
    log_event("approval", f"Content {content_id} approved")
    return _render_card(request, content_id)


@router.post("/content/{content_id}/reject", response_class=HTMLResponse)
async def reject(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    update_content_status(content_id, "rejected")
    log_event("approval", f"Content {content_id} rejected")
    return _render_card(request, content_id)


@router.post("/content/{content_id}/edit", response_class=HTMLResponse)
async def edit_and_approve(request: Request, content_id: int, body: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    update_content_status(content_id, "approved", edited_body=body)
    log_event("approval", f"Content {content_id} edited and approved")
    return _render_card(request, content_id)


@router.post("/content/approve-all", response_class=HTMLResponse)
async def approve_all(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    pieces = get_content_pieces(status="pending")
    for p in pieces:
        if p["content_type"] != "blog":
            update_content_status(p["id"], "approved")
    log_event("approval", f"Bulk approved {len(pieces)} posts")
    approved = get_content_pieces(status="approved", limit=200)
    approved = [p for p in approved if p["content_type"] != "blog"]
    html_parts = []
    for piece in approved:
        resp = templates.TemplateResponse("partials/content_card.html", {"request": request, "piece": piece})
        html_parts.append(resp.body.decode())
    return HTMLResponse("\n".join(html_parts))


@router.post("/content/{content_id}/regenerate-image", response_class=HTMLResponse)
async def regenerate_image(request: Request, content_id: int):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    conn = get_db()
    row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (content_id,)).fetchone()
    conn.close()
    if row and row["image_prompt"]:
        from app.services.image_generator import generate_image
        generate_image(content_id, row["content_type"], row["image_prompt"])
    return _render_card(request, content_id)


@router.post("/generate/social", response_class=HTMLResponse)
async def trigger_social_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_weekly_social
    from app.services.image_generator import generate_images_for_batch
    try:
        ids = generate_weekly_social()
        pieces = get_content_pieces(limit=200)
        batch_pieces = [p for p in pieces if p["id"] in ids]
        generate_images_for_batch(ids, batch_pieces)
        return HTMLResponse(
            f'<div class="bg-green-50 text-green-700 p-3 rounded">'
            f'Generated {len(ids)} posts! <a href="/dashboard/review" class="underline">Review them now</a></div>'
        )
    except Exception as e:
        log_event("error", f"Manual generation failed: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Error: {str(e)}</div>')


@router.post("/generate/blog", response_class=HTMLResponse)
async def trigger_blog_generation(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.content_generator import generate_blog_post
    from app.services.image_generator import generate_image
    from app.database import get_db
    try:
        row_id = generate_blog_post()
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_image(row_id, "blog", row["image_prompt"])
            return HTMLResponse(
                f'<div class="bg-green-50 text-green-700 p-3 rounded">'
                f'Blog post generated! <a href="/dashboard/blog" class="underline">Review it now</a></div>'
            )
        return HTMLResponse('<div class="bg-yellow-50 text-yellow-700 p-3 rounded">No unused blog topics remaining.</div>')
    except Exception as e:
        log_event("error", f"Blog generation failed: {str(e)}")
        return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Error: {str(e)}</div>')
```

- [ ] **Step 4: Register API routes in main.py**

Add to `app/main.py`:

```python
from app.routes.api import router as api_router
app.include_router(api_router)
```

- [ ] **Step 5: Commit**

```bash
git add app/routes/api.py app/templates/review.html app/templates/partials/content_card.html app/main.py
git commit -m "feat: review queue with approve/reject/edit and generation API"
```

---

### Task 10: Scheduler (APScheduler)

**Files:**
- Create: `app/services/scheduler.py`

- [ ] **Step 1: Create app/services/scheduler.py**

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import log_event


scheduler = BackgroundScheduler(timezone="America/Chicago")


def weekly_social_job():
    """Generate next week's social media posts."""
    try:
        from app.services.content_generator import generate_weekly_social
        from app.services.image_generator import generate_images_for_batch
        from app.database import get_content_pieces
        ids = generate_weekly_social()
        pieces = get_content_pieces(limit=200)
        batch_pieces = [p for p in pieces if p["id"] in ids]
        generate_images_for_batch(ids, batch_pieces)
        log_event("generation", f"Scheduled: generated {len(ids)} social posts")
        # Send notification
        try:
            from app.services.email_service import send_notification
            send_notification(
                f"Zerona: {len(ids)} New Posts Ready for Review",
                f"{len(ids)} new social media posts have been generated and are waiting for your review.\n\nVisit your dashboard to approve them.",
            )
        except Exception:
            pass
    except Exception as e:
        log_event("error", f"Scheduled social generation failed: {str(e)}")


def blog_generation_job():
    """Generate a blog post on the 1st and 15th."""
    try:
        from app.services.content_generator import generate_blog_post
        from app.services.image_generator import generate_image
        from app.database import get_db
        row_id = generate_blog_post()
        if row_id:
            conn = get_db()
            row = conn.execute("SELECT * FROM content_pieces WHERE id = ?", (row_id,)).fetchone()
            conn.close()
            if row and row["image_prompt"]:
                generate_image(row_id, "blog", row["image_prompt"])
            log_event("generation", f"Scheduled: generated blog post {row_id}")
    except Exception as e:
        log_event("error", f"Scheduled blog generation failed: {str(e)}")


def daily_buffer_queue_job():
    """Queue approved posts for today to Buffer."""
    try:
        from app.services.buffer_service import queue_todays_posts
        count = queue_todays_posts()
        if count > 0:
            log_event("queue", f"Scheduled: queued {count} posts to Buffer")
    except Exception as e:
        log_event("error", f"Scheduled Buffer queue failed: {str(e)}")


def init_scheduler():
    day_map = {
        "sunday": "sun", "monday": "mon", "tuesday": "tue",
        "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat",
    }
    gen_day = day_map.get(settings.generation_day.lower(), "sun")
    gen_hour = settings.generation_hour

    # Weekly social generation
    scheduler.add_job(
        weekly_social_job, CronTrigger(day_of_week=gen_day, hour=gen_hour, minute=0),
        id="weekly_social", replace_existing=True,
    )

    # Blog generation on 1st and 15th
    scheduler.add_job(
        blog_generation_job, CronTrigger(day="1,15", hour=gen_hour, minute=0),
        id="blog_generation", replace_existing=True,
    )

    # Daily Buffer queue at 7 AM
    scheduler.add_job(
        daily_buffer_queue_job, CronTrigger(hour=7, minute=0),
        id="daily_buffer", replace_existing=True,
    )

    scheduler.start()
    log_event("system", "Scheduler initialized", {
        "social_gen": f"{gen_day} at {gen_hour}:00",
        "blog_gen": f"1st & 15th at {gen_hour}:00",
        "buffer_queue": "daily at 7:00",
    })
```

- [ ] **Step 2: Wire scheduler into main.py startup**

Update the startup event in `app/main.py`:

```python
from app.services.scheduler import init_scheduler

@app.on_event("startup")
def startup():
    init_db()
    init_scheduler()
```

- [ ] **Step 3: Commit**

```bash
git add app/services/scheduler.py app/main.py
git commit -m "feat: APScheduler with weekly social, bi-weekly blog, daily Buffer jobs"
```

---

### Task 11: Buffer Integration

**Files:**
- Create: `app/services/buffer_service.py`

- [ ] **Step 1: Create app/services/buffer_service.py**

```python
import httpx
from datetime import date, datetime
from pathlib import Path

from app.config import settings
from app.database import get_content_pieces, update_content_status, log_event

BUFFER_API = "https://api.bufferapp.com/1"


def _headers():
    return {"Authorization": f"Bearer {settings.buffer_access_token}"}


def test_connection() -> dict:
    """Test Buffer API connection and return profiles."""
    if not settings.buffer_access_token:
        return {"connected": False, "error": "No Buffer access token configured"}
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{BUFFER_API}/profiles.json", params={"access_token": settings.buffer_access_token})
            resp.raise_for_status()
            profiles = resp.json()
            return {
                "connected": True,
                "profiles": [{"id": p["id"], "service": p["service"], "formatted_username": p.get("formatted_username", "")} for p in profiles],
            }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def _get_profile_id(content_type: str) -> str | None:
    if "fb" in content_type:
        return settings.buffer_fb_profile_id
    elif "ig" in content_type:
        return settings.buffer_ig_profile_id
    return None


def queue_post(piece: dict) -> str | None:
    """Queue a single approved post to Buffer. Returns buffer post ID or None."""
    profile_id = _get_profile_id(piece["content_type"])
    if not profile_id:
        log_event("error", f"No Buffer profile ID for {piece['content_type']}")
        return None

    text = piece.get("edited_body") or piece["body"]

    # Add hashtags for Instagram
    if "ig" in piece["content_type"] and piece.get("hashtags"):
        text += f"\n\n{piece['hashtags']}"

    data = {
        "access_token": settings.buffer_access_token,
        "profile_ids[]": profile_id,
        "text": text,
        "top": "false",
    }

    # Schedule time
    if piece.get("scheduled_date") and piece.get("scheduled_time"):
        scheduled_dt = f"{piece['scheduled_date']}T{piece['scheduled_time']}:00"
        data["scheduled_at"] = scheduled_dt

    # Attach image if available
    image_path = piece.get("image_local_path")
    if image_path and Path(image_path).exists():
        data["media[photo]"] = piece.get("image_url", "")

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{BUFFER_API}/updates/create.json", data=data)
            resp.raise_for_status()
            result = resp.json()
            buffer_id = result.get("updates", [{}])[0].get("id") if result.get("updates") else result.get("id")
            return buffer_id
    except Exception as e:
        log_event("error", f"Buffer queue failed for content {piece['id']}: {str(e)}")
        return None


def queue_todays_posts() -> int:
    """Queue all approved posts scheduled for today. Returns count of queued posts."""
    today = date.today().isoformat()
    pieces = get_content_pieces(status="approved", scheduled_date=today)
    count = 0
    for piece in pieces:
        buffer_id = queue_post(piece)
        if buffer_id:
            update_content_status(piece["id"], "queued", buffer_post_id=buffer_id)
            count += 1
        else:
            update_content_status(piece["id"], "failed")
    if count > 0:
        log_event("queue", f"Queued {count} posts to Buffer for {today}")
    return count
```

- [ ] **Step 2: Add Buffer test endpoint to API routes**

Add to `app/routes/api.py`:

```python
@router.get("/buffer/test", response_class=HTMLResponse)
async def test_buffer(request: Request):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from app.services.buffer_service import test_connection
    result = test_connection()
    if result["connected"]:
        profiles_html = "".join(
            f'<li class="text-sm">{p["service"]}: {p["formatted_username"]} (ID: {p["id"]})</li>'
            for p in result["profiles"]
        )
        return HTMLResponse(f'<div class="bg-green-50 text-green-700 p-3 rounded"><p class="font-semibold">Connected!</p><ul class="mt-2">{profiles_html}</ul></div>')
    return HTMLResponse(f'<div class="bg-red-50 text-red-600 p-3 rounded">Not connected: {result.get("error", "Unknown error")}</div>')
```

- [ ] **Step 3: Commit**

```bash
git add app/services/buffer_service.py app/routes/api.py
git commit -m "feat: Buffer API integration with queue and connection test"
```

---

### Task 12: Calendar Page

**Files:**
- Create: `app/templates/calendar.html`

- [ ] **Step 1: Create app/templates/calendar.html**

```html
{% extends "base.html" %}
{% block title %}Calendar - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Content Calendar</h2>
        <div class="flex gap-2">
            <a href="/dashboard/calendar?month={{ prev_month }}" class="px-3 py-1 border rounded text-sm hover:bg-gray-50">&larr; Prev</a>
            <span class="px-3 py-1 text-sm font-semibold">{{ first_day.strftime('%B %Y') }}</span>
            <a href="/dashboard/calendar?month={{ next_month }}" class="px-3 py-1 border rounded text-sm hover:bg-gray-50">Next &rarr;</a>
        </div>
    </div>

    <!-- Day headers -->
    <div class="grid grid-cols-7 gap-1 mb-1">
        {% for day_name in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] %}
        <div class="text-center text-xs font-semibold text-gray-500 py-2">{{ day_name }}</div>
        {% endfor %}
    </div>

    <!-- Calendar grid -->
    <div class="grid grid-cols-7 gap-1">
        {# Empty cells for days before the 1st #}
        {% for _ in range(first_day.weekday()) %}
        <div class="bg-gray-50 rounded min-h-[100px] p-2"></div>
        {% endfor %}

        {# Days of the month #}
        {% set ns = namespace(current_day=1) %}
        {% for day_num in range(1, (last_day.day + 1)) %}
        {% set day_str = '%04d-%02d-%02d' % (first_day.year, first_day.month, day_num) %}
        <div class="bg-white rounded min-h-[100px] p-2 border hover:border-teal/50 transition">
            <p class="text-xs font-semibold text-gray-400 mb-1">{{ day_num }}</p>
            {% for post in month_pieces.get(day_str, []) %}
            <div class="text-xs mb-0.5 px-1.5 py-0.5 rounded truncate
                {% if post.status == 'pending' %}bg-gray-100 text-gray-600
                {% elif post.status == 'approved' %}bg-green-100 text-green-700
                {% elif post.status == 'queued' %}bg-blue-100 text-blue-700
                {% elif post.status == 'posted' %}bg-emerald-100 text-emerald-700
                {% elif post.status == 'rejected' %}bg-red-100 text-red-600
                {% endif %}"
                title="{{ post.title or post.body[:50] }}">
                {{ post.content_type|replace('social_', '')|upper }}
                {{ post.title[:15] if post.title else '' }}
            </div>
            {% endfor %}
        </div>
        {% endfor %}

        {# Empty cells after the last day #}
        {% set remaining = 7 - ((first_day.weekday() + last_day.day) % 7) %}
        {% if remaining < 7 %}
        {% for _ in range(remaining) %}
        <div class="bg-gray-50 rounded min-h-[100px] p-2"></div>
        {% endfor %}
        {% endif %}
    </div>

    <!-- Legend -->
    <div class="flex gap-4 mt-4 text-xs">
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-gray-200"></span> Pending</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-green-200"></span> Approved</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-blue-200"></span> Queued</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-emerald-200"></span> Posted</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-red-200"></span> Rejected</span>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/calendar.html && git commit -m "feat: calendar month view with color-coded status"
```

---

### Task 13: Blog Review Page

**Files:**
- Create: `app/templates/blog_review.html`

- [ ] **Step 1: Create app/templates/blog_review.html**

```html
{% extends "base.html" %}
{% block title %}Blog Posts - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Blog Posts</h2>
        <button hx-post="/api/generate/blog" hx-swap="outerHTML"
                class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90 transition">
            Generate Next Blog Post
        </button>
    </div>

    {% if blogs %}
    {% for blog in blogs %}
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border" id="blog-{{ blog.id }}">
        <div class="flex justify-between items-start mb-4">
            <div>
                <h3 class="text-xl font-bold text-navy">{{ blog.title }}</h3>
                <div class="flex gap-2 mt-2">
                    <span class="text-xs font-semibold px-2 py-0.5 rounded
                        {% if blog.status == 'pending' %}bg-gray-100 text-gray-600
                        {% elif blog.status == 'approved' %}bg-green-100 text-green-700
                        {% elif blog.status == 'rejected' %}bg-red-100 text-red-600
                        {% endif %}">{{ blog.status|upper }}</span>
                    <span class="text-xs text-gray-400">{{ blog.scheduled_date }}</span>
                    {% if blog.hashtags %}
                    <span class="text-xs text-teal">Keyword: {{ blog.hashtags }}</span>
                    {% endif %}
                </div>
            </div>
            {% if blog.image_url %}
            <img src="{{ blog.image_url }}" alt="" class="w-32 h-20 object-cover rounded">
            {% endif %}
        </div>

        <!-- Article preview -->
        <div id="preview-{{ blog.id }}" class="prose prose-sm max-w-none mb-4 border-t pt-4">
            {{ blog.edited_body or blog.body | safe }}
        </div>

        <!-- Edit form (hidden by default) -->
        <div id="edit-blog-{{ blog.id }}" class="hidden border-t pt-4">
            <form hx-post="/api/content/{{ blog.id }}/edit" hx-target="#blog-{{ blog.id }}" hx-swap="outerHTML">
                <label class="block text-sm font-medium text-gray-700 mb-1">Body (HTML)</label>
                <textarea name="body" rows="12" class="w-full border rounded p-2 text-sm font-mono mb-3">{{ blog.edited_body or blog.body }}</textarea>
                <button type="submit" class="px-4 py-1.5 bg-teal text-white text-sm rounded hover:bg-teal/90 transition">Save & Approve</button>
            </form>
        </div>

        <!-- Actions -->
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
    </div>
    {% endfor %}
    {% else %}
    <div class="text-center py-12 text-gray-400">
        <p class="text-lg">No blog posts yet</p>
        <p class="text-sm mt-1">Generate one using the button above</p>
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/blog_review.html && git commit -m "feat: blog post review page with edit and approve"
```

---

### Task 14: Settings Page

**Files:**
- Create: `app/templates/settings.html`

- [ ] **Step 1: Create app/templates/settings.html**

```html
{% extends "base.html" %}
{% block title %}Settings - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <h2 class="text-2xl font-bold text-navy mb-6">Settings</h2>

    <!-- Buffer Connection -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">Buffer Connection</h3>
        <div id="buffer-status">
            <button hx-get="/api/buffer/test" hx-target="#buffer-status" hx-swap="innerHTML"
                    class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">
                Test Connection
            </button>
        </div>
    </div>

    <!-- Social Media Prompt -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">Social Media Prompt</h3>
        <form hx-post="/api/settings/prompt/social" hx-swap="outerHTML" hx-target="this">
            <textarea name="prompt" rows="12" class="w-full border rounded p-3 text-sm font-mono mb-3">{{ social_prompt }}</textarea>
            <button type="submit" class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">Save Prompt</button>
        </form>
    </div>

    <!-- Blog Prompt -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">Blog Post Prompt</h3>
        <form hx-post="/api/settings/prompt/blog" hx-swap="outerHTML" hx-target="this">
            <textarea name="prompt" rows="12" class="w-full border rounded p-3 text-sm font-mono mb-3">{{ blog_prompt }}</textarea>
            <button type="submit" class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">Save Prompt</button>
        </form>
    </div>

    <!-- Blog Topics -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">Blog Topic Queue</h3>
        <div id="topics-list">
            {% for topic in topics %}
            <div class="flex items-center justify-between py-2 border-b last:border-0">
                <div class="flex items-center gap-2">
                    {% if topic.used %}
                    <span class="w-2 h-2 rounded-full bg-green-500" title="Used"></span>
                    {% else %}
                    <span class="w-2 h-2 rounded-full bg-gray-300" title="Unused"></span>
                    {% endif %}
                    <span class="text-sm">{{ topic.topic }}</span>
                    <span class="text-xs text-gray-400">({{ topic.keyword }})</span>
                </div>
            </div>
            {% endfor %}
        </div>

        <!-- Add topic form -->
        <form hx-post="/api/settings/topic/add" hx-target="#topics-list" hx-swap="beforeend" class="mt-4 flex gap-2">
            <input type="text" name="topic" placeholder="Blog topic title" required class="flex-1 border rounded px-3 py-2 text-sm">
            <input type="text" name="keyword" placeholder="Target keyword" required class="w-48 border rounded px-3 py-2 text-sm">
            <button type="submit" class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">Add</button>
        </form>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Add settings API endpoints**

Add to `app/routes/api.py`:

```python
@router.post("/settings/prompt/{prompt_type}", response_class=HTMLResponse)
async def save_prompt(request: Request, prompt_type: str, prompt: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    from pathlib import Path
    filename = "social_media.txt" if prompt_type == "social" else "blog_post.txt"
    Path(f"prompts/{filename}").write_text(prompt)
    log_event("system", f"Updated {prompt_type} prompt template")
    return HTMLResponse(f'<div class="bg-green-50 text-green-700 p-3 rounded">Prompt saved successfully!</div>')


@router.post("/settings/topic/add", response_class=HTMLResponse)
async def add_topic(request: Request, topic: str = Form(...), keyword: str = Form(...)):
    if not _auth_check(request):
        return HTMLResponse("Unauthorized", status_code=401)
    import json
    from pathlib import Path
    topics_path = Path("config/blog_topics.json")
    topics = json.loads(topics_path.read_text()) if topics_path.exists() else []
    topics.append({"topic": topic, "keyword": keyword, "used": False})
    topics_path.write_text(json.dumps(topics, indent=2))
    return HTMLResponse(f'''
    <div class="flex items-center justify-between py-2 border-b">
        <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-gray-300"></span>
            <span class="text-sm">{topic}</span>
            <span class="text-xs text-gray-400">({keyword})</span>
        </div>
    </div>''')
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/settings.html app/routes/api.py
git commit -m "feat: settings page with prompt editor, Buffer test, topic manager"
```

---

### Task 15: Email Notification Service

**Files:**
- Create: `app/services/email_service.py`

- [ ] **Step 1: Create app/services/email_service.py**

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings
from app.database import log_event


def send_notification(subject: str, body: str):
    """Send an email notification. Fails silently if SMTP not configured."""
    if not settings.smtp_user or not settings.notification_email:
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_user
        msg["To"] = settings.notification_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        log_event("email", f"Notification sent: {subject}")
    except Exception as e:
        log_event("error", f"Email failed: {str(e)}")
```

- [ ] **Step 2: Commit**

```bash
git add app/services/email_service.py && git commit -m "feat: SMTP email notification service"
```

---

### Task 16: Logs Page

**Files:**
- Create: `app/templates/logs.html`

- [ ] **Step 1: Create app/templates/logs.html**

```html
{% extends "base.html" %}
{% block title %}Logs - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <h2 class="text-2xl font-bold text-navy mb-6">System Logs</h2>

    <!-- Filters -->
    <div class="flex gap-3 mb-6">
        <select onchange="window.location.href='/dashboard/logs?event_type='+this.value" class="border rounded px-3 py-1.5 text-sm">
            <option value="" {% if not current_type %}selected{% endif %}>All Events</option>
            <option value="generation" {% if current_type == 'generation' %}selected{% endif %}>Generation</option>
            <option value="approval" {% if current_type == 'approval' %}selected{% endif %}>Approval</option>
            <option value="queue" {% if current_type == 'queue' %}selected{% endif %}>Queue</option>
            <option value="error" {% if current_type == 'error' %}selected{% endif %}>Errors</option>
            <option value="system" {% if current_type == 'system' %}selected{% endif %}>System</option>
            <option value="email" {% if current_type == 'email' %}selected{% endif %}>Email</option>
        </select>
    </div>

    <!-- Log entries -->
    <div class="bg-white rounded-lg shadow-sm border overflow-hidden">
        <table class="w-full text-sm">
            <thead class="bg-gray-50">
                <tr>
                    <th class="text-left px-4 py-3 font-semibold text-gray-600">Time</th>
                    <th class="text-left px-4 py-3 font-semibold text-gray-600">Type</th>
                    <th class="text-left px-4 py-3 font-semibold text-gray-600">Message</th>
                </tr>
            </thead>
            <tbody>
                {% for log in logs %}
                <tr class="border-t hover:bg-gray-50">
                    <td class="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">{{ log.created_at }}</td>
                    <td class="px-4 py-3">
                        <span class="text-xs font-semibold px-2 py-0.5 rounded
                            {% if log.event_type == 'error' %}bg-red-100 text-red-600
                            {% elif log.event_type == 'generation' %}bg-purple-100 text-purple-600
                            {% elif log.event_type == 'approval' %}bg-green-100 text-green-600
                            {% elif log.event_type == 'queue' %}bg-blue-100 text-blue-600
                            {% else %}bg-gray-100 text-gray-600
                            {% endif %}">{{ log.event_type }}</span>
                    </td>
                    <td class="px-4 py-3 text-gray-700">{{ log.message }}</td>
                </tr>
                {% endfor %}
                {% if not logs %}
                <tr><td colspan="3" class="px-4 py-8 text-center text-gray-400">No log entries</td></tr>
                {% endif %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/logs.html && git commit -m "feat: system logs page with filterable event log"
```

---

### Task 17: Final Assembly & main.py Completion

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Finalize app/main.py**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.database import init_db
from app.services.scheduler import init_scheduler
from app.routes.auth_routes import router as auth_router
from app.routes.dashboard import router as dashboard_router
from app.routes.api import router as api_router

# Ensure directories exist
Path("media/images").mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)
Path("prompts").mkdir(parents=True, exist_ok=True)
Path("config").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Zerona Content Engine")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(api_router)


@app.on_event("startup")
def startup():
    init_db()
    init_scheduler()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")
```

- [ ] **Step 2: Verify app starts**

```bash
cp .env.example .env
pip install -r requirements.txt
python -c "from app.main import app; print('App loaded successfully')"
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py && git commit -m "feat: finalize main.py with all routes and startup"
```

---

## Build Order Summary

| Task | Component | Est. |
|------|-----------|------|
| 1 | Scaffolding & config | 3 min |
| 2 | Database | 3 min |
| 3 | Auth | 3 min |
| 4 | Prompt templates & topics | 2 min |
| 5 | Content generation (Claude) | 5 min |
| 6 | Image generation (Replicate) | 3 min |
| 7 | Base template & layout | 3 min |
| 8 | Dashboard overview | 3 min |
| 9 | Review queue & API | 5 min |
| 10 | Scheduler | 3 min |
| 11 | Buffer integration | 3 min |
| 12 | Calendar page | 3 min |
| 13 | Blog review page | 3 min |
| 14 | Settings page | 3 min |
| 15 | Email service | 2 min |
| 16 | Logs page | 2 min |
| 17 | Final assembly | 2 min |

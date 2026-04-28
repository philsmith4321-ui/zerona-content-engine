# Module 2: GHL Integration + Referral Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Receive lead events from GoHighLevel, track patient referrals with tiered rewards, and push reward notifications to GHL for sending.

**Architecture:** GHL webhooks flow into a `ghl_events` table for debugging/replay, then trigger referral status transitions. Referral codes generate redirect URLs with UTM params. When reward thresholds are hit, AI-generated congratulations drafts enter a review queue before being pushed to GHL via their v2 API. Credit balances are tracked locally and synced to GHL custom fields.

**Tech Stack:** FastAPI, SQLite (sync sqlite3), Jinja2+HTMX+Tailwind, GHL v2 API (Private Integration Token), Anthropic Claude API, APScheduler

---

## File Structure

**New files:**
| File | Responsibility |
|------|---------------|
| `migrations/004_create_ghl_tables.sql` | All new tables: ghl_events, ghl_contacts, referrals, referral_codes, patient_credits, patient_credit_transactions, reward_notifications |
| `app/services/ghl_service.py` | GHL API client (contacts, custom fields, rate limiter), webhook signature verification |
| `app/services/referral_service.py` | Referral code generation, status transitions, reward threshold logic, credit operations |
| `app/services/reward_service.py` | AI reward copy generation, notification drafts, push-to-GHL |
| `app/ghl_db.py` | All GHL/referral database functions |
| `app/routes/ghl_webhooks.py` | POST /webhooks/ghl endpoint |
| `app/routes/referrals.py` | Dashboard pages: leaderboard, patient history, GHL events, reward queue |
| `app/routes/referral_api.py` | API routes: manual referral entry, approve reward, redeem credit, test harness |
| `app/routes/referral_public.py` | Public /r/{code} redirect (no auth) |
| `app/templates/referrals.html` | Referral leaderboard + stats |
| `app/templates/referral_patient.html` | Per-patient referral history + credits |
| `app/templates/ghl_events.html` | GHL event log viewer with filters |
| `app/templates/reward_queue.html` | Reward notification review queue |
| `app/templates/ghl_test.html` | Test harness for simulating webhooks |
| `prompts/referral_reward.txt` | Claude prompt for reward notification copy |
| `tests/test_referral_flow.py` | End-to-end test: webhook → referral → reward |

**Modified files:**
| File | Change |
|------|--------|
| `app/config.py` | Add GHL env vars |
| `app/main.py` | Register 4 new routers |
| `app/templates/base.html` | Add "Referrals" sidebar link |
| `app/templates/settings.html` | Add GHL connection status card |
| `.env.example` | Add GHL env vars with docs |

---

### Task 1: Database Migration — All New Tables

**Files:**
- Create: `migrations/004_create_ghl_tables.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- GHL Events (webhook log + idempotency)
CREATE TABLE IF NOT EXISTS ghl_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ghl_event_id TEXT UNIQUE,
    event_type TEXT NOT NULL,
    location_id TEXT,
    contact_id TEXT,
    payload TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ghl_events_type ON ghl_events(event_type);
CREATE INDEX IF NOT EXISTS idx_ghl_events_contact ON ghl_events(contact_id);
CREATE INDEX IF NOT EXISTS idx_ghl_events_created ON ghl_events(created_at);

-- GHL Contact Mirror (read-only sync)
CREATE TABLE IF NOT EXISTS ghl_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ghl_contact_id TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    pipeline_stage TEXT DEFAULT '',
    source TEXT DEFAULT '',
    utm_source TEXT DEFAULT '',
    utm_medium TEXT DEFAULT '',
    utm_campaign TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    custom_fields TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ghl_contacts_email ON ghl_contacts(email);
CREATE INDEX IF NOT EXISTS idx_ghl_contacts_ghl_id ON ghl_contacts(ghl_contact_id);

-- Referral Codes (one per patient)
CREATE TABLE IF NOT EXISTS referral_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    code TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);
CREATE INDEX IF NOT EXISTS idx_referral_codes_patient ON referral_codes(patient_id);

-- Referrals
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_patient_id INTEGER NOT NULL REFERENCES patients(id),
    referee_ghl_contact_id TEXT,
    referee_email TEXT DEFAULT '',
    referee_name TEXT DEFAULT '',
    referral_code TEXT NOT NULL,
    source TEXT DEFAULT 'utm',
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    qualified_at TIMESTAMP,
    paid_at TIMESTAMP,
    reward_notified_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_patient_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referee ON referrals(referee_ghl_contact_id);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status);
CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(referral_code);

-- Patient Credits
CREATE TABLE IF NOT EXISTS patient_credits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER UNIQUE NOT NULL REFERENCES patients(id),
    balance_cents INTEGER DEFAULT 0,
    lifetime_earned_cents INTEGER DEFAULT 0,
    lifetime_redeemed_cents INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS patient_credit_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    amount_cents INTEGER NOT NULL,
    type TEXT NOT NULL,
    reference TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_credit_tx_patient ON patient_credit_transactions(patient_id);

-- Reward Notifications (review queue)
CREATE TABLE IF NOT EXISTS reward_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    referral_id INTEGER REFERENCES referrals(id),
    reward_tier TEXT NOT NULL,
    reward_description TEXT NOT NULL,
    channel TEXT DEFAULT 'email',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    status TEXT DEFAULT 'draft',
    ghl_push_result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    pushed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reward_notif_status ON reward_notifications(status);
CREATE INDEX IF NOT EXISTS idx_reward_notif_patient ON reward_notifications(patient_id);
```

- [ ] **Step 2: Verify migration applies on app startup**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.database import get_db, run_migrations; from app.database import init_db; init_db(); run_migrations(); conn = get_db(); print([r['filename'] for r in conn.execute('SELECT filename FROM migrations ORDER BY filename').fetchall()]); conn.close()"`

Expected: List includes `004_create_ghl_tables.sql`

- [ ] **Step 3: Commit**

```bash
git add migrations/004_create_ghl_tables.sql
git commit -m "feat(ghl): add migration 004 with all GHL and referral tables"
```

---

### Task 2: Config + Env Vars

**Files:**
- Modify: `app/config.py:27-32`
- Modify: `.env.example`

- [ ] **Step 1: Add GHL settings to config.py**

Add after the Mailgun block (after line 32):

```python
    # GoHighLevel (GHL) Integration
    ghl_api_token: str = ""
    ghl_location_id: str = ""
    ghl_api_base_url: str = "https://services.leadconnectorhq.com"
    ghl_api_version: str = "2021-07-28"
    ghl_webhook_secret: str = ""
    ghl_referral_landing_url: str = ""
    ghl_credit_balance_field_id: str = ""
    enable_ghl_test_harness: bool = False
```

- [ ] **Step 2: Add env vars to .env.example**

Append to end of `.env.example`:

```
# GoHighLevel (GHL) Integration
# Private Integration Token from GHL Settings > Private Integrations
GHL_API_TOKEN=
# Sub-account Location ID (from GHL Settings > Business Info)
GHL_LOCATION_ID=
# GHL API base URL (default works for most setups)
GHL_API_BASE_URL=https://services.leadconnectorhq.com
# GHL API version header
GHL_API_VERSION=2021-07-28
# Webhook secret for verifying incoming GHL webhooks
GHL_WEBHOOK_SECRET=
# URL to redirect referral links to (GHL funnel page)
# Falls back to whitehousechiropractic.com if not set
GHL_REFERRAL_LANDING_URL=
# GHL Custom Field ID for referral credit balance (find via GHL Custom Fields API)
GHL_CREDIT_BALANCE_FIELD_ID=
# Set to true to enable the webhook test harness at /dashboard/ghl-test
ENABLE_GHL_TEST_HARNESS=false
```

- [ ] **Step 3: Commit**

```bash
git add app/config.py .env.example
git commit -m "feat(ghl): add GHL config settings and env vars"
```

---

### Task 3: GHL Service — API Client + Webhook Verification

**Files:**
- Create: `app/services/ghl_service.py`

- [ ] **Step 1: Create the GHL service**

```python
import hashlib
import hmac
import json
import time
import threading
from datetime import datetime
from typing import Optional

import requests

from app.config import settings
from app.database import log_event


# ── Rate Limiter ─────────────────────────────────────────

class TokenBucketLimiter:
    """Simple token bucket: 100 requests per 10 seconds."""

    def __init__(self, max_tokens: int = 100, refill_seconds: float = 10.0):
        self.max_tokens = max_tokens
        self.refill_seconds = refill_seconds
        self.tokens = max_tokens
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, timeout: float = 30.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                if elapsed >= self.refill_seconds:
                    self.tokens = self.max_tokens
                    self.last_refill = now
                if self.tokens > 0:
                    self.tokens -= 1
                    return True
            time.sleep(0.1)
        return False


_limiter = TokenBucketLimiter()


# ── Auth + Headers ───────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.ghl_api_token}",
        "Content-Type": "application/json",
        "Version": settings.ghl_api_version,
    }


def _api_url(path: str) -> str:
    base = settings.ghl_api_base_url.rstrip("/")
    return f"{base}{path}"


def is_configured() -> bool:
    return bool(settings.ghl_api_token and settings.ghl_location_id)


# ── Webhook Verification ────────────────────────────────

def verify_webhook(request_body: bytes, headers: dict) -> bool:
    """Verify GHL webhook. Supports HMAC-SHA256 shared secret."""
    secret = settings.ghl_webhook_secret
    if not secret:
        return False

    # HMAC-SHA256 verification using shared secret header
    signature = headers.get("x-ghl-signature", "") or headers.get("x-wh-signature", "")
    if signature:
        expected = hmac.new(
            key=secret.encode("utf-8"),
            msg=request_body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # Fallback: simple shared secret comparison in custom header
    header_secret = headers.get("x-ghl-webhook-secret", "")
    if header_secret:
        return hmac.compare_digest(header_secret, secret)

    return False


# ── Contact API ──────────────────────────────────────────

def test_connection() -> dict:
    """Test GHL API connection by fetching location info."""
    if not is_configured():
        return {"connected": False, "error": "GHL not configured"}
    try:
        if not _limiter.acquire():
            return {"connected": False, "error": "Rate limit exceeded"}
        resp = requests.get(
            _api_url(f"/locations/{settings.ghl_location_id}"),
            headers=_headers(), timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            loc = data.get("location", data)
            return {
                "connected": True,
                "name": loc.get("name", ""),
                "address": loc.get("address", ""),
            }
        return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


def get_contact(ghl_contact_id: str) -> Optional[dict]:
    """Fetch a contact from GHL by ID."""
    if not is_configured():
        return None
    try:
        if not _limiter.acquire():
            log_event("warning", "GHL rate limit hit fetching contact")
            return None
        resp = requests.get(
            _api_url(f"/contacts/{ghl_contact_id}"),
            headers=_headers(), timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("contact", resp.json())
        return None
    except Exception as e:
        log_event("error", f"GHL get_contact failed: {e}")
        return None


def update_contact_custom_field(ghl_contact_id: str, field_id: str, value) -> bool:
    """Update a single custom field on a GHL contact."""
    if not is_configured() or not field_id:
        return False
    try:
        if not _limiter.acquire():
            log_event("warning", "GHL rate limit hit updating contact")
            return False
        resp = requests.put(
            _api_url(f"/contacts/{ghl_contact_id}"),
            headers=_headers(), timeout=10,
            json={"customFields": [{"id": field_id, "value": value}]},
        )
        return resp.status_code == 200
    except Exception as e:
        log_event("error", f"GHL update_contact failed: {e}")
        return False


def push_note_to_contact(ghl_contact_id: str, body: str) -> bool:
    """Add a note to a GHL contact (used for reward notifications)."""
    if not is_configured():
        return False
    try:
        if not _limiter.acquire():
            return False
        resp = requests.post(
            _api_url(f"/contacts/{ghl_contact_id}/notes"),
            headers=_headers(), timeout=10,
            json={"body": body, "userId": None},
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        log_event("error", f"GHL push_note failed: {e}")
        return False
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.services.ghl_service import is_configured, verify_webhook, TokenBucketLimiter; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/ghl_service.py
git commit -m "feat(ghl): add GHL API client with rate limiter and webhook verification"
```

---

### Task 4: GHL Database Functions

**Files:**
- Create: `app/ghl_db.py`

- [ ] **Step 1: Create the GHL database module**

```python
import json
from datetime import datetime
from typing import Optional
from app.database import get_db, log_event


# ── GHL Events ───────────────────────────────────────────

def insert_ghl_event(data: dict) -> Optional[int]:
    """Insert a GHL webhook event. Returns None if duplicate (idempotent)."""
    conn = get_db()
    ghl_event_id = data.get("ghl_event_id")

    # Idempotency check
    if ghl_event_id:
        existing = conn.execute(
            "SELECT id FROM ghl_events WHERE ghl_event_id = ?", (ghl_event_id,)
        ).fetchone()
        if existing:
            conn.close()
            return None  # Duplicate — skip

    cursor = conn.execute(
        """INSERT INTO ghl_events (ghl_event_id, event_type, location_id, contact_id, payload, processed)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            ghl_event_id,
            data["event_type"],
            data.get("location_id"),
            data.get("contact_id"),
            json.dumps(data.get("payload", {})),
            0,
        ),
    )
    conn.commit()
    eid = cursor.lastrowid
    conn.close()
    return eid


def mark_ghl_event_processed(event_id: int):
    conn = get_db()
    conn.execute("UPDATE ghl_events SET processed = 1 WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


def get_ghl_events(event_type: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM ghl_events WHERE 1=1"
    params = []
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ghl_event_count(event_type: Optional[str] = None) -> int:
    conn = get_db()
    query = "SELECT COUNT(*) as cnt FROM ghl_events WHERE 1=1"
    params = []
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row["cnt"]


# ── GHL Contacts ─────────────────────────────────────────

def upsert_ghl_contact(data: dict) -> int:
    """Insert or update a GHL contact mirror. Returns row id."""
    conn = get_db()
    now = datetime.now().isoformat()
    existing = conn.execute(
        "SELECT id FROM ghl_contacts WHERE ghl_contact_id = ?", (data["ghl_contact_id"],)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE ghl_contacts SET name=?, first_name=?, last_name=?, email=?, phone=?,
               pipeline_stage=?, source=?, utm_source=?, utm_medium=?, utm_campaign=?,
               tags=?, custom_fields=?, updated_at=? WHERE ghl_contact_id=?""",
            (
                data.get("name", ""), data.get("first_name", ""), data.get("last_name", ""),
                data.get("email", ""), data.get("phone", ""),
                data.get("pipeline_stage", ""), data.get("source", ""),
                data.get("utm_source", ""), data.get("utm_medium", ""), data.get("utm_campaign", ""),
                json.dumps(data.get("tags", [])), json.dumps(data.get("custom_fields", {})),
                now, data["ghl_contact_id"],
            ),
        )
        conn.commit()
        rid = existing["id"]
    else:
        cursor = conn.execute(
            """INSERT INTO ghl_contacts (ghl_contact_id, name, first_name, last_name, email, phone,
               pipeline_stage, source, utm_source, utm_medium, utm_campaign, tags, custom_fields,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["ghl_contact_id"], data.get("name", ""),
                data.get("first_name", ""), data.get("last_name", ""),
                data.get("email", ""), data.get("phone", ""),
                data.get("pipeline_stage", ""), data.get("source", ""),
                data.get("utm_source", ""), data.get("utm_medium", ""), data.get("utm_campaign", ""),
                json.dumps(data.get("tags", [])), json.dumps(data.get("custom_fields", {})),
                now, now,
            ),
        )
        conn.commit()
        rid = cursor.lastrowid
    conn.close()
    return rid


def get_ghl_contact(ghl_contact_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM ghl_contacts WHERE ghl_contact_id = ?", (ghl_contact_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Referral Codes ───────────────────────────────────────

def create_referral_code(patient_id: int, code: str) -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO referral_codes (patient_id, code) VALUES (?, ?)",
        (patient_id, code),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return rid


def get_referral_code_by_patient(patient_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM referral_codes WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_referral_code_by_code(code: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM referral_codes WHERE code = ?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Referrals ────────────────────────────────────────────

def create_referral(data: dict) -> int:
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        """INSERT INTO referrals (referrer_patient_id, referee_ghl_contact_id, referee_email,
           referee_name, referral_code, source, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["referrer_patient_id"], data.get("referee_ghl_contact_id"),
            data.get("referee_email", ""), data.get("referee_name", ""),
            data["referral_code"], data.get("source", "utm"),
            "pending", now,
        ),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return rid


def get_referral(referral_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM referrals WHERE id = ?", (referral_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_referrals_by_referrer(patient_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM referrals WHERE referrer_patient_id = ? ORDER BY created_at DESC",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_referral_by_referee(ghl_contact_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM referrals WHERE referee_ghl_contact_id = ? ORDER BY created_at DESC LIMIT 1",
        (ghl_contact_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_referral(referral_id: int, **kwargs):
    conn = get_db()
    sets = []
    params = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(val)
    params.append(referral_id)
    conn.execute(f"UPDATE referrals SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_referral_leaderboard(limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        """SELECT r.referrer_patient_id, p.first_name, p.last_name, p.email,
                  COUNT(*) as total_referrals,
                  SUM(CASE WHEN r.status = 'paid' THEN 1 ELSE 0 END) as paid_referrals,
                  SUM(CASE WHEN r.status = 'qualified' THEN 1 ELSE 0 END) as qualified_referrals,
                  SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) as pending_referrals
           FROM referrals r JOIN patients p ON r.referrer_patient_id = p.id
           GROUP BY r.referrer_patient_id
           ORDER BY paid_referrals DESC, qualified_referrals DESC, total_referrals DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_paid_referral_count(patient_id: int) -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_patient_id = ? AND status = 'paid'",
        (patient_id,),
    ).fetchone()
    conn.close()
    return row["cnt"]


# ── Patient Credits ──────────────────────────────────────

def get_or_create_patient_credits(patient_id: int) -> dict:
    conn = get_db()
    row = conn.execute("SELECT * FROM patient_credits WHERE patient_id = ?", (patient_id,)).fetchone()
    if row:
        conn.close()
        return dict(row)
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO patient_credits (patient_id, balance_cents, lifetime_earned_cents, lifetime_redeemed_cents, updated_at) VALUES (?, 0, 0, 0, ?)",
        (patient_id, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM patient_credits WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row)


def add_credit(patient_id: int, amount_cents: int, tx_type: str, reference: str = ""):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO patient_credit_transactions (patient_id, amount_cents, type, reference, created_at) VALUES (?, ?, ?, ?, ?)",
        (patient_id, amount_cents, tx_type, reference, now),
    )
    # Update balance
    existing = conn.execute("SELECT id FROM patient_credits WHERE patient_id = ?", (patient_id,)).fetchone()
    if existing:
        if tx_type == "earned":
            conn.execute(
                "UPDATE patient_credits SET balance_cents = balance_cents + ?, lifetime_earned_cents = lifetime_earned_cents + ?, updated_at = ? WHERE patient_id = ?",
                (amount_cents, amount_cents, now, patient_id),
            )
        elif tx_type == "redeemed":
            conn.execute(
                "UPDATE patient_credits SET balance_cents = balance_cents - ?, lifetime_redeemed_cents = lifetime_redeemed_cents + ?, updated_at = ? WHERE patient_id = ?",
                (abs(amount_cents), abs(amount_cents), now, patient_id),
            )
        elif tx_type == "adjusted":
            conn.execute(
                "UPDATE patient_credits SET balance_cents = balance_cents + ?, updated_at = ? WHERE patient_id = ?",
                (amount_cents, now, patient_id),
            )
    else:
        bal = amount_cents if tx_type == "earned" else 0
        earned = amount_cents if tx_type == "earned" else 0
        conn.execute(
            "INSERT INTO patient_credits (patient_id, balance_cents, lifetime_earned_cents, lifetime_redeemed_cents, updated_at) VALUES (?, ?, ?, 0, ?)",
            (patient_id, bal, earned, now),
        )
    conn.commit()
    conn.close()


def get_credit_transactions(patient_id: int, limit: int = 50) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM patient_credit_transactions WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Reward Notifications ─────────────────────────────────

def create_reward_notification(data: dict) -> int:
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        """INSERT INTO reward_notifications (patient_id, referral_id, reward_tier, reward_description,
           channel, subject, body, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["patient_id"], data.get("referral_id"),
            data["reward_tier"], data["reward_description"],
            data.get("channel", "email"), data.get("subject", ""),
            data.get("body", ""), "draft", now,
        ),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return rid


def get_reward_notifications(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = get_db()
    query = """SELECT rn.*, p.first_name, p.last_name, p.email
               FROM reward_notifications rn JOIN patients p ON rn.patient_id = p.id WHERE 1=1"""
    params = []
    if status:
        query += " AND rn.status = ?"
        params.append(status)
    query += " ORDER BY rn.created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_reward_notification(notification_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        """SELECT rn.*, p.first_name, p.last_name, p.email
           FROM reward_notifications rn JOIN patients p ON rn.patient_id = p.id WHERE rn.id = ?""",
        (notification_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_reward_notification(notification_id: int, **kwargs):
    conn = get_db()
    sets = []
    params = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(val)
    params.append(notification_id)
    conn.execute(f"UPDATE reward_notifications SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.ghl_db import insert_ghl_event, upsert_ghl_contact, create_referral, get_referral_leaderboard; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/ghl_db.py
git commit -m "feat(ghl): add all GHL and referral database functions"
```

---

### Task 5: Referral Service — Code Generation + Status Transitions + Rewards

**Files:**
- Create: `app/services/referral_service.py`

- [ ] **Step 1: Create the referral service**

```python
import re
import secrets
import string
from datetime import datetime
from typing import Optional

from app.database import log_event
from app.ghl_db import (
    get_referral_code_by_patient, get_referral_code_by_code,
    create_referral_code, create_referral, get_referral,
    get_referral_by_referee, update_referral, get_paid_referral_count,
    get_or_create_patient_credits, add_credit,
)


# ── Reward Tiers ─────────────────────────────────────────

REWARD_TIERS = [
    {"threshold": 1, "tier": "tier_1", "description": "$100 credit", "amount_cents": 10000},
    {"threshold": 3, "tier": "tier_2", "description": "Free session earned", "amount_cents": 0},
    {"threshold": 5, "tier": "tier_3", "description": "15% VIP ongoing discount unlocked", "amount_cents": 0},
]


# ── Code Generation ──────────────────────────────────────

def _clean_for_code(s: str) -> str:
    """Strip non-alphanumeric characters and lowercase."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _random_chars(n: int) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(n))


def generate_referral_code(patient_id: int, first_name: str = "", phone: str = "") -> str:
    """Generate a unique referral code for a patient.

    Format: {first_name}-{last4_of_phone}-{random3}
    Fallback: random 8-char code if name/phone missing.
    """
    existing = get_referral_code_by_patient(patient_id)
    if existing:
        return existing["code"]

    clean_name = _clean_for_code(first_name)
    clean_phone = re.sub(r"[^0-9]", "", phone)
    phone_last4 = clean_phone[-4:] if len(clean_phone) >= 4 else ""

    if clean_name and phone_last4:
        code = f"{clean_name}-{phone_last4}-{_random_chars(3)}"
    else:
        code = _random_chars(8)

    # Ensure uniqueness
    while get_referral_code_by_code(code):
        code = f"{clean_name or ''}-{phone_last4 or ''}-{_random_chars(3)}" if clean_name else _random_chars(8)

    create_referral_code(patient_id, code)
    log_event("referral", f"Generated referral code '{code}' for patient {patient_id}")
    return code


# ── Referral Creation ────────────────────────────────────

def create_referral_from_webhook(
    referral_code: str, ghl_contact_id: str,
    referee_email: str = "", referee_name: str = "",
) -> Optional[int]:
    """Create a pending referral from a GHL webhook event."""
    code_record = get_referral_code_by_code(referral_code)
    if not code_record:
        log_event("referral", f"Unknown referral code: {referral_code}")
        return None

    # Check if referral already exists for this referee
    existing = get_referral_by_referee(ghl_contact_id)
    if existing:
        log_event("referral", f"Referral already exists for GHL contact {ghl_contact_id}")
        return existing["id"]

    rid = create_referral({
        "referrer_patient_id": code_record["patient_id"],
        "referee_ghl_contact_id": ghl_contact_id,
        "referee_email": referee_email,
        "referee_name": referee_name,
        "referral_code": referral_code,
        "source": "utm",
    })
    log_event("referral", f"New referral created: code={referral_code}, referee={ghl_contact_id}")
    return rid


def create_manual_referral(
    referrer_patient_id: int, referee_ghl_contact_id: str = "",
    referee_email: str = "", referee_name: str = "",
) -> int:
    """Create a referral manually (front desk verbal referral)."""
    code_record = get_referral_code_by_patient(referrer_patient_id)
    referral_code = code_record["code"] if code_record else "manual"

    rid = create_referral({
        "referrer_patient_id": referrer_patient_id,
        "referee_ghl_contact_id": referee_ghl_contact_id,
        "referee_email": referee_email,
        "referee_name": referee_name,
        "referral_code": referral_code,
        "source": "manual",
    })
    log_event("referral", f"Manual referral created: referrer={referrer_patient_id}, referee={referee_name}")
    return rid


# ── Status Transitions ──────────────────────────────────

def advance_referral_to_qualified(ghl_contact_id: str) -> Optional[dict]:
    """Move a referral from pending to qualified (appointment booked)."""
    referral = get_referral_by_referee(ghl_contact_id)
    if not referral:
        return None
    if referral["status"] != "pending":
        return referral  # Already advanced
    update_referral(referral["id"], status="qualified", qualified_at=datetime.now().isoformat())
    log_event("referral", f"Referral {referral['id']} qualified (appointment booked)")
    return get_referral(referral["id"])


def advance_referral_to_paid(ghl_contact_id: str) -> Optional[dict]:
    """Move a referral to paid (opportunity won). Triggers reward check."""
    referral = get_referral_by_referee(ghl_contact_id)
    if not referral:
        return None
    if referral["status"] == "paid":
        return referral  # Already paid
    update_referral(referral["id"], status="paid", paid_at=datetime.now().isoformat())
    log_event("referral", f"Referral {referral['id']} paid (opportunity won)")

    # Check reward thresholds
    check_reward_thresholds(referral["referrer_patient_id"], referral["id"])

    return get_referral(referral["id"])


# ── Reward Threshold Check ───────────────────────────────

def check_reward_thresholds(patient_id: int, referral_id: int):
    """Check if a patient has hit a new reward tier and create notification draft."""
    paid_count = get_paid_referral_count(patient_id)

    for tier in REWARD_TIERS:
        if paid_count == tier["threshold"]:
            # Award credit if applicable
            if tier["amount_cents"] > 0:
                add_credit(patient_id, tier["amount_cents"], "earned", f"referral_{referral_id}")

            # Create reward notification draft
            from app.services.reward_service import create_reward_draft
            create_reward_draft(patient_id, referral_id, tier["tier"], tier["description"])

            log_event("reward", f"Patient {patient_id} hit {tier['tier']}: {tier['description']}")
            break  # Only one tier per transition
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.services.referral_service import generate_referral_code, REWARD_TIERS; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/referral_service.py
git commit -m "feat(ghl): add referral service with code generation, status transitions, and reward logic"
```

---

### Task 6: Reward Service — AI Copy Generation + Push to GHL

**Files:**
- Create: `app/services/reward_service.py`
- Create: `prompts/referral_reward.txt`

- [ ] **Step 1: Create the reward prompt**

```text
You are writing a congratulations message for a patient at White House Chiropractic who has earned a referral reward.

BRAND VOICE:
- Warm, grateful, and celebratory
- Thank them sincerely for their trust in referring friends and family
- Keep it concise — 2-3 short paragraphs max
- Dr. Chris Banning and the team are grateful

Write both an email subject line and body. The body should be plain text suitable for SMS or email.

Respond with ONLY valid JSON (no code fences):
{
    "subject": "the email subject line",
    "body": "the message body (plain text, 2-3 paragraphs)"
}
```

- [ ] **Step 2: Create the reward service**

```python
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import anthropic

from app.config import settings
from app.database import log_event
from app.ghl_db import (
    create_reward_notification, get_reward_notification,
    update_reward_notification, get_referral_by_referee,
    get_or_create_patient_credits,
)
from app.services.ghl_service import push_note_to_contact, update_contact_custom_field


# ── Fallback Templates ───────────────────────────────────

FALLBACK_TEMPLATES = {
    "tier_1": {
        "subject": "You've earned a $100 credit!",
        "body": "Thank you so much for referring a friend to White House Chiropractic! Because your referral completed their treatment, we're delighted to credit your account with $100.\n\nJust mention your referral credit at your next visit and we'll apply it. We truly appreciate you spreading the word about our practice!\n\nWith gratitude,\nDr. Chris Banning & Team",
    },
    "tier_2": {
        "subject": "You've earned a FREE session!",
        "body": "Wow — three successful referrals! You are incredible. As a thank-you, you've earned a complimentary session on us.\n\nCall us or mention it at your next visit to schedule your free session. Your enthusiasm for sharing White House Chiropractic with friends and family means the world to us.\n\nWith gratitude,\nDr. Chris Banning & Team",
    },
    "tier_3": {
        "subject": "Welcome to VIP status — 15% off everything!",
        "body": "Five successful referrals — you are officially a VIP! As our way of saying thank you, you now receive 15% off all services, ongoing.\n\nThis discount applies automatically to every future visit. You've been an extraordinary ambassador for our practice, and we want you to know how much that means to us.\n\nWith gratitude,\nDr. Chris Banning & Team",
    },
}


# ── Draft Creation ───────────────────────────────────────

def create_reward_draft(patient_id: int, referral_id: int, reward_tier: str, reward_description: str):
    """Generate reward notification copy via AI and save as draft for review."""
    from app.campaign_db import get_patients

    # Get patient info
    conn = __import__("app.database", fromlist=["get_db"]).get_db()
    patient = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    patient = dict(patient) if patient else {}

    subject = ""
    body = ""

    # Try AI generation
    try:
        prompt_text = ""
        prompt_path = Path("prompts/referral_reward.txt")
        if prompt_path.exists():
            prompt_text = prompt_path.read_text()

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""{prompt_text}

PATIENT NAME: {patient.get('first_name', 'Valued Patient')} {patient.get('last_name', '')}
REWARD: {reward_description}
REWARD TIER: {reward_tier}

Generate the congratulations message.""",
            }],
        )

        text = message.content[0].text.strip()
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        result = json.loads(text)
        subject = result.get("subject", "")
        body = result.get("body", "")
        log_event("reward", f"AI-generated reward copy for patient {patient_id}")
    except Exception as e:
        log_event("warning", f"AI reward generation failed, using fallback: {e}")
        fallback = FALLBACK_TEMPLATES.get(reward_tier, FALLBACK_TEMPLATES["tier_1"])
        subject = fallback["subject"]
        body = fallback["body"]
        # Personalize fallback
        first_name = patient.get("first_name", "")
        if first_name:
            body = f"Dear {first_name},\n\n{body}"

    create_reward_notification({
        "patient_id": patient_id,
        "referral_id": referral_id,
        "reward_tier": reward_tier,
        "reward_description": reward_description,
        "subject": subject,
        "body": body,
    })


# ── Push to GHL ──────────────────────────────────────────

def push_reward_to_ghl(notification_id: int) -> dict:
    """Push an approved reward notification to GHL as a contact note."""
    notif = get_reward_notification(notification_id)
    if not notif:
        return {"error": "Notification not found"}
    if notif["status"] != "approved":
        return {"error": "Notification must be approved first"}

    # Find the referee's GHL contact ID to push the note to the referrer
    # Actually, the reward goes to the REFERRER — we need their GHL contact
    # For now, push as a note. The referrer may or may not be in GHL.
    # Push the note to the referrer's patient record in our system and log it.

    patient_id = notif["patient_id"]

    # Try to sync credit balance to GHL if the patient has a linked GHL contact
    credits = get_or_create_patient_credits(patient_id)
    balance_dollars = credits["balance_cents"] / 100

    # Log the push
    push_result = {"method": "logged", "notification_id": notification_id}

    # If we have a GHL credit balance field configured, try to update it
    if settings.ghl_credit_balance_field_id:
        # Find if this patient has a GHL contact record
        from app.database import get_db
        conn = get_db()
        # Check if patient email matches a GHL contact
        patient = conn.execute("SELECT email FROM patients WHERE id = ?", (patient_id,)).fetchone()
        ghl_contact = None
        if patient:
            ghl_contact = conn.execute(
                "SELECT ghl_contact_id FROM ghl_contacts WHERE email = ?", (patient["email"],)
            ).fetchone()
        conn.close()

        if ghl_contact:
            ghl_cid = ghl_contact["ghl_contact_id"]
            # Update credit balance custom field
            update_contact_custom_field(ghl_cid, settings.ghl_credit_balance_field_id, str(balance_dollars))
            # Push congratulations as a note
            note_body = f"REFERRAL REWARD: {notif['reward_description']}\n\n{notif['body']}"
            push_note_to_contact(ghl_cid, note_body)
            push_result["method"] = "ghl_api"
            push_result["ghl_contact_id"] = ghl_cid

    now = datetime.now().isoformat()
    update_reward_notification(notification_id, status="pushed", pushed_at=now,
                                ghl_push_result=json.dumps(push_result))
    log_event("reward", f"Reward notification {notification_id} pushed: {push_result.get('method')}")
    return {"success": True, **push_result}
```

- [ ] **Step 3: Verify import**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.services.reward_service import FALLBACK_TEMPLATES, push_reward_to_ghl; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/services/reward_service.py prompts/referral_reward.txt
git commit -m "feat(ghl): add reward service with AI copy generation and GHL push"
```

---

### Task 7: GHL Webhook Endpoint

**Files:**
- Create: `app/routes/ghl_webhooks.py`

- [ ] **Step 1: Create the GHL webhook route**

```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ghl_service import verify_webhook
from app.ghl_db import insert_ghl_event, upsert_ghl_contact, get_ghl_contact
from app.services.referral_service import (
    create_referral_from_webhook, advance_referral_to_qualified,
    advance_referral_to_paid,
)
from app.database import log_event

router = APIRouter()


def _extract_utm_campaign(payload: dict) -> str:
    """Extract referral code from UTM campaign field in webhook payload."""
    # Check top-level fields
    utm = payload.get("utm_campaign", "") or payload.get("utmCampaign", "")
    if utm:
        return utm

    # Check custom fields array
    for cf in payload.get("customFields", []):
        field_key = cf.get("key", "") or cf.get("id", "")
        if "utm_campaign" in field_key.lower() or "utmcampaign" in field_key.lower():
            return cf.get("value", "")

    # Check source field as fallback
    source = payload.get("source", "")
    # If source looks like a referral code pattern (name-digits-chars)
    import re
    if re.match(r"^[a-z]+-\d{4}-[a-z0-9]{3}$", source):
        return source

    return ""


def _extract_contact_data(payload: dict) -> dict:
    """Extract contact fields from GHL webhook payload."""
    custom_fields = {}
    for cf in payload.get("customFields", []):
        key = cf.get("key", cf.get("id", ""))
        custom_fields[key] = cf.get("value", "")

    return {
        "ghl_contact_id": payload.get("id", ""),
        "name": payload.get("name", ""),
        "first_name": payload.get("firstName", ""),
        "last_name": payload.get("lastName", ""),
        "email": payload.get("email", ""),
        "phone": payload.get("phone", ""),
        "source": payload.get("source", ""),
        "utm_source": payload.get("utm_source", "") or custom_fields.get("utm_source", ""),
        "utm_medium": payload.get("utm_medium", "") or custom_fields.get("utm_medium", ""),
        "utm_campaign": payload.get("utm_campaign", "") or custom_fields.get("utm_campaign", ""),
        "tags": payload.get("tags", []),
        "custom_fields": custom_fields,
    }


@router.post("/webhooks/ghl")
async def ghl_webhook(request: Request):
    """Receive GHL webhook events. Public endpoint — verified via signature/secret."""
    try:
        body = await request.body()
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Verify webhook authenticity
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not verify_webhook(body, headers):
        return JSONResponse({"error": "Invalid signature"}, status_code=403)

    event_type = payload.get("type", "unknown")
    location_id = payload.get("locationId", "")

    # Determine contact_id based on event type
    if event_type in ("ContactCreate", "ContactUpdate"):
        contact_id = payload.get("id", "")
    elif event_type in ("OpportunityStageUpdate", "OpportunityStatusUpdate"):
        contact_id = payload.get("contactId", "")
    elif event_type in ("AppointmentCreate", "AppointmentUpdate"):
        appt = payload.get("appointment", {})
        contact_id = appt.get("contactId", "")
    else:
        contact_id = payload.get("contactId", payload.get("id", ""))

    # Build a unique event ID for idempotency
    # GHL doesn't always send a unique event ID, so we construct one
    ghl_event_id = payload.get("eventId", "") or payload.get("id", "")
    if ghl_event_id:
        ghl_event_id = f"{event_type}_{ghl_event_id}"

    # Store event (returns None if duplicate)
    event_id = insert_ghl_event({
        "ghl_event_id": ghl_event_id or None,
        "event_type": event_type,
        "location_id": location_id,
        "contact_id": contact_id,
        "payload": payload,
    })

    if event_id is None:
        log_event("ghl", f"Duplicate event skipped: {ghl_event_id}")
        return JSONResponse({"status": "duplicate_skipped"})

    # Process by event type
    if event_type == "ContactCreate":
        contact_data = _extract_contact_data(payload)
        upsert_ghl_contact(contact_data)

        # Check for referral UTM
        utm_campaign = _extract_utm_campaign(payload)
        utm_source = payload.get("utm_source", "") or contact_data.get("utm_source", "")
        if utm_source == "referral" and utm_campaign:
            create_referral_from_webhook(
                referral_code=utm_campaign,
                ghl_contact_id=contact_id,
                referee_email=payload.get("email", ""),
                referee_name=payload.get("name", payload.get("firstName", "")),
            )

    elif event_type == "ContactUpdate":
        contact_data = _extract_contact_data(payload)
        upsert_ghl_contact(contact_data)

    elif event_type == "AppointmentCreate":
        appt = payload.get("appointment", {})
        appt_contact_id = appt.get("contactId", "")
        if appt_contact_id:
            advance_referral_to_qualified(appt_contact_id)

    elif event_type in ("OpportunityStageUpdate", "OpportunityStatusUpdate"):
        opp_contact_id = payload.get("contactId", "")
        opp_status = payload.get("status", "")
        if opp_status == "won" and opp_contact_id:
            advance_referral_to_paid(opp_contact_id)

    from app.ghl_db import mark_ghl_event_processed
    mark_ghl_event_processed(event_id)

    return JSONResponse({"status": "ok", "event_id": event_id})
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.routes.ghl_webhooks import router; print(f'Routes: {len(router.routes)}')"`

Expected: `Routes: 1`

- [ ] **Step 3: Commit**

```bash
git add app/routes/ghl_webhooks.py
git commit -m "feat(ghl): add GHL webhook endpoint with idempotency and referral processing"
```

---

### Task 8: Public Referral Redirect + Referral Code Generation API

**Files:**
- Create: `app/routes/referral_public.py`

- [ ] **Step 1: Create the public referral route**

```python
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse

from app.config import settings
from app.ghl_db import get_referral_code_by_code
from app.database import log_event

router = APIRouter()


@router.get("/r/{code}")
async def referral_redirect(code: str):
    """Public referral link. Redirects to GHL landing page with UTM params."""
    code_record = get_referral_code_by_code(code.lower().strip())
    if not code_record:
        return HTMLResponse(
            "<h1>Invalid referral link</h1><p>This referral link is not recognized.</p>",
            status_code=404,
        )

    # Build redirect URL
    base_url = settings.ghl_referral_landing_url or "https://www.whitehousechiropractic.com"

    # Parse existing URL to preserve any existing query params
    parsed = urlparse(base_url)
    existing_params = parse_qs(parsed.query)

    # Add UTM params
    utm_params = {
        "utm_source": "referral",
        "utm_medium": "patient_referral",
        "utm_campaign": code,
        "utm_content": str(code_record["patient_id"]),
    }
    existing_params.update(utm_params)

    # Flatten params (parse_qs returns lists)
    flat_params = {}
    for k, v in existing_params.items():
        flat_params[k] = v[0] if isinstance(v, list) else v

    new_query = urlencode(flat_params)
    redirect_url = urlunparse(parsed._replace(query=new_query))

    log_event("referral", f"Referral link clicked: code={code}")
    return RedirectResponse(url=redirect_url, status_code=302)
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.routes.referral_public import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routes/referral_public.py
git commit -m "feat(ghl): add public referral redirect endpoint with UTM params"
```

---

### Task 9: Referral API Routes — Manual Entry, Approve Reward, Redeem Credit

**Files:**
- Create: `app/routes/referral_api.py`

- [ ] **Step 1: Create the referral API routes**

```python
import json
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.ghl_db import (
    get_reward_notification, update_reward_notification,
    get_or_create_patient_credits, add_credit, get_referral_code_by_patient,
)
from app.services.referral_service import (
    generate_referral_code, create_manual_referral,
)
from app.services.reward_service import push_reward_to_ghl
from app.database import log_event

router = APIRouter(prefix="/api/referrals")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return None


# ── Referral Code Generation ─────────────────────────────

@router.post("/generate-code")
async def api_generate_code(request: Request, patient_id: int = Form(...),
                             first_name: str = Form(""), phone: str = Form("")):
    auth = _require_auth(request)
    if auth:
        return auth
    code = generate_referral_code(patient_id, first_name=first_name, phone=phone)
    return HTMLResponse(f'<span class="font-mono text-teal">{code}</span>')


# ── Manual Referral Entry ────────────────────────────────

@router.post("/manual")
async def api_manual_referral(request: Request,
                               referrer_patient_id: int = Form(...),
                               referee_name: str = Form(""),
                               referee_email: str = Form(""),
                               referee_ghl_contact_id: str = Form("")):
    auth = _require_auth(request)
    if auth:
        return auth
    rid = create_manual_referral(
        referrer_patient_id=referrer_patient_id,
        referee_ghl_contact_id=referee_ghl_contact_id,
        referee_email=referee_email,
        referee_name=referee_name,
    )
    return RedirectResponse(
        url=f"/dashboard/referrals/patient/{referrer_patient_id}",
        status_code=303,
    )


# ── Reward Approval + Push ───────────────────────────────

@router.post("/rewards/{notification_id}/approve")
async def api_approve_reward(request: Request, notification_id: int,
                              subject: str = Form(""), body: str = Form("")):
    auth = _require_auth(request)
    if auth:
        return auth
    kwargs = {"status": "approved", "approved_at": datetime.now().isoformat()}
    if subject:
        kwargs["subject"] = subject
    if body:
        kwargs["body"] = body
    update_reward_notification(notification_id, **kwargs)
    log_event("reward", f"Reward notification {notification_id} approved")
    return RedirectResponse(url="/dashboard/referrals/rewards", status_code=303)


@router.post("/rewards/{notification_id}/push")
async def api_push_reward(request: Request, notification_id: int):
    auth = _require_auth(request)
    if auth:
        return auth
    result = push_reward_to_ghl(notification_id)
    if result.get("error"):
        return HTMLResponse(f'<p class="text-red-500 text-sm">{result["error"]}</p>')
    return RedirectResponse(url="/dashboard/referrals/rewards", status_code=303)


# ── Credit Redemption ────────────────────────────────────

@router.post("/credits/{patient_id}/redeem")
async def api_redeem_credit(request: Request, patient_id: int,
                             amount_cents: int = Form(...), note: str = Form("")):
    auth = _require_auth(request)
    if auth:
        return auth
    credits = get_or_create_patient_credits(patient_id)
    if amount_cents > credits["balance_cents"]:
        return HTMLResponse('<p class="text-red-500 text-sm">Insufficient balance</p>')
    add_credit(patient_id, amount_cents, "redeemed", note or "manual_redemption")
    log_event("credit", f"Redeemed {amount_cents} cents for patient {patient_id}")
    return RedirectResponse(url=f"/dashboard/referrals/patient/{patient_id}", status_code=303)
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "from app.routes.referral_api import router; print(f'Routes: {len(router.routes)}')"`

Expected: `Routes: 5`

- [ ] **Step 3: Commit**

```bash
git add app/routes/referral_api.py
git commit -m "feat(ghl): add referral API routes for manual entry, rewards, and credits"
```

---

### Task 10: Referral Dashboard Pages — Leaderboard, Patient History, Events, Rewards

**Files:**
- Create: `app/routes/referrals.py`
- Create: `app/templates/referrals.html`
- Create: `app/templates/referral_patient.html`
- Create: `app/templates/ghl_events.html`
- Create: `app/templates/reward_queue.html`

- [ ] **Step 1: Create the referral dashboard routes**

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.ghl_db import (
    get_referral_leaderboard, get_referrals_by_referrer,
    get_referral_code_by_patient, get_or_create_patient_credits,
    get_credit_transactions, get_ghl_events, get_ghl_event_count,
    get_reward_notifications, get_reward_notification,
)
from app.campaign_db import get_patients
from app.database import get_db
from app.services.ghl_service import is_configured as ghl_is_configured

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


@router.get("/referrals", response_class=HTMLResponse)
async def referrals_dashboard(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    leaderboard = get_referral_leaderboard(limit=20)

    # Get summary stats
    conn = get_db()
    total_referrals = conn.execute("SELECT COUNT(*) as cnt FROM referrals").fetchone()["cnt"]
    pending = conn.execute("SELECT COUNT(*) as cnt FROM referrals WHERE status = 'pending'").fetchone()["cnt"]
    qualified = conn.execute("SELECT COUNT(*) as cnt FROM referrals WHERE status = 'qualified'").fetchone()["cnt"]
    paid = conn.execute("SELECT COUNT(*) as cnt FROM referrals WHERE status = 'paid'").fetchone()["cnt"]
    pending_rewards = conn.execute("SELECT COUNT(*) as cnt FROM reward_notifications WHERE status = 'draft'").fetchone()["cnt"]
    conn.close()

    return templates.TemplateResponse("referrals.html", {
        "request": request, "active": "referrals",
        "leaderboard": leaderboard,
        "stats": {"total": total_referrals, "pending": pending, "qualified": qualified, "paid": paid},
        "pending_rewards": pending_rewards,
        "ghl_configured": ghl_is_configured(),
    })


@router.get("/referrals/patient/{patient_id}", response_class=HTMLResponse)
async def referral_patient_detail(request: Request, patient_id: int):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    if not patient:
        return RedirectResponse(url="/dashboard/referrals", status_code=303)
    patient = dict(patient)

    referrals = get_referrals_by_referrer(patient_id)
    code_record = get_referral_code_by_patient(patient_id)
    credits = get_or_create_patient_credits(patient_id)
    transactions = get_credit_transactions(patient_id)

    return templates.TemplateResponse("referral_patient.html", {
        "request": request, "active": "referrals",
        "patient": patient, "referrals": referrals,
        "referral_code": code_record["code"] if code_record else None,
        "credits": credits, "transactions": transactions,
    })


@router.get("/referrals/events", response_class=HTMLResponse)
async def ghl_events_page(request: Request, event_type: str = "", page: int = 1):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    per_page = 50
    offset = (page - 1) * per_page
    events = get_ghl_events(event_type=event_type or None, limit=per_page, offset=offset)
    total = get_ghl_event_count(event_type=event_type or None)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse("ghl_events.html", {
        "request": request, "active": "referrals",
        "events": events, "current_type": event_type,
        "page": page, "total_pages": total_pages, "total": total,
    })


@router.get("/referrals/rewards", response_class=HTMLResponse)
async def reward_queue_page(request: Request, status: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    notifications = get_reward_notifications(status=status or None)
    return templates.TemplateResponse("reward_queue.html", {
        "request": request, "active": "referrals",
        "notifications": notifications, "current_status": status,
    })
```

- [ ] **Step 2: Create referrals.html template**

```html
{% extends "base.html" %}
{% block title %}Referrals - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-2xl font-bold text-navy">Referral Program</h2>
        <div class="flex gap-2">
            <a href="/dashboard/referrals/rewards" class="bg-gray-500 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-gray-600 transition">
                Rewards Queue {% if pending_rewards %}({{ pending_rewards }}){% endif %}
            </a>
            <a href="/dashboard/referrals/events" class="bg-gray-500 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-gray-600 transition">
                GHL Events
            </a>
        </div>
    </div>

    {% if not ghl_configured %}
    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
        <p class="text-sm text-yellow-800">GHL is not configured. Set GHL_API_TOKEN and GHL_LOCATION_ID in your environment to enable integration.</p>
    </div>
    {% endif %}

    <!-- Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-blue-500">
            <p class="text-xs text-gray-500">Total Referrals</p>
            <p class="text-2xl font-bold text-navy">{{ stats.total }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-yellow-500">
            <p class="text-xs text-gray-500">Pending</p>
            <p class="text-2xl font-bold text-navy">{{ stats.pending }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-blue-400">
            <p class="text-xs text-gray-500">Qualified</p>
            <p class="text-2xl font-bold text-navy">{{ stats.qualified }}</p>
        </div>
        <div class="bg-white rounded-lg p-3 shadow-sm border-l-4 border-green-500">
            <p class="text-xs text-gray-500">Paid (Converted)</p>
            <p class="text-2xl font-bold text-navy">{{ stats.paid }}</p>
        </div>
    </div>

    <!-- Leaderboard -->
    <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Referral Leaderboard</h3>
        {% if leaderboard %}
        <table class="w-full text-sm">
            <thead class="bg-gray-50">
                <tr>
                    <th class="text-left p-3">Rank</th>
                    <th class="text-left p-3">Patient</th>
                    <th class="text-center p-3">Paid</th>
                    <th class="text-center p-3">Qualified</th>
                    <th class="text-center p-3">Pending</th>
                    <th class="text-center p-3">Total</th>
                    <th class="text-right p-3"></th>
                </tr>
            </thead>
            <tbody>
                {% for row in leaderboard %}
                <tr class="border-t hover:bg-gray-50">
                    <td class="p-3 font-semibold text-navy">{{ loop.index }}</td>
                    <td class="p-3">
                        <p class="font-semibold">{{ row.first_name }} {{ row.last_name }}</p>
                        <p class="text-xs text-gray-400">{{ row.email }}</p>
                    </td>
                    <td class="p-3 text-center font-semibold text-green-600">{{ row.paid_referrals }}</td>
                    <td class="p-3 text-center text-blue-600">{{ row.qualified_referrals }}</td>
                    <td class="p-3 text-center text-yellow-600">{{ row.pending_referrals }}</td>
                    <td class="p-3 text-center">{{ row.total_referrals }}</td>
                    <td class="p-3 text-right">
                        <a href="/dashboard/referrals/patient/{{ row.referrer_patient_id }}" class="text-teal text-sm hover:underline">View</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="text-gray-400 text-center py-8">No referrals yet</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Create referral_patient.html template**

```html
{% extends "base.html" %}
{% block title %}{{ patient.first_name }} {{ patient.last_name }} - Referrals{% endblock %}
{% block content %}
<div class="mb-8">
    <a href="/dashboard/referrals" class="text-sm text-teal hover:underline">&larr; Back to Leaderboard</a>
    <h2 class="text-2xl font-bold text-navy mt-2">{{ patient.first_name }} {{ patient.last_name }}</h2>
    <p class="text-sm text-gray-500">{{ patient.email }}</p>

    <!-- Referral Code -->
    <div class="bg-white rounded-lg shadow-sm p-6 mt-4 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Referral Code</h3>
        {% if referral_code %}
        <div class="flex items-center gap-4">
            <span class="font-mono text-lg text-teal bg-teal/10 px-4 py-2 rounded">{{ referral_code }}</span>
            <span class="text-sm text-gray-500">Link: /r/{{ referral_code }}</span>
        </div>
        {% else %}
        <form hx-post="/api/referrals/generate-code" hx-target="#code-result" hx-swap="innerHTML">
            <input type="hidden" name="patient_id" value="{{ patient.id }}">
            <input type="hidden" name="first_name" value="{{ patient.first_name }}">
            <input type="hidden" name="phone" value="{{ patient.phone }}">
            <button class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90">Generate Code</button>
            <span id="code-result" class="ml-3"></span>
        </form>
        {% endif %}
    </div>

    <!-- Credit Balance -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Credit Balance</h3>
        <div class="grid grid-cols-3 gap-4 mb-4">
            <div class="text-center p-3 bg-green-50 rounded">
                <p class="text-2xl font-bold text-green-700">${{ "%.2f"|format(credits.balance_cents / 100) }}</p>
                <p class="text-xs text-gray-500">Current Balance</p>
            </div>
            <div class="text-center p-3 bg-blue-50 rounded">
                <p class="text-2xl font-bold text-blue-700">${{ "%.2f"|format(credits.lifetime_earned_cents / 100) }}</p>
                <p class="text-xs text-gray-500">Lifetime Earned</p>
            </div>
            <div class="text-center p-3 bg-gray-50 rounded">
                <p class="text-2xl font-bold text-gray-700">${{ "%.2f"|format(credits.lifetime_redeemed_cents / 100) }}</p>
                <p class="text-xs text-gray-500">Lifetime Redeemed</p>
            </div>
        </div>
        {% if credits.balance_cents > 0 %}
        <form method="POST" action="/api/referrals/credits/{{ patient.id }}/redeem" class="flex gap-2">
            <input type="number" name="amount_cents" placeholder="Amount (cents)" required min="1" max="{{ credits.balance_cents }}" class="border rounded px-3 py-2 text-sm w-40">
            <input type="text" name="note" placeholder="Note (optional)" class="border rounded px-3 py-2 text-sm flex-1">
            <button class="bg-gray-500 text-white px-4 py-2 rounded text-sm hover:bg-gray-600">Redeem</button>
        </form>
        {% endif %}
    </div>

    <!-- Manual Referral Entry -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Add Manual Referral</h3>
        <form method="POST" action="/api/referrals/manual" class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input type="hidden" name="referrer_patient_id" value="{{ patient.id }}">
            <input type="text" name="referee_name" placeholder="Referee name" required class="border rounded px-3 py-2 text-sm">
            <input type="email" name="referee_email" placeholder="Referee email (optional)" class="border rounded px-3 py-2 text-sm">
            <input type="text" name="referee_ghl_contact_id" placeholder="GHL Contact ID (optional)" class="border rounded px-3 py-2 text-sm">
            <button class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90">Add Referral</button>
        </form>
    </div>

    <!-- Referral History -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Referral History</h3>
        {% if referrals %}
        <table class="w-full text-sm">
            <thead class="bg-gray-50">
                <tr>
                    <th class="text-left p-3">Referee</th>
                    <th class="text-left p-3">Source</th>
                    <th class="text-left p-3">Status</th>
                    <th class="text-left p-3">Created</th>
                </tr>
            </thead>
            <tbody>
                {% for ref in referrals %}
                <tr class="border-t">
                    <td class="p-3">{{ ref.referee_name or ref.referee_email or ref.referee_ghl_contact_id or "Unknown" }}</td>
                    <td class="p-3"><span class="text-xs px-2 py-1 rounded bg-gray-100">{{ ref.source }}</span></td>
                    <td class="p-3">
                        <span class="px-2 py-1 rounded text-xs font-medium
                            {% if ref.status == 'paid' %}bg-green-100 text-green-700
                            {% elif ref.status == 'qualified' %}bg-blue-100 text-blue-700
                            {% else %}bg-yellow-100 text-yellow-700{% endif %}">
                            {{ ref.status }}
                        </span>
                    </td>
                    <td class="p-3 text-gray-500">{{ ref.created_at[:10] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="text-gray-400 text-center py-4">No referrals yet</p>
        {% endif %}
    </div>

    <!-- Credit Transaction History -->
    {% if transactions %}
    <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Credit Transactions</h3>
        <table class="w-full text-sm">
            <thead class="bg-gray-50">
                <tr>
                    <th class="text-left p-3">Type</th>
                    <th class="text-right p-3">Amount</th>
                    <th class="text-left p-3">Reference</th>
                    <th class="text-left p-3">Date</th>
                </tr>
            </thead>
            <tbody>
                {% for tx in transactions %}
                <tr class="border-t">
                    <td class="p-3">
                        <span class="px-2 py-1 rounded text-xs font-medium
                            {% if tx.type == 'earned' %}bg-green-100 text-green-700
                            {% elif tx.type == 'redeemed' %}bg-red-100 text-red-700
                            {% else %}bg-gray-100 text-gray-700{% endif %}">
                            {{ tx.type }}
                        </span>
                    </td>
                    <td class="p-3 text-right font-mono {% if tx.type == 'redeemed' %}text-red-600{% else %}text-green-600{% endif %}">
                        {{ "+" if tx.type != "redeemed" else "-" }}${{ "%.2f"|format(tx.amount_cents|abs / 100) }}
                    </td>
                    <td class="p-3 text-gray-500">{{ tx.reference }}</td>
                    <td class="p-3 text-gray-500">{{ tx.created_at[:10] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 4: Create ghl_events.html template**

```html
{% extends "base.html" %}
{% block title %}GHL Events - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <div>
            <a href="/dashboard/referrals" class="text-sm text-teal hover:underline">&larr; Back to Referrals</a>
            <h2 class="text-2xl font-bold text-navy mt-1">GHL Event Log</h2>
            <p class="text-sm text-gray-500">{{ total }} total events</p>
        </div>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-4">
        <select onchange="window.location.href='/dashboard/referrals/events?event_type='+this.value" class="border rounded px-3 py-1.5 text-sm">
            <option value="" {% if not current_type %}selected{% endif %}>All Events</option>
            <option value="ContactCreate" {% if current_type == 'ContactCreate' %}selected{% endif %}>ContactCreate</option>
            <option value="ContactUpdate" {% if current_type == 'ContactUpdate' %}selected{% endif %}>ContactUpdate</option>
            <option value="AppointmentCreate" {% if current_type == 'AppointmentCreate' %}selected{% endif %}>AppointmentCreate</option>
            <option value="OpportunityStageUpdate" {% if current_type == 'OpportunityStageUpdate' %}selected{% endif %}>OpportunityStageUpdate</option>
            <option value="OpportunityStatusUpdate" {% if current_type == 'OpportunityStatusUpdate' %}selected{% endif %}>OpportunityStatusUpdate</option>
        </select>
    </div>

    <!-- Events Table -->
    <div class="bg-white rounded-lg shadow-sm overflow-hidden">
        {% if events %}
        <table class="w-full text-sm">
            <thead class="bg-gray-50">
                <tr>
                    <th class="text-left p-3">ID</th>
                    <th class="text-left p-3">Type</th>
                    <th class="text-left p-3">Contact</th>
                    <th class="text-left p-3">Processed</th>
                    <th class="text-left p-3">Time</th>
                </tr>
            </thead>
            <tbody>
                {% for evt in events %}
                <tr class="border-t hover:bg-gray-50">
                    <td class="p-3 font-mono text-xs">{{ evt.id }}</td>
                    <td class="p-3">
                        <span class="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">{{ evt.event_type }}</span>
                    </td>
                    <td class="p-3 font-mono text-xs">{{ evt.contact_id[:12] if evt.contact_id else "—" }}...</td>
                    <td class="p-3">
                        {% if evt.processed %}<span class="text-green-600">Yes</span>{% else %}<span class="text-yellow-600">No</span>{% endif %}
                    </td>
                    <td class="p-3 text-gray-500">{{ evt.created_at }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="text-gray-400 text-center py-8">No events received yet</p>
        {% endif %}
    </div>

    <!-- Pagination -->
    {% if total_pages > 1 %}
    <div class="flex justify-center gap-2 mt-4">
        {% if page > 1 %}
        <a href="/dashboard/referrals/events?event_type={{ current_type }}&page={{ page - 1 }}" class="px-3 py-1 border rounded text-sm hover:bg-gray-50">Prev</a>
        {% endif %}
        <span class="px-3 py-1 text-sm text-gray-500">Page {{ page }} of {{ total_pages }}</span>
        {% if page < total_pages %}
        <a href="/dashboard/referrals/events?event_type={{ current_type }}&page={{ page + 1 }}" class="px-3 py-1 border rounded text-sm hover:bg-gray-50">Next</a>
        {% endif %}
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Create reward_queue.html template**

```html
{% extends "base.html" %}
{% block title %}Reward Queue - Zerona Content Engine{% endblock %}
{% block content %}
<div class="mb-8">
    <div class="flex justify-between items-center mb-6">
        <div>
            <a href="/dashboard/referrals" class="text-sm text-teal hover:underline">&larr; Back to Referrals</a>
            <h2 class="text-2xl font-bold text-navy mt-1">Reward Notifications</h2>
        </div>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-4">
        <select onchange="window.location.href='/dashboard/referrals/rewards?status='+this.value" class="border rounded px-3 py-1.5 text-sm">
            <option value="" {% if not current_status %}selected{% endif %}>All</option>
            <option value="draft" {% if current_status == 'draft' %}selected{% endif %}>Draft (Pending Review)</option>
            <option value="approved" {% if current_status == 'approved' %}selected{% endif %}>Approved</option>
            <option value="pushed" {% if current_status == 'pushed' %}selected{% endif %}>Pushed to GHL</option>
        </select>
    </div>

    <!-- Notifications -->
    <div class="space-y-4">
        {% for notif in notifications %}
        <div class="bg-white rounded-lg shadow-sm p-6">
            <div class="flex justify-between items-start mb-3">
                <div>
                    <h3 class="font-semibold text-navy">{{ notif.first_name }} {{ notif.last_name }}</h3>
                    <p class="text-sm text-gray-500">{{ notif.reward_description }} ({{ notif.reward_tier }})</p>
                </div>
                <span class="px-2 py-1 rounded text-xs font-medium
                    {% if notif.status == 'draft' %}bg-yellow-100 text-yellow-700
                    {% elif notif.status == 'approved' %}bg-blue-100 text-blue-700
                    {% elif notif.status == 'pushed' %}bg-green-100 text-green-700
                    {% else %}bg-gray-100 text-gray-700{% endif %}">
                    {{ notif.status | upper }}
                </span>
            </div>

            {% if notif.status == 'draft' %}
            <form method="POST" action="/api/referrals/rewards/{{ notif.id }}/approve">
                <div class="mb-3">
                    <label class="text-xs text-gray-500 block mb-1">Subject</label>
                    <input type="text" name="subject" value="{{ notif.subject }}" class="w-full border rounded px-3 py-2 text-sm">
                </div>
                <div class="mb-3">
                    <label class="text-xs text-gray-500 block mb-1">Body</label>
                    <textarea name="body" rows="4" class="w-full border rounded px-3 py-2 text-sm">{{ notif.body }}</textarea>
                </div>
                <button class="bg-green-500 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-green-600">Approve</button>
            </form>
            {% elif notif.status == 'approved' %}
            <div class="bg-gray-50 rounded p-3 mb-3 text-sm">
                <p class="font-semibold">{{ notif.subject }}</p>
                <p class="text-gray-600 mt-1 whitespace-pre-line">{{ notif.body }}</p>
            </div>
            <form method="POST" action="/api/referrals/rewards/{{ notif.id }}/push" class="inline">
                <button class="bg-teal text-white px-4 py-2 rounded text-sm font-semibold hover:bg-teal/90"
                        onclick="return confirm('Push this notification to GHL?')">
                    Approve & Push to GHL
                </button>
            </form>
            {% else %}
            <div class="bg-gray-50 rounded p-3 text-sm">
                <p class="font-semibold">{{ notif.subject }}</p>
                <p class="text-gray-600 mt-1 whitespace-pre-line">{{ notif.body }}</p>
                <p class="text-xs text-gray-400 mt-2">Pushed at {{ notif.pushed_at }}</p>
            </div>
            {% endif %}
        </div>
        {% else %}
        <div class="text-center py-12 text-gray-400">
            <p class="text-lg">No reward notifications</p>
            <p class="text-sm mt-1">Notifications appear here when patients hit referral reward thresholds</p>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
git add app/routes/referrals.py app/templates/referrals.html app/templates/referral_patient.html app/templates/ghl_events.html app/templates/reward_queue.html
git commit -m "feat(ghl): add referral dashboard pages with leaderboard, patient detail, events, and reward queue"
```

---

### Task 11: GHL Test Harness

**Files:**
- Create: `app/templates/ghl_test.html`

- [ ] **Step 1: Add test harness route to referral_api.py**

Add to the end of `app/routes/referral_api.py`:

```python
from app.config import settings as app_settings
from fastapi.templating import Jinja2Templates as _Templates

_tmpl = Jinja2Templates(directory="app/templates")


@router.get("/test-harness", response_class=HTMLResponse)
async def ghl_test_harness(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    if not app_settings.enable_ghl_test_harness:
        return HTMLResponse("<h1>Test harness disabled</h1><p>Set ENABLE_GHL_TEST_HARNESS=true to enable.</p>", status_code=403)
    return _tmpl.TemplateResponse("ghl_test.html", {"request": request, "active": "referrals"})


@router.post("/test-harness/send")
async def ghl_test_send(request: Request, event_type: str = Form(...),
                         contact_email: str = Form("test@example.com"),
                         contact_name: str = Form("Test User"),
                         referral_code: str = Form("")):
    """Simulate a GHL webhook event for testing."""
    auth = _require_auth(request)
    if auth:
        return auth
    if not app_settings.enable_ghl_test_harness:
        return JSONResponse({"error": "Test harness disabled"}, status_code=403)

    import uuid
    fake_contact_id = f"test_{uuid.uuid4().hex[:12]}"
    first_name = contact_name.split()[0] if contact_name else "Test"
    last_name = contact_name.split()[-1] if len(contact_name.split()) > 1 else ""

    payloads = {
        "ContactCreate": {
            "type": "ContactCreate",
            "locationId": app_settings.ghl_location_id or "test_location",
            "id": fake_contact_id,
            "email": contact_email,
            "name": contact_name,
            "firstName": first_name,
            "lastName": last_name,
            "phone": "+16155550000",
            "source": referral_code if referral_code else "test",
            "utm_source": "referral" if referral_code else "",
            "utm_campaign": referral_code,
            "utm_medium": "patient_referral" if referral_code else "",
            "dateAdded": datetime.now().isoformat(),
            "tags": [],
            "customFields": [],
        },
        "AppointmentCreate": {
            "type": "AppointmentCreate",
            "locationId": app_settings.ghl_location_id or "test_location",
            "appointment": {
                "id": f"appt_{uuid.uuid4().hex[:8]}",
                "contactId": fake_contact_id,
                "title": "Zerona Consultation",
                "appointmentStatus": "confirmed",
                "startTime": datetime.now().isoformat(),
            },
        },
        "OpportunityStatusUpdate": {
            "type": "OpportunityStatusUpdate",
            "locationId": app_settings.ghl_location_id or "test_location",
            "id": f"opp_{uuid.uuid4().hex[:8]}",
            "contactId": fake_contact_id,
            "status": "won",
            "monetaryValue": 2500,
            "name": "Zerona Package",
        },
    }

    payload = payloads.get(event_type)
    if not payload:
        return HTMLResponse(f'<p class="text-red-500">Unknown event type: {event_type}</p>')

    # Process directly (skip webhook signature verification)
    from app.ghl_db import insert_ghl_event, upsert_ghl_contact
    from app.services.referral_service import (
        create_referral_from_webhook, advance_referral_to_qualified,
        advance_referral_to_paid,
    )

    event_id = insert_ghl_event({
        "ghl_event_id": f"test_{event_type}_{uuid.uuid4().hex[:8]}",
        "event_type": event_type,
        "location_id": payload.get("locationId", ""),
        "contact_id": fake_contact_id,
        "payload": payload,
    })

    result_msg = f"Event stored (ID: {event_id}). "

    if event_type == "ContactCreate":
        from app.routes.ghl_webhooks import _extract_contact_data, _extract_utm_campaign
        contact_data = _extract_contact_data(payload)
        upsert_ghl_contact(contact_data)
        result_msg += "Contact mirrored. "
        utm_campaign = _extract_utm_campaign(payload)
        if payload.get("utm_source") == "referral" and utm_campaign:
            rid = create_referral_from_webhook(utm_campaign, fake_contact_id, contact_email, contact_name)
            result_msg += f"Referral created (ID: {rid}). " if rid else "Referral already exists. "

    elif event_type == "AppointmentCreate":
        ref = advance_referral_to_qualified(fake_contact_id)
        result_msg += f"Referral qualified. " if ref else "No matching referral found. "

    elif event_type == "OpportunityStatusUpdate":
        ref = advance_referral_to_paid(fake_contact_id)
        result_msg += f"Referral marked paid. " if ref else "No matching referral found. "

    from app.ghl_db import mark_ghl_event_processed
    if event_id:
        mark_ghl_event_processed(event_id)

    return HTMLResponse(f'<p class="text-green-600 text-sm mt-2">{result_msg}</p>')
```

- [ ] **Step 2: Create ghl_test.html template**

```html
{% extends "base.html" %}
{% block title %}GHL Test Harness - Zerona Content Engine{% endblock %}
{% block content %}
<div class="max-w-3xl mx-auto mb-8">
    <div class="mb-6">
        <a href="/dashboard/referrals" class="text-sm text-teal hover:underline">&larr; Back to Referrals</a>
        <h2 class="text-2xl font-bold text-navy mt-1">GHL Webhook Test Harness</h2>
        <p class="text-sm text-gray-500">Simulate GHL webhook events to test the referral flow end-to-end.</p>
    </div>

    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
        <p class="text-sm text-yellow-800">This page bypasses webhook signature verification. Only available when ENABLE_GHL_TEST_HARNESS=true.</p>
    </div>

    <!-- Test Flow Instructions -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h3 class="text-lg font-semibold text-navy mb-3">Test Flow</h3>
        <ol class="text-sm text-gray-600 space-y-2 list-decimal list-inside">
            <li>First, generate a referral code for a patient on their Referral detail page</li>
            <li>Send a <strong>ContactCreate</strong> with that referral code to create a pending referral</li>
            <li>Copy the generated Contact ID from the result</li>
            <li>Send an <strong>AppointmentCreate</strong> with that Contact ID to qualify the referral</li>
            <li>Send an <strong>OpportunityWon</strong> with that Contact ID to mark it paid and trigger rewards</li>
            <li>Check the Rewards Queue for the generated notification draft</li>
        </ol>
    </div>

    <!-- Event Simulator -->
    <div class="bg-white rounded-lg shadow-sm p-6">
        <h3 class="text-lg font-semibold text-navy mb-4">Send Test Event</h3>
        <form hx-post="/api/referrals/test-harness/send" hx-target="#test-result" hx-swap="innerHTML">
            <div class="grid grid-cols-1 gap-4 mb-4">
                <div>
                    <label class="text-sm font-medium text-gray-700 block mb-1">Event Type</label>
                    <select name="event_type" class="w-full border rounded px-3 py-2 text-sm">
                        <option value="ContactCreate">ContactCreate (new lead)</option>
                        <option value="AppointmentCreate">AppointmentCreate (booked)</option>
                        <option value="OpportunityStatusUpdate">OpportunityWon (purchased)</option>
                    </select>
                </div>
                <div>
                    <label class="text-sm font-medium text-gray-700 block mb-1">Contact Email</label>
                    <input type="email" name="contact_email" value="test@example.com" class="w-full border rounded px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="text-sm font-medium text-gray-700 block mb-1">Contact Name</label>
                    <input type="text" name="contact_name" value="Test Referral" class="w-full border rounded px-3 py-2 text-sm">
                </div>
                <div>
                    <label class="text-sm font-medium text-gray-700 block mb-1">Referral Code (for ContactCreate only)</label>
                    <input type="text" name="referral_code" placeholder="e.g., sarah-4821-x7k" class="w-full border rounded px-3 py-2 text-sm">
                </div>
            </div>
            <button class="bg-teal text-white px-6 py-2 rounded text-sm font-semibold hover:bg-teal/90">Send Event</button>
        </form>
        <div id="test-result" class="mt-3"></div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/referral_api.py app/templates/ghl_test.html
git commit -m "feat(ghl): add webhook test harness for simulating GHL events"
```

---

### Task 12: Wire Up Routers + Sidebar + Settings

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/base.html`
- Modify: `app/templates/settings.html`

- [ ] **Step 1: Register new routers in main.py**

Add imports after the existing campaign imports (after line 14):

```python
from app.routes.ghl_webhooks import router as ghl_webhooks_router
from app.routes.referrals import router as referrals_router
from app.routes.referral_api import router as referral_api_router
from app.routes.referral_public import router as referral_public_router
```

Add router registrations after line 32 (`app.include_router(campaign_api_router)`):

```python
app.include_router(ghl_webhooks_router)
app.include_router(referrals_router)
app.include_router(referral_api_router)
app.include_router(referral_public_router)
```

- [ ] **Step 2: Add Referrals link to sidebar in base.html**

In `app/templates/base.html`, add after the Campaigns link (after line 31):

```html
                <a href="/dashboard/referrals" class="block px-6 py-3 text-sm hover:bg-white/10 {% if active == 'referrals' %}bg-white/10 border-r-2 border-teal{% endif %}">Referrals</a>
```

Also add to mobile nav (after the Campaigns link around line 53):

```html
                <a href="/dashboard/referrals" class="block py-3 text-white">Referrals</a>
```

- [ ] **Step 3: Add GHL status card to settings.html**

Add after the WordPress section (after line 45) in `app/templates/settings.html`:

```html
    <!-- GHL Connection -->
    <div class="bg-white rounded-lg shadow-sm p-6 mb-6 border">
        <h3 class="text-lg font-semibold text-navy mb-3">GoHighLevel (GHL)</h3>
        <p class="text-sm text-gray-500 mb-3">Integration with GoHighLevel CRM for referral tracking and content push. Configure GHL_API_TOKEN and GHL_LOCATION_ID in your .env file.</p>
        <div id="ghl-status">
            <button hx-get="/api/campaigns/ghl/test" hx-target="#ghl-status" hx-swap="innerHTML"
                    class="bg-teal text-white px-4 py-2 rounded text-sm hover:bg-teal/90 transition">
                Test Connection
            </button>
        </div>
    </div>
```

- [ ] **Step 4: Add GHL test connection API endpoint to campaign_api.py**

Add at the end of `app/routes/campaign_api.py`:

```python
from app.services.ghl_service import test_connection as ghl_test_connection, is_configured as ghl_is_configured


@router.get("/ghl/test")
async def api_ghl_test(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    result = ghl_test_connection()
    return JSONResponse(result)
```

- [ ] **Step 5: Verify app starts cleanly**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && timeout 5 python3 -c "from app.main import app; print(f'Routes: {len(app.routes)}')" || true`

Expected: Prints route count without errors

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/templates/base.html app/templates/settings.html app/routes/campaign_api.py
git commit -m "feat(ghl): wire up routers, add sidebar link, add GHL status to settings"
```

---

### Task 13: End-to-End Test Script

**Files:**
- Create: `tests/test_referral_flow.py`

- [ ] **Step 1: Create the test script**

```python
"""End-to-end test for the referral flow.

Simulates: webhook → referral creation → qualification → payment → reward generation.
Run with: python3 tests/test_referral_flow.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, run_migrations, get_db
from app.campaign_db import upsert_patient
from app.ghl_db import (
    insert_ghl_event, upsert_ghl_contact, get_referral_code_by_patient,
    get_referral_by_referee, get_or_create_patient_credits,
    get_reward_notifications, get_paid_referral_count,
)
from app.services.referral_service import (
    generate_referral_code, create_referral_from_webhook,
    advance_referral_to_qualified, advance_referral_to_paid,
)


def test_full_referral_flow():
    print("=== Referral Flow End-to-End Test ===\n")

    # Setup
    init_db()
    run_migrations()

    # 1. Create a referrer patient
    print("1. Creating referrer patient...")
    patient_id, was_new = upsert_patient({
        "email": "referrer-test@example.com",
        "first_name": "Sarah",
        "last_name": "Test",
        "phone": "615-555-4821",
        "last_visit_date": "2026-03-15",
    })
    print(f"   Patient ID: {patient_id}, new: {was_new}")
    assert patient_id > 0

    # 2. Generate referral code
    print("2. Generating referral code...")
    code = generate_referral_code(patient_id, first_name="Sarah", phone="615-555-4821")
    print(f"   Code: {code}")
    assert "sarah" in code or len(code) == 8  # Either name-based or fallback
    assert get_referral_code_by_patient(patient_id) is not None

    # 3. Simulate ContactCreate webhook with referral UTM
    print("3. Simulating ContactCreate with referral UTM...")
    ghl_contact_id = "test_contact_001"
    rid = create_referral_from_webhook(
        referral_code=code,
        ghl_contact_id=ghl_contact_id,
        referee_email="newlead@example.com",
        referee_name="Jane Lead",
    )
    print(f"   Referral ID: {rid}")
    assert rid is not None

    referral = get_referral_by_referee(ghl_contact_id)
    assert referral is not None
    assert referral["status"] == "pending"
    print(f"   Status: {referral['status']}")

    # 4. Simulate AppointmentCreate → qualified
    print("4. Simulating AppointmentCreate (qualification)...")
    ref = advance_referral_to_qualified(ghl_contact_id)
    assert ref is not None
    assert ref["status"] == "qualified"
    print(f"   Status: {ref['status']}")

    # 5. Simulate OpportunityWon → paid + reward check
    print("5. Simulating OpportunityWon (payment)...")
    ref = advance_referral_to_paid(ghl_contact_id)
    assert ref is not None
    assert ref["status"] == "paid"
    print(f"   Status: {ref['status']}")

    # 6. Check reward was created
    print("6. Checking reward notification...")
    paid_count = get_paid_referral_count(patient_id)
    print(f"   Paid referral count: {paid_count}")
    assert paid_count == 1

    # Check credits
    credits = get_or_create_patient_credits(patient_id)
    print(f"   Credit balance: ${credits['balance_cents'] / 100:.2f}")
    assert credits["balance_cents"] == 10000  # $100

    # Check reward notification draft
    notifications = get_reward_notifications(status="draft")
    matching = [n for n in notifications if n["patient_id"] == patient_id]
    print(f"   Reward notifications (draft): {len(matching)}")
    assert len(matching) >= 1
    print(f"   Reward tier: {matching[0]['reward_tier']}")
    print(f"   Subject: {matching[0]['subject']}")

    # 7. Idempotency check
    print("7. Testing idempotency...")
    event_id = insert_ghl_event({
        "ghl_event_id": "test_unique_123",
        "event_type": "ContactCreate",
        "contact_id": "test_contact_001",
        "payload": {"test": True},
    })
    assert event_id is not None
    duplicate_id = insert_ghl_event({
        "ghl_event_id": "test_unique_123",
        "event_type": "ContactCreate",
        "contact_id": "test_contact_001",
        "payload": {"test": True},
    })
    assert duplicate_id is None
    print("   Duplicate correctly rejected")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    test_full_referral_flow()
```

- [ ] **Step 2: Run the test**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 tests/test_referral_flow.py`

Expected: `=== ALL TESTS PASSED ===`

- [ ] **Step 3: Commit**

```bash
git add tests/test_referral_flow.py
git commit -m "feat(ghl): add end-to-end referral flow test script"
```

---

### Task 14: Create Feature Branch + Final Integration Verification

- [ ] **Step 1: Create the feature branch**

Note: If not already on a feature branch, create one from the current working branch:

```bash
git checkout -b feature/module-2-ghl-referrals
```

If the tasks above were committed on main, cherry-pick or rebase them onto this branch. If already on a feature branch, skip this step.

- [ ] **Step 2: Verify full app startup**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 -c "
from app.database import init_db, run_migrations
init_db()
run_migrations()
from app.main import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
print(f'Total routes: {len(routes)}')
for r in sorted(routes):
    if 'ghl' in r or 'referral' in r or '/r/' in r:
        print(f'  {r}')
"`

Expected: Shows new GHL/referral routes without errors

- [ ] **Step 3: Run the end-to-end test**

Run: `cd /Users/philipsmith/zerona-content-engine && source venv/bin/activate && python3 tests/test_referral_flow.py`

Expected: `=== ALL TESTS PASSED ===`

- [ ] **Step 4: Final commit with any fixups**

```bash
git add -A
git status
# Only commit if there are changes
git diff --cached --stat
```

---

## Self-Review Checklist

**Spec Coverage:**
| Requirement | Task |
|------------|------|
| GHL Webhook Receiver (POST /webhooks/ghl) | Task 7 |
| Signature verification | Task 3 |
| Handle 6 event types | Task 7 |
| ghl_events table + idempotency | Tasks 1, 4, 7 |
| GHL Contact Mirror (read-only) | Tasks 1, 4, 7 |
| Content Push to GHL (reward notifications only) | Task 6 |
| Referral code generation | Task 5 |
| Public /r/{code} redirect | Task 8 |
| referrals table + status transitions | Tasks 1, 4, 5 |
| Tiered rewards ($100/free session/15% VIP) | Task 5 |
| Reward notification review queue | Tasks 6, 10 |
| Referral leaderboard | Task 10 |
| Per-patient referral history | Task 10 |
| GHL event log viewer | Task 10 |
| GHL connection status in Settings | Task 12 |
| Manual referral entry | Tasks 9, 10 |
| Idempotency via ghl_event_id | Tasks 4, 7, 13 |
| Rate limiting on GHL API | Task 3 |
| Test harness (/dashboard/ghl-test) | Task 11 |
| patient_credits + transactions | Tasks 1, 4 |
| Credit redemption | Task 9 |
| Credit balance sync to GHL custom field | Task 6 |
| Migration file | Task 1 |
| Env vars in .env.example | Task 2 |
| End-to-end test | Task 13 |
| Feature branch | Task 14 |

**No placeholders found.** All tasks contain complete code.

**Type consistency verified:** Function names, parameters, and return types are consistent across tasks.

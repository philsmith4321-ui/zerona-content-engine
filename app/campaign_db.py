import json
from datetime import datetime, date, timedelta
from typing import Optional
from app.database import get_db, log_event


# ── Patients ──────────────────────────────────────────────

def compute_tier(last_visit_date: Optional[str]) -> str:
    if not last_visit_date:
        return "lapsed"
    try:
        visit = date.fromisoformat(last_visit_date)
    except (ValueError, TypeError):
        return "lapsed"
    months = (date.today() - visit).days / 30.44
    if months <= 6:
        return "active"
    elif months <= 12:
        return "semi_active"
    return "lapsed"


def upsert_patient(data: dict) -> tuple[int, bool]:
    """Insert or skip patient by email. Returns (patient_id, was_inserted)."""
    conn = get_db()
    existing = conn.execute("SELECT id FROM patients WHERE email = ?", (data["email"].lower().strip(),)).fetchone()
    if existing:
        conn.close()
        return existing["id"], False

    tier = compute_tier(data.get("last_visit_date"))
    tags = json.dumps(data.get("tags", []))
    now = datetime.now().isoformat()
    cursor = conn.execute(
        """INSERT INTO patients (email, first_name, last_name, phone, last_visit_date,
           gender, age, tags, tier, import_batch_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["email"].lower().strip(),
            data.get("first_name", ""),
            data.get("last_name", ""),
            data.get("phone", ""),
            data.get("last_visit_date"),
            data.get("gender", ""),
            data.get("age"),
            tags,
            tier,
            data.get("import_batch_id"),
            now, now,
        ),
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return pid, True


def get_patients(tier: Optional[str] = None, email_status: str = "valid",
                 search: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[dict]:
    conn = get_db()
    query = "SELECT * FROM patients WHERE email_status = ?"
    params = [email_status]
    if tier:
        query += " AND tier = ?"
        params.append(tier)
    if search:
        query += " AND (email LIKE ? OR first_name LIKE ? OR last_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])
    query += " ORDER BY last_name ASC, first_name ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_patient_count(tier: Optional[str] = None, email_status: str = "valid") -> int:
    conn = get_db()
    query = "SELECT COUNT(*) as cnt FROM patients WHERE email_status = ?"
    params = [email_status]
    if tier:
        query += " AND tier = ?"
        params.append(tier)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row["cnt"]


def get_patient_stats() -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as cnt FROM patients WHERE email_status = 'valid'").fetchone()["cnt"]
    active = conn.execute("SELECT COUNT(*) as cnt FROM patients WHERE tier = 'active' AND email_status = 'valid'").fetchone()["cnt"]
    semi = conn.execute("SELECT COUNT(*) as cnt FROM patients WHERE tier = 'semi_active' AND email_status = 'valid'").fetchone()["cnt"]
    lapsed = conn.execute("SELECT COUNT(*) as cnt FROM patients WHERE tier = 'lapsed' AND email_status = 'valid'").fetchone()["cnt"]
    invalid = conn.execute("SELECT COUNT(*) as cnt FROM patients WHERE email_status = 'invalid'").fetchone()["cnt"]
    unsubscribed = conn.execute("SELECT COUNT(*) as cnt FROM patients WHERE email_status = 'unsubscribed'").fetchone()["cnt"]
    conn.close()
    return {"total": total, "active": active, "semi_active": semi, "lapsed": lapsed,
            "invalid": invalid, "unsubscribed": unsubscribed}


def mark_patient_unsubscribed(email: str):
    conn = get_db()
    conn.execute(
        "UPDATE patients SET email_status = 'unsubscribed', mailgun_unsubscribed_at = ?, updated_at = ? WHERE email = ?",
        (datetime.now().isoformat(), datetime.now().isoformat(), email.lower().strip()),
    )
    conn.commit()
    conn.close()


def mark_patient_invalid(email: str):
    conn = get_db()
    conn.execute(
        "UPDATE patients SET email_status = 'invalid', updated_at = ? WHERE email = ?",
        (datetime.now().isoformat(), email.lower().strip()),
    )
    conn.commit()
    conn.close()


def recompute_all_tiers():
    conn = get_db()
    rows = conn.execute("SELECT id, last_visit_date FROM patients WHERE email_status = 'valid'").fetchall()
    for row in rows:
        tier = compute_tier(row["last_visit_date"])
        conn.execute("UPDATE patients SET tier = ?, updated_at = ? WHERE id = ?",
                      (tier, datetime.now().isoformat(), row["id"]))
    conn.commit()
    conn.close()


# ── Import History ────────────────────────────────────────

def insert_import_history(data: dict) -> int:
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO import_history (filename, column_mapping, total_rows, imported, duplicates_skipped, errors)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["filename"], json.dumps(data.get("column_mapping", {})),
         data.get("total_rows", 0), data.get("imported", 0),
         data.get("duplicates_skipped", 0), data.get("errors", 0)),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    return rid


def get_import_history(limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM import_history ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Segments ──────────────────────────────────────────────

def create_segment(name: str, segment_type: str, criteria: dict) -> int:
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO segments (name, segment_type, criteria) VALUES (?, ?, ?)",
        (name, segment_type, json.dumps(criteria)),
    )
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid


def get_segments() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM segments ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_segment(segment_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM segments WHERE id = ?", (segment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def resolve_segment(segment_id: int) -> list[dict]:
    """Return list of patients matching this segment's criteria."""
    seg = get_segment(segment_id)
    if not seg:
        return []
    criteria = json.loads(seg["criteria"]) if isinstance(seg["criteria"], str) else seg["criteria"]

    conn = get_db()
    query = "SELECT * FROM patients WHERE email_status = 'valid'"
    params = []

    if "tier" in criteria:
        query += " AND tier = ?"
        params.append(criteria["tier"])
    if "tiers" in criteria:
        placeholders = ",".join(["?"] * len(criteria["tiers"]))
        query += f" AND tier IN ({placeholders})"
        params.extend(criteria["tiers"])
    if "tags" in criteria:
        for tag in criteria["tags"]:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')
    if "gender" in criteria:
        query += " AND gender = ?"
        params.append(criteria["gender"])

    query += " ORDER BY last_name, first_name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_segment_count(segment_id: int) -> int:
    return len(resolve_segment(segment_id))


# ── Campaigns ─────────────────────────────────────────────

def create_campaign(data: dict) -> int:
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        """INSERT INTO campaigns (name, segment_id, subject, body_html, body_text,
           from_email, from_name, template_key, scheduled_at, status, warmup_schedule,
           created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["name"], data.get("segment_id"), data.get("subject", ""),
            data.get("body_html", ""), data.get("body_text", ""),
            data.get("from_email", ""), data.get("from_name", ""),
            data.get("template_key"), data.get("scheduled_at"),
            data.get("status", "draft"), data.get("warmup_schedule"),
            now, now,
        ),
    )
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid


def get_campaigns(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    conn = get_db()
    query = "SELECT c.*, s.name as segment_name FROM campaigns c LEFT JOIN segments s ON c.segment_id = s.id WHERE 1=1"
    params = []
    if status:
        query += " AND c.status = ?"
        params.append(status)
    query += " ORDER BY c.created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_campaign(campaign_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT c.*, s.name as segment_name FROM campaigns c LEFT JOIN segments s ON c.segment_id = s.id WHERE c.id = ?",
        (campaign_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_campaign(campaign_id: int, **kwargs):
    conn = get_db()
    sets = ["updated_at = ?"]
    params = [datetime.now().isoformat()]
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(val)
    params.append(campaign_id)
    conn.execute(f"UPDATE campaigns SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


# ── Campaign Sends ────────────────────────────────────────

def create_campaign_sends(campaign_id: int, patient_ids: list[int]):
    conn = get_db()
    for pid in patient_ids:
        conn.execute(
            "INSERT INTO campaign_sends (campaign_id, patient_id, status) VALUES (?, ?, 'queued')",
            (campaign_id, pid),
        )
    conn.commit()
    conn.close()


def get_campaign_sends(campaign_id: int, status: Optional[str] = None, limit: int = 500, offset: int = 0) -> list[dict]:
    conn = get_db()
    query = """SELECT cs.*, p.email, p.first_name, p.last_name
               FROM campaign_sends cs JOIN patients p ON cs.patient_id = p.id
               WHERE cs.campaign_id = ?"""
    params = [campaign_id]
    if status:
        query += " AND cs.status = ?"
        params.append(status)
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_campaign_send(send_id: int, **kwargs):
    conn = get_db()
    sets = []
    params = []
    for key, val in kwargs.items():
        sets.append(f"{key} = ?")
        params.append(val)
    params.append(send_id)
    conn.execute(f"UPDATE campaign_sends SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    conn.close()


# ── Campaign Events ───────────────────────────────────────

def insert_campaign_event(data: dict):
    conn = get_db()
    conn.execute(
        """INSERT INTO campaign_events (campaign_id, recipient_email, event_type, event_data,
           mailgun_message_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)""",
        (
            data.get("campaign_id"), data["recipient_email"], data["event_type"],
            json.dumps(data.get("event_data", {})),
            data.get("mailgun_message_id"), data.get("timestamp"),
        ),
    )
    conn.commit()
    conn.close()


def get_campaign_metrics(campaign_id: int) -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as cnt FROM campaign_sends WHERE campaign_id = ?", (campaign_id,)).fetchone()["cnt"]
    sent = conn.execute("SELECT COUNT(*) as cnt FROM campaign_sends WHERE campaign_id = ? AND status = 'sent'", (campaign_id,)).fetchone()["cnt"]
    failed = conn.execute("SELECT COUNT(*) as cnt FROM campaign_sends WHERE campaign_id = ? AND status = 'failed'", (campaign_id,)).fetchone()["cnt"]

    delivered = conn.execute("SELECT COUNT(DISTINCT recipient_email) as cnt FROM campaign_events WHERE campaign_id = ? AND event_type = 'delivered'", (campaign_id,)).fetchone()["cnt"]
    opened = conn.execute("SELECT COUNT(DISTINCT recipient_email) as cnt FROM campaign_events WHERE campaign_id = ? AND event_type = 'opened'", (campaign_id,)).fetchone()["cnt"]
    clicked = conn.execute("SELECT COUNT(DISTINCT recipient_email) as cnt FROM campaign_events WHERE campaign_id = ? AND event_type = 'clicked'", (campaign_id,)).fetchone()["cnt"]
    bounced = conn.execute("SELECT COUNT(DISTINCT recipient_email) as cnt FROM campaign_events WHERE campaign_id = ? AND event_type = 'bounced'", (campaign_id,)).fetchone()["cnt"]
    complained = conn.execute("SELECT COUNT(DISTINCT recipient_email) as cnt FROM campaign_events WHERE campaign_id = ? AND event_type = 'complained'", (campaign_id,)).fetchone()["cnt"]
    unsubscribed = conn.execute("SELECT COUNT(DISTINCT recipient_email) as cnt FROM campaign_events WHERE campaign_id = ? AND event_type = 'unsubscribed'", (campaign_id,)).fetchone()["cnt"]
    conn.close()

    return {
        "total": total, "sent": sent, "failed": failed,
        "delivered": delivered, "opened": opened, "clicked": clicked,
        "bounced": bounced, "complained": complained, "unsubscribed": unsubscribed,
        "open_rate": round(opened / max(delivered, 1) * 100, 1),
        "click_rate": round(clicked / max(delivered, 1) * 100, 1),
        "bounce_rate": round(bounced / max(total, 1) * 100, 1),
    }


def find_campaign_by_message_id(message_id: str) -> Optional[int]:
    """Look up campaign_id from a Mailgun message ID."""
    conn = get_db()
    row = conn.execute(
        "SELECT campaign_id FROM campaign_sends WHERE mailgun_message_id = ? LIMIT 1",
        (message_id,),
    ).fetchone()
    conn.close()
    return row["campaign_id"] if row else None


def get_soft_bounce_count(email: str, campaign_id: int) -> int:
    conn = get_db()
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM campaign_events
           WHERE recipient_email = ? AND campaign_id = ? AND event_type = 'bounced'
           AND json_extract(event_data, '$.severity') = 'temporary'""",
        (email, campaign_id),
    ).fetchone()
    conn.close()
    return row["cnt"]

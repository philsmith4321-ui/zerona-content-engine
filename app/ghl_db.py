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

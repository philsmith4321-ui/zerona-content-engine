import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

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


def log_event(event_type: str, message: str, details: Optional[dict] = None):
    conn = get_db()
    conn.execute(
        "INSERT INTO system_log (event_type, message, details) VALUES (?, ?, ?)",
        (event_type, message, json.dumps(details) if details else None),
    )
    conn.commit()
    conn.close()


def get_content_pieces(status: Optional[str] = None, content_type: Optional[str] = None,
                       category: Optional[str] = None, scheduled_date: Optional[str] = None,
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


def get_logs(event_type: Optional[str] = None, limit: int = 100) -> list[dict]:
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

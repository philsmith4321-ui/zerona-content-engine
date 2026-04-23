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

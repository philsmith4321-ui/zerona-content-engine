import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Optional

import requests

from app.config import settings
from app.database import log_event


MAILGUN_API_BASE = "https://api.mailgun.net/v3"


def _auth():
    return ("api", settings.mailgun_api_key)


def _domain_url(path: str = "") -> str:
    return f"{MAILGUN_API_BASE}/{settings.mailgun_domain}{path}"


def is_configured() -> bool:
    return bool(settings.mailgun_api_key and settings.mailgun_domain)


def test_connection() -> dict:
    if not is_configured():
        return {"connected": False, "error": "Mailgun not configured"}
    try:
        resp = requests.get(f"{MAILGUN_API_BASE}/domains/{settings.mailgun_domain}", auth=_auth(), timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            domain = data.get("domain", {})
            return {
                "connected": True,
                "domain": domain.get("name"),
                "state": domain.get("state"),
                "type": domain.get("type"),
            }
        return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


def send_single(to_email: str, subject: str, html: str, text: str = "",
                from_email: Optional[str] = None, from_name: Optional[str] = None,
                tags: Optional[list[str]] = None, campaign_id: Optional[int] = None) -> dict:
    """Send a single email via Mailgun. Returns {success, message_id} or {success, error}."""
    sender = f"{from_name or settings.mailgun_from_name} <{from_email or settings.mailgun_from_email}>"
    data = {
        "from": sender,
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    if text:
        data["text"] = text
    if tags:
        data["o:tag"] = tags
    if campaign_id:
        data["v:campaign_id"] = str(campaign_id)

    try:
        resp = requests.post(_domain_url("/messages"), auth=_auth(), data=data, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            return {"success": True, "message_id": result.get("id", "").strip("<>")}
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_batch(recipients: list[dict], subject: str, html: str, text: str = "",
               from_email: Optional[str] = None, from_name: Optional[str] = None,
               campaign_id: Optional[int] = None) -> list[dict]:
    """Send to multiple recipients using Mailgun's recipient-variables for merge tags.

    recipients: [{"email": "...", "first_name": "...", "last_visit_date": "...", "send_id": 123}, ...]
    Returns list of {email, success, message_id, error, send_id}
    """
    results = []
    # Mailgun batch limit is 1000 per API call
    batch_size = 1000
    sender = f"{from_name or settings.mailgun_from_name} <{from_email or settings.mailgun_from_email}>"

    for i in range(0, len(recipients), batch_size):
        batch = recipients[i : i + batch_size]
        to_list = [r["email"] for r in batch]
        recipient_vars = {}
        for r in batch:
            recipient_vars[r["email"]] = {
                "first_name": r.get("first_name", ""),
                "last_visit_date": r.get("last_visit_date", ""),
            }

        data = {
            "from": sender,
            "to": to_list,
            "subject": subject,
            "html": html,
            "recipient-variables": json.dumps(recipient_vars),
        }
        if text:
            data["text"] = text
        if campaign_id:
            data["v:campaign_id"] = str(campaign_id)
            data["o:tag"] = [f"campaign_{campaign_id}"]

        try:
            resp = requests.post(_domain_url("/messages"), auth=_auth(), data=data, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                msg_id = result.get("id", "").strip("<>")
                for r in batch:
                    results.append({"email": r["email"], "success": True, "message_id": msg_id, "send_id": r.get("send_id")})
            else:
                for r in batch:
                    results.append({"email": r["email"], "success": False, "error": f"HTTP {resp.status_code}", "send_id": r.get("send_id")})
        except Exception as e:
            for r in batch:
                results.append({"email": r["email"], "success": False, "error": str(e), "send_id": r.get("send_id")})

        # Rate limit: brief pause between batches
        if i + batch_size < len(recipients):
            time.sleep(1)

    return results


def check_unsubscribes(emails: list[str]) -> set[str]:
    """Check Mailgun's suppression list. Returns set of unsubscribed emails."""
    unsubscribed = set()
    if not is_configured():
        return unsubscribed

    # Mailgun suppression API paginates; check in batches
    for email in emails:
        try:
            resp = requests.get(
                _domain_url(f"/unsubscribes/{email}"),
                auth=_auth(), timeout=10,
            )
            if resp.status_code == 200:
                unsubscribed.add(email)
        except Exception:
            pass  # If we can't check, allow the send
    return unsubscribed


def check_unsubscribes_bulk(emails: list[str]) -> set[str]:
    """Bulk check against Mailgun's unsubscribe list. More efficient for large lists."""
    unsubscribed = set()
    if not is_configured() or not emails:
        return unsubscribed

    try:
        page_url = _domain_url("/unsubscribes")
        while page_url:
            resp = requests.get(page_url, auth=_auth(), params={"limit": 1000}, timeout=30)
            if resp.status_code != 200:
                break
            data = resp.json()
            for item in data.get("items", []):
                addr = item.get("address", "").lower()
                if addr in {e.lower() for e in emails}:
                    unsubscribed.add(addr)
            paging = data.get("paging", {})
            next_url = paging.get("next")
            if next_url and next_url != page_url:
                page_url = next_url
            else:
                break
    except Exception as e:
        log_event("warning", f"Mailgun unsubscribe bulk check failed: {e}")

    return unsubscribed


def verify_webhook_signature(token: str, timestamp: str, signature: str) -> bool:
    """Verify Mailgun webhook signature using HMAC-SHA256."""
    signing_key = settings.mailgun_webhook_signing_key
    if not signing_key:
        return False
    hmac_digest = hmac.new(
        key=signing_key.encode("utf-8"),
        msg=f"{timestamp}{token}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(str(signature), hmac_digest)


def get_warmup_schedule(total_recipients: int) -> list[dict]:
    """Generate a staggered warmup schedule for a new domain."""
    tiers = [50, 100, 250, 500]
    schedule = []
    remaining = total_recipients
    day = 1
    for tier_size in tiers:
        if remaining <= 0:
            break
        batch = min(tier_size, remaining)
        schedule.append({"day": day, "count": batch})
        remaining -= batch
        day += 1
    if remaining > 0:
        schedule.append({"day": day, "count": remaining})
    return schedule

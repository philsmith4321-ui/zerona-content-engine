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
    from app.database import get_db

    # Get patient info
    conn = get_db()
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

    patient_id = notif["patient_id"]

    # Try to sync credit balance to GHL if the patient has a linked GHL contact
    credits = get_or_create_patient_credits(patient_id)
    balance_dollars = credits["balance_cents"] / 100

    # Log the push
    push_result = {"method": "logged", "notification_id": notification_id}

    # If we have a GHL credit balance field configured, try to update it
    if settings.ghl_credit_balance_field_id:
        from app.database import get_db
        conn = get_db()
        patient = conn.execute("SELECT email FROM patients WHERE id = ?", (patient_id,)).fetchone()
        ghl_contact = None
        if patient:
            ghl_contact = conn.execute(
                "SELECT ghl_contact_id FROM ghl_contacts WHERE email = ?", (patient["email"],)
            ).fetchone()
        conn.close()

        if ghl_contact:
            ghl_cid = ghl_contact["ghl_contact_id"]
            update_contact_custom_field(ghl_cid, settings.ghl_credit_balance_field_id, str(balance_dollars))
            note_body = f"REFERRAL REWARD: {notif['reward_description']}\n\n{notif['body']}"
            push_note_to_contact(ghl_cid, note_body)
            push_result["method"] = "ghl_api"
            push_result["ghl_contact_id"] = ghl_cid

    now = datetime.now().isoformat()
    update_reward_notification(notification_id, status="pushed", pushed_at=now,
                                ghl_push_result=json.dumps(push_result))
    log_event("reward", f"Reward notification {notification_id} pushed: {push_result.get('method')}")
    return {"success": True, **push_result}

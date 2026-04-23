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

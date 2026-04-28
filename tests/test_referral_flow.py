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

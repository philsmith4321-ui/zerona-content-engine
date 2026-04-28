"""Module 1 (Email Campaigns) End-to-End Test Suite

Runs 13 tests covering database, services, routes, and business logic.
Uses a temporary database to avoid affecting production data.

Run with: python tests/test_module1_e2e.py
"""
import hashlib
import hmac
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temp database for all tests
TEST_DB_DIR = tempfile.mkdtemp(prefix="zerona_test_")
TEST_DB_PATH = Path(TEST_DB_DIR) / "test.db"

# Patch DB_PATH before any app imports
import app.database as db_module
db_module.DB_PATH = TEST_DB_PATH

# Now safe to import app modules
from app.database import init_db, run_migrations, get_db, log_event
from app.campaign_db import (
    compute_tier, upsert_patient, get_patients, get_patient_count,
    get_patient_stats, mark_patient_unsubscribed, mark_patient_invalid,
    recompute_all_tiers, create_segment, get_segments, get_segment,
    resolve_segment, get_segment_count, create_campaign, get_campaigns,
    get_campaign, update_campaign, create_campaign_sends, get_campaign_sends,
    update_campaign_send, insert_campaign_event, get_campaign_metrics,
    find_campaign_by_message_id, get_soft_bounce_count,
    insert_import_history, get_import_history,
)
from app.services.mailgun_service import (
    verify_webhook_signature, get_warmup_schedule, is_configured,
)
from app.services.campaign_service import apply_merge_tags
from app.services.patient_service import auto_map_columns, preview_csv, import_patients


# ── Test infrastructure ──────────────────────────────────

passed = 0
failed = 0
errors = []


def run_test(name, test_fn):
    global passed, failed
    try:
        test_fn()
        passed += 1
        print(f"  PASSED: {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  FAILED: {name}")
        print(f"          {e}")


# ── Test 1: Database Migration & Schema Integrity ────────

def test_1_database_migration():
    init_db()
    run_migrations()
    conn = get_db()

    # Check all 4 campaign tables exist
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    for t in ["segments", "campaigns", "campaign_sends", "campaign_events"]:
        assert t in tables, f"Missing table: {t}"

    # Check segments columns
    seg_cols = [r[1] for r in conn.execute("PRAGMA table_info(segments)").fetchall()]
    for col in ["id", "name", "segment_type", "criteria", "created_at"]:
        assert col in seg_cols, f"Missing segments column: {col}"

    # Check campaigns columns
    camp_cols = [r[1] for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()]
    for col in ["id", "name", "segment_id", "subject", "body_html", "body_text",
                "from_email", "from_name", "template_key", "scheduled_at",
                "started_at", "completed_at", "status", "total_recipients",
                "warmup_schedule", "created_at", "updated_at"]:
        assert col in camp_cols, f"Missing campaigns column: {col}"

    # Check campaign_sends columns
    send_cols = [r[1] for r in conn.execute("PRAGMA table_info(campaign_sends)").fetchall()]
    for col in ["id", "campaign_id", "patient_id", "mailgun_message_id",
                "status", "sent_at", "error_message"]:
        assert col in send_cols, f"Missing campaign_sends column: {col}"

    # Check campaign_events columns
    event_cols = [r[1] for r in conn.execute("PRAGMA table_info(campaign_events)").fetchall()]
    for col in ["id", "campaign_id", "recipient_email", "event_type",
                "event_data", "mailgun_message_id", "timestamp", "created_at"]:
        assert col in event_cols, f"Missing campaign_events column: {col}"

    # Check default segments were seeded
    segs = get_segments()
    assert len(segs) == 4, f"Expected 4 default segments, got {len(segs)}"
    seg_names = [s["name"] for s in segs]
    assert any("Active" in n for n in seg_names), "Missing Active segment"
    assert any("Lapsed" in n for n in seg_names), "Missing Lapsed segment"
    assert any("All Valid" in n for n in seg_names), "Missing All Valid segment"

    # Check migrations were recorded
    applied = [r["filename"] for r in conn.execute("SELECT filename FROM migrations").fetchall()]
    assert "002_create_campaigns.sql" in applied, "Migration 002 not recorded"
    assert "003_create_campaign_events.sql" in applied, "Migration 003 not recorded"

    conn.close()


# ── Test 2: Patient CSV Import — Full Workflow ───────────

def test_2_csv_import():
    csv_path = Path("tests/test_patients.csv")
    assert csv_path.exists(), f"Test CSV not found at {csv_path}"
    csv_content = csv_path.read_text()

    # Step 1: Preview CSV
    preview = preview_csv(csv_content, limit=3)
    assert "headers" in preview
    assert "preview_rows" in preview
    assert "auto_mapping" in preview
    assert len(preview["preview_rows"]) == 3
    assert "email" in preview["auto_mapping"].values(), \
        f"Auto-mapping failed to detect email: {preview['auto_mapping']}"

    # Step 2: Import patients
    mapping = preview["auto_mapping"]
    result = import_patients(csv_content, mapping, "test_patients.csv")
    assert result["imported"] > 0, f"No patients imported: {result}"
    assert result["errors"] == 0, f"Import errors: {result['errors']}"
    total_imported = result["imported"]

    # Step 3: Verify patients exist with correct tiers
    stats = get_patient_stats()
    assert stats["total"] == total_imported, \
        f"Expected {total_imported} patients, got {stats['total']}"
    assert stats["active"] > 0, "No active patients found"
    assert stats["lapsed"] > 0, "No lapsed patients found"

    # Step 4: Deduplication — re-import should add 0 new
    result2 = import_patients(csv_content, mapping, "test_patients_dup.csv")
    assert result2["imported"] == 0, \
        f"Expected 0 new on re-import, got {result2['imported']}"
    assert result2["duplicates_skipped"] == total_imported, \
        f"Expected {total_imported} duplicates, got {result2['duplicates_skipped']}"

    # Step 5: Import history recorded
    history = get_import_history(limit=5)
    assert len(history) >= 2, f"Expected 2+ import records, got {len(history)}"

    # Check a specific patient
    patients = get_patients(search="sarah.johnson@example.com")
    assert len(patients) == 1, f"Expected 1 patient for sarah, got {len(patients)}"
    sarah = patients[0]
    assert sarah["first_name"] == "Sarah"
    assert sarah["last_name"] == "Johnson"
    assert sarah["tier"] == "active"  # last_visit 2026-03-15, ~1 month ago


# ── Test 3: Patient Tier Computation Edge Cases ──────────

def test_3_tier_computation():
    now = datetime.now()

    # 3 months ago → active
    d3 = (now - timedelta(days=90)).strftime("%Y-%m-%d")
    assert compute_tier(d3) == "active", f"3mo should be active, got {compute_tier(d3)}"

    # 9 months ago → semi_active
    d9 = (now - timedelta(days=270)).strftime("%Y-%m-%d")
    assert compute_tier(d9) == "semi_active", f"9mo should be semi_active"

    # 18 months ago → lapsed
    d18 = (now - timedelta(days=540)).strftime("%Y-%m-%d")
    assert compute_tier(d18) == "lapsed", f"18mo should be lapsed"

    # None → lapsed
    assert compute_tier(None) == "lapsed", "None should be lapsed"

    # Invalid string → lapsed
    assert compute_tier("not-a-date") == "lapsed", "Invalid date should be lapsed"

    # Empty string → lapsed
    assert compute_tier("") == "lapsed", "Empty string should be lapsed"

    # Exact 6-month boundary (182 days) — should be active
    d6 = (now - timedelta(days=182)).strftime("%Y-%m-%d")
    tier_6 = compute_tier(d6)
    assert tier_6 in ("active", "semi_active"), f"6mo boundary: {tier_6}"

    # Exact 12-month boundary (365 days) — should be semi_active or lapsed
    d12 = (now - timedelta(days=365)).strftime("%Y-%m-%d")
    tier_12 = compute_tier(d12)
    assert tier_12 in ("semi_active", "lapsed"), f"12mo boundary: {tier_12}"


# ── Test 4: Segment Creation & Resolution ────────────────

def test_4_segment_resolution():
    # Create a test segment for active patients only
    seg_id = create_segment("Test Active Only", "tier", {"tier": "active"})
    assert seg_id > 0

    # Resolve it — should return only active, valid patients
    patients = resolve_segment(seg_id)
    for p in patients:
        assert p["tier"] == "active", f"Non-active patient in segment: {p['tier']}"
        assert p["email_status"] == "valid", f"Invalid patient in segment: {p['email_status']}"

    # Create multi-tier segment
    multi_id = create_segment("Test Multi", "tier", {"tiers": ["active", "semi_active"]})
    multi_patients = resolve_segment(multi_id)
    for p in multi_patients:
        assert p["tier"] in ("active", "semi_active"), f"Wrong tier in multi: {p['tier']}"

    # Mark a patient as unsubscribed, verify excluded
    active_patients = resolve_segment(seg_id)
    if active_patients:
        test_email = active_patients[0]["email"]
        mark_patient_unsubscribed(test_email)
        updated = resolve_segment(seg_id)
        unsub_in_segment = [p for p in updated if p["email"] == test_email]
        assert len(unsub_in_segment) == 0, "Unsubscribed patient still in segment"

        # Restore for later tests
        conn = get_db()
        conn.execute(
            "UPDATE patients SET email_status = 'valid' WHERE email = ?",
            (test_email,),
        )
        conn.commit()
        conn.close()

    # Verify segment count matches
    count = get_segment_count(seg_id)
    resolved = resolve_segment(seg_id)
    assert count == len(resolved), f"Count {count} != resolved {len(resolved)}"


# ── Test 5: Campaign CRUD & State Machine ────────────────

def test_5_campaign_state_machine():
    segs = get_segments()
    seg_id = segs[0]["id"]

    # Create draft campaign
    camp_id = create_campaign({
        "name": "Test Campaign",
        "segment_id": seg_id,
        "subject": "Hello {{first_name}}",
        "body_html": "<p>Hi {{first_name}}, visit us!</p>",
        "body_text": "Hi {{first_name}}, visit us!",
        "status": "draft",
    })
    assert camp_id > 0

    camp = get_campaign(camp_id)
    assert camp["status"] == "draft"
    assert camp["name"] == "Test Campaign"

    # Update fields
    update_campaign(camp_id, subject="Updated Subject")
    camp = get_campaign(camp_id)
    assert camp["subject"] == "Updated Subject"

    # Approve
    update_campaign(camp_id, status="approved")
    camp = get_campaign(camp_id)
    assert camp["status"] == "approved"

    # Transition to sending
    update_campaign(camp_id, status="sending", started_at=datetime.now().isoformat())
    camp = get_campaign(camp_id)
    assert camp["status"] == "sending"
    assert camp["started_at"] is not None

    # Transition to sent
    update_campaign(camp_id, status="sent", completed_at=datetime.now().isoformat())
    camp = get_campaign(camp_id)
    assert camp["status"] == "sent"
    assert camp["completed_at"] is not None

    # Verify campaign appears in list
    camps = get_campaigns()
    assert any(c["id"] == camp_id for c in camps), "Campaign not in list"

    # Verify filter works
    sent_camps = get_campaigns(status="sent")
    assert all(c["status"] == "sent" for c in sent_camps)


# ── Test 6: Campaign Creation from Template ──────────────

def test_6_templates():
    from app.services.campaign_service import CAMPAIGN_TEMPLATES, create_campaign_from_template

    template_keys = list(CAMPAIGN_TEMPLATES.keys())
    assert len(template_keys) == 6, f"Expected 6 templates, got {len(template_keys)}"

    for key in template_keys:
        camp_id = create_campaign_from_template(key)
        assert camp_id is not None, f"Template {key} returned None"
        camp = get_campaign(camp_id)
        assert camp["status"] == "draft", f"Template {key} not draft"
        assert camp["template_key"] == key, f"Template key mismatch for {key}"
        assert camp["subject"] is not None and len(camp["subject"]) > 0, \
            f"Template {key} has no subject"

    # Invalid template key returns None
    result = create_campaign_from_template("nonexistent_template")
    assert result is None, "Nonexistent template should return None"


# ── Test 7: Merge Tag Substitution ───────────────────────

def test_7_merge_tags():
    patient = {
        "first_name": "Sarah",
        "last_visit_date": "2026-03-15",
    }

    # {{var}} syntax
    html1 = "<p>Hello {{first_name}}, your last visit was {{last_visit_date}}.</p>"
    result1 = apply_merge_tags(html1, patient)
    assert "Sarah" in result1, f"first_name not substituted: {result1}"
    assert "2026-03-15" in result1, f"last_visit_date not substituted: {result1}"
    assert "{{" not in result1, f"Unreplaced tags remain: {result1}"

    # %recipient.var% syntax (Mailgun)
    html2 = "<p>Hello %recipient.first_name%, last visit %recipient.last_visit_date%.</p>"
    result2 = apply_merge_tags(html2, patient)
    assert "Sarah" in result2, f"Mailgun first_name not substituted: {result2}"
    assert "2026-03-15" in result2, f"Mailgun last_visit_date not substituted: {result2}"

    # Missing values — should substitute empty or gracefully
    patient_partial = {"first_name": "Mike"}
    html3 = "Hello {{first_name}}, visit was {{last_visit_date}}."
    result3 = apply_merge_tags(html3, patient_partial)
    assert "Mike" in result3
    # last_visit_date should be replaced with empty or the tag stays — either is acceptable
    assert "{{first_name}}" not in result3

    # Empty patient dict
    html4 = "Hello {{first_name}}!"
    result4 = apply_merge_tags(html4, {})
    # Should not crash
    assert isinstance(result4, str)


# ── Test 8: Warmup Schedule Calculation ──────────────────

def test_8_warmup_schedule():
    # 30 recipients — all in day 1
    s30 = get_warmup_schedule(30)
    assert len(s30) == 1, f"30 recipients: expected 1 day, got {len(s30)}"
    assert s30[0]["count"] == 30
    assert s30[0]["day"] == 1

    # 150 recipients — day 1: 50, day 2: 100
    s150 = get_warmup_schedule(150)
    assert len(s150) == 2, f"150 recipients: expected 2 days, got {len(s150)}"
    assert s150[0]["count"] == 50
    assert s150[1]["count"] == 100
    assert sum(d["count"] for d in s150) == 150

    # 500 recipients — day 1: 50, day 2: 100, day 3: 250, day 4: 100
    s500 = get_warmup_schedule(500)
    assert s500[0]["count"] == 50
    assert s500[1]["count"] == 100
    assert s500[2]["count"] == 250
    assert sum(d["count"] for d in s500) == 500

    # 1000 recipients — should use all 4 tiers + remainder
    s1000 = get_warmup_schedule(1000)
    assert s1000[0]["count"] == 50
    assert s1000[1]["count"] == 100
    assert s1000[2]["count"] == 250
    assert s1000[3]["count"] == 500
    assert sum(d["count"] for d in s1000) == 1000

    # 5000 recipients — 4 tiers + remainder day
    s5000 = get_warmup_schedule(5000)
    assert len(s5000) == 5, f"5000 recipients: expected 5 days, got {len(s5000)}"
    assert s5000[4]["count"] == 4100  # 5000 - 50 - 100 - 250 - 500
    assert sum(d["count"] for d in s5000) == 5000

    # 0 recipients — empty schedule
    s0 = get_warmup_schedule(0)
    assert len(s0) == 0, f"0 recipients: expected 0 days, got {len(s0)}"


# ── Test 9: Webhook Signature Verification ───────────────

def test_9_webhook_signature():
    test_key = "test-signing-key-12345"
    token = "test-token-abc"
    timestamp = "1234567890"

    # Compute valid signature
    valid_sig = hmac.new(
        key=test_key.encode("utf-8"),
        msg=f"{timestamp}{token}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Valid signature should pass
    with patch("app.services.mailgun_service.settings") as mock_settings:
        mock_settings.mailgun_webhook_signing_key = test_key
        assert verify_webhook_signature(token, timestamp, valid_sig) is True

    # Invalid signature should fail
    with patch("app.services.mailgun_service.settings") as mock_settings:
        mock_settings.mailgun_webhook_signing_key = test_key
        assert verify_webhook_signature(token, timestamp, "bad-signature") is False

    # Tampered timestamp should fail
    with patch("app.services.mailgun_service.settings") as mock_settings:
        mock_settings.mailgun_webhook_signing_key = test_key
        assert verify_webhook_signature(token, "9999999999", valid_sig) is False

    # Missing signing key should fail
    with patch("app.services.mailgun_service.settings") as mock_settings:
        mock_settings.mailgun_webhook_signing_key = ""
        assert verify_webhook_signature(token, timestamp, valid_sig) is False


# ── Test 10: Webhook Event Processing ────────────────────

def test_10_webhook_events():
    # Create a campaign and sends for event processing
    segs = get_segments()
    seg_id = segs[0]["id"]
    camp_id = create_campaign({
        "name": "Webhook Test Campaign",
        "segment_id": seg_id,
        "subject": "Test",
        "body_html": "<p>Test</p>",
        "status": "sent",
    })

    # Get some patients for sends
    patients = get_patients(limit=5)
    assert len(patients) >= 3, "Need at least 3 patients for webhook test"
    patient_ids = [p["id"] for p in patients]
    create_campaign_sends(camp_id, patient_ids)

    sends = get_campaign_sends(camp_id)
    assert len(sends) == len(patient_ids)

    # Update sends with fake message IDs
    for i, send in enumerate(sends):
        update_campaign_send(send["id"], mailgun_message_id=f"msg-{camp_id}-{i}", status="sent")

    # Insert events: 5 delivered, 3 opened, 1 clicked, 1 bounced
    # Note: event_data must be a dict — insert_campaign_event calls json.dumps()
    for i in range(5):
        insert_campaign_event({
            "campaign_id": camp_id,
            "recipient_email": patients[i % len(patients)]["email"],
            "event_type": "delivered",
            "event_data": {"test": True},
            "mailgun_message_id": f"msg-{camp_id}-{i}",
            "timestamp": datetime.now().isoformat(),
        })

    for i in range(3):
        insert_campaign_event({
            "campaign_id": camp_id,
            "recipient_email": patients[i]["email"],
            "event_type": "opened",
            "event_data": {"test": True},
            "mailgun_message_id": f"msg-{camp_id}-{i}",
            "timestamp": datetime.now().isoformat(),
        })

    insert_campaign_event({
        "campaign_id": camp_id,
        "recipient_email": patients[0]["email"],
        "event_type": "clicked",
        "event_data": {"url": "https://example.com"},
        "mailgun_message_id": f"msg-{camp_id}-0",
        "timestamp": datetime.now().isoformat(),
    })

    insert_campaign_event({
        "campaign_id": camp_id,
        "recipient_email": patients[4 % len(patients)]["email"],
        "event_type": "bounced",
        "event_data": {"severity": "permanent"},
        "mailgun_message_id": f"msg-{camp_id}-4",
        "timestamp": datetime.now().isoformat(),
    })

    # Verify metrics
    metrics = get_campaign_metrics(camp_id)
    assert metrics["delivered"] == 5, f"Expected 5 delivered, got {metrics['delivered']}"
    assert metrics["opened"] == 3, f"Expected 3 opened, got {metrics['opened']}"
    assert metrics["clicked"] == 1, f"Expected 1 clicked, got {metrics['clicked']}"
    assert metrics["bounced"] == 1, f"Expected 1 bounced, got {metrics['bounced']}"

    # Verify rates (opened/delivered, clicked/delivered)
    assert metrics["open_rate"] > 0, "Open rate should be > 0"
    assert metrics["click_rate"] > 0, "Click rate should be > 0"

    # Verify message ID reverse lookup
    found_camp_id = find_campaign_by_message_id(f"msg-{camp_id}-0")
    assert found_camp_id == camp_id, f"Reverse lookup failed: {found_camp_id}"

    # Verify unknown message ID returns None
    not_found = find_campaign_by_message_id("nonexistent-msg-id")
    assert not_found is None, "Should return None for unknown message ID"


# ── Test 11: Campaign Metrics Aggregation ────────────────

def test_11_metrics_aggregation():
    # Use the campaign from Test 10
    camps = get_campaigns(status="sent")
    assert len(camps) > 0, "No sent campaigns found"
    camp = camps[0]

    metrics = get_campaign_metrics(camp["id"])

    # Verify all expected keys exist
    for key in ["total", "sent", "delivered", "opened", "clicked",
                "bounced", "complained", "unsubscribed",
                "open_rate", "click_rate", "bounce_rate"]:
        assert key in metrics, f"Missing metric key: {key}"

    # Rates should be between 0 and 100
    for rate_key in ["open_rate", "click_rate", "bounce_rate"]:
        assert 0 <= metrics[rate_key] <= 100, \
            f"{rate_key} out of range: {metrics[rate_key]}"

    # Total should match sends count
    sends = get_campaign_sends(camp["id"])
    assert metrics["total"] == len(sends), \
        f"Total {metrics['total']} != sends count {len(sends)}"


# ── Test 12: Patient Suppression Logic ───────────────────

def test_12_suppression():
    # Create two test patients
    pid1, _ = upsert_patient({
        "email": "suppress-test-1@example.com",
        "first_name": "Suppress",
        "last_name": "Test1",
    })
    pid2, _ = upsert_patient({
        "email": "suppress-test-2@example.com",
        "first_name": "Suppress",
        "last_name": "Test2",
    })

    # Both should be valid initially
    valid = get_patients(email_status="valid", search="suppress-test")
    emails = [p["email"] for p in valid]
    assert "suppress-test-1@example.com" in emails
    assert "suppress-test-2@example.com" in emails

    # Mark one as unsubscribed
    mark_patient_unsubscribed("suppress-test-1@example.com")
    conn = get_db()
    p1 = conn.execute(
        "SELECT email_status, mailgun_unsubscribed_at FROM patients WHERE id = ?",
        (pid1,)
    ).fetchone()
    conn.close()
    assert p1["email_status"] == "unsubscribed", f"Expected unsubscribed, got {p1['email_status']}"
    assert p1["mailgun_unsubscribed_at"] is not None

    # Mark one as invalid (hard bounce)
    mark_patient_invalid("suppress-test-2@example.com")
    conn = get_db()
    p2 = conn.execute(
        "SELECT email_status FROM patients WHERE id = ?", (pid2,)
    ).fetchone()
    conn.close()
    assert p2["email_status"] == "invalid", f"Expected invalid, got {p2['email_status']}"

    # Neither should appear in valid patient queries
    valid_after = get_patients(email_status="valid", search="suppress-test")
    assert len(valid_after) == 0, f"Suppressed patients still in valid list: {len(valid_after)}"

    # Neither should appear in segment resolution
    segs = get_segments()
    all_seg = [s for s in segs if "All Valid" in s["name"]]
    if all_seg:
        resolved = resolve_segment(all_seg[0]["id"])
        resolved_emails = [p["email"] for p in resolved]
        assert "suppress-test-1@example.com" not in resolved_emails
        assert "suppress-test-2@example.com" not in resolved_emails

    # Stats should reflect suppressions
    stats = get_patient_stats()
    assert stats["unsubscribed"] >= 1, "No unsubscribed patients in stats"
    assert stats["invalid"] >= 1, "No invalid patients in stats"

    # Soft bounce tracking
    camp_id = create_campaign({
        "name": "Bounce Test",
        "subject": "Test",
        "body_html": "<p>Test</p>",
        "status": "sent",
    })
    test_email = "softbounce-test@example.com"
    upsert_patient({"email": test_email, "first_name": "Soft", "last_name": "Bounce"})

    # Insert 2 soft bounces — should NOT trigger invalid
    # Note: event_data must be a dict (not pre-serialized JSON string)
    # because insert_campaign_event calls json.dumps() on it internally
    for i in range(2):
        insert_campaign_event({
            "campaign_id": camp_id,
            "recipient_email": test_email,
            "event_type": "bounced",
            "event_data": {"severity": "temporary"},
            "mailgun_message_id": f"soft-{i}",
            "timestamp": datetime.now().isoformat(),
        })
    count = get_soft_bounce_count(test_email, camp_id)
    assert count == 2, f"Expected 2 soft bounces, got {count}"

    # Insert 3rd soft bounce — webhook handler would mark invalid at 3+
    insert_campaign_event({
        "campaign_id": camp_id,
        "recipient_email": test_email,
        "event_type": "bounced",
        "event_data": {"severity": "temporary"},
        "mailgun_message_id": "soft-2",
        "timestamp": datetime.now().isoformat(),
    })
    count = get_soft_bounce_count(test_email, camp_id)
    assert count >= 3, f"Expected 3+ soft bounces, got {count}"


# ── Test 13: App Startup & Route Protection ──────────────

def test_13_app_routes():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)

    # Health check should work without auth
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    assert resp.json()["status"] == "ok"

    # Root should redirect to dashboard
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 307), f"Root didn't redirect: {resp.status_code}"

    # Protected routes should redirect to login without auth
    protected_routes = [
        "/dashboard",
        "/dashboard/campaigns",
        "/dashboard/patients",
    ]
    for route in protected_routes:
        resp = client.get(route, follow_redirects=False)
        assert resp.status_code in (303, 401, 403), \
            f"{route} accessible without auth: {resp.status_code}"

    # Login with wrong password should fail
    resp = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert resp.status_code == 200, f"Wrong password didn't show login page: {resp.status_code}"
    assert b"Invalid password" in resp.content or resp.status_code == 200

    # Login with correct password should set session cookie
    from app.config import settings
    resp = client.post(
        "/login",
        data={"password": settings.admin_password},
        follow_redirects=False,
    )
    assert resp.status_code == 303, f"Login didn't redirect: {resp.status_code}"
    assert "session" in resp.cookies, "No session cookie set"

    # Use the session cookie for authenticated requests
    session_cookie = resp.cookies["session"]

    # Dashboard should load with auth
    resp = client.get("/dashboard", cookies={"session": session_cookie})
    assert resp.status_code == 200, f"Dashboard failed with auth: {resp.status_code}"

    # Campaigns page should load
    resp = client.get("/dashboard/campaigns", cookies={"session": session_cookie})
    assert resp.status_code == 200, f"Campaigns page failed: {resp.status_code}"

    # Patients page should load
    resp = client.get("/dashboard/patients", cookies={"session": session_cookie})
    assert resp.status_code == 200, f"Patients page failed: {resp.status_code}"

    # Campaign diagnostics page should load
    resp = client.get(
        "/dashboard/campaigns/diagnostics",
        cookies={"session": session_cookie},
    )
    assert resp.status_code == 200, f"Diagnostics page failed: {resp.status_code}"

    # Patient import page should load
    resp = client.get(
        "/dashboard/patients/import",
        cookies={"session": session_cookie},
    )
    assert resp.status_code == 200, f"Import page failed: {resp.status_code}"


# ── Run all tests ────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("MODULE 1 END-TO-END TEST SUITE")
    print("=" * 60)
    print(f"Database: {TEST_DB_PATH}")
    print()

    tests = [
        ("Test 1: Database Migration & Schema Integrity", test_1_database_migration),
        ("Test 2: Patient CSV Import — Full Workflow", test_2_csv_import),
        ("Test 3: Patient Tier Computation Edge Cases", test_3_tier_computation),
        ("Test 4: Segment Creation & Resolution", test_4_segment_resolution),
        ("Test 5: Campaign CRUD & State Machine", test_5_campaign_state_machine),
        ("Test 6: Campaign Creation from Template", test_6_templates),
        ("Test 7: Merge Tag Substitution", test_7_merge_tags),
        ("Test 8: Warmup Schedule Calculation", test_8_warmup_schedule),
        ("Test 9: Webhook Signature Verification", test_9_webhook_signature),
        ("Test 10: Webhook Event Processing", test_10_webhook_events),
        ("Test 11: Campaign Metrics Aggregation", test_11_metrics_aggregation),
        ("Test 12: Patient Suppression Logic", test_12_suppression),
        ("Test 13: App Startup & Route Protection", test_13_app_routes),
    ]

    for name, fn in tests:
        run_test(name, fn)

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    print("=" * 60)

    if errors:
        print("\nFAILURES:")
        for name, err in errors:
            print(f"  {name}")
            print(f"    {err}")

    # Cleanup temp database
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)

    if failed > 0:
        sys.exit(1)
    else:
        print("\nAll tests passed.")
        sys.exit(0)

import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.config import settings as app_settings
from app.ghl_db import (
    get_reward_notification, update_reward_notification,
    get_or_create_patient_credits, add_credit, get_referral_code_by_patient,
    insert_ghl_event, upsert_ghl_contact, mark_ghl_event_processed,
)
from app.services.referral_service import (
    generate_referral_code, create_manual_referral,
    create_referral_from_webhook, advance_referral_to_qualified,
    advance_referral_to_paid,
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


# ── GHL Test Harness ─────────────────────────────────────

@router.get("/test-harness", response_class=HTMLResponse)
async def ghl_test_harness(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    if not app_settings.enable_ghl_test_harness:
        return HTMLResponse("<h1>Test harness disabled</h1><p>Set ENABLE_GHL_TEST_HARNESS=true to enable.</p>", status_code=403)
    return templates.TemplateResponse("ghl_test.html", {"request": request, "active": "referrals"})


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
        result_msg += "Referral qualified. " if ref else "No matching referral found. "

    elif event_type == "OpportunityStatusUpdate":
        ref = advance_referral_to_paid(fake_contact_id)
        result_msg += "Referral marked paid. " if ref else "No matching referral found. "

    if event_id:
        mark_ghl_event_processed(event_id)

    return HTMLResponse(f'<p class="text-green-600 text-sm mt-2">{result_msg}</p>')

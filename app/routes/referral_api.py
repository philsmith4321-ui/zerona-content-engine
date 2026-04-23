import json
from datetime import datetime

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.ghl_db import (
    get_reward_notification, update_reward_notification,
    get_or_create_patient_credits, add_credit, get_referral_code_by_patient,
)
from app.services.referral_service import (
    generate_referral_code, create_manual_referral,
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

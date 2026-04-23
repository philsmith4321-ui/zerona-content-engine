from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.ghl_db import (
    get_referral_leaderboard, get_referrals_by_referrer,
    get_referral_code_by_patient, get_or_create_patient_credits,
    get_credit_transactions, get_ghl_events, get_ghl_event_count,
    get_reward_notifications, get_reward_notification,
)
from app.campaign_db import get_patients
from app.database import get_db
from app.services.ghl_service import is_configured as ghl_is_configured

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


@router.get("/referrals", response_class=HTMLResponse)
async def referrals_dashboard(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    leaderboard = get_referral_leaderboard(limit=20)

    # Get summary stats
    conn = get_db()
    total_referrals = conn.execute("SELECT COUNT(*) as cnt FROM referrals").fetchone()["cnt"]
    pending = conn.execute("SELECT COUNT(*) as cnt FROM referrals WHERE status = 'pending'").fetchone()["cnt"]
    qualified = conn.execute("SELECT COUNT(*) as cnt FROM referrals WHERE status = 'qualified'").fetchone()["cnt"]
    paid = conn.execute("SELECT COUNT(*) as cnt FROM referrals WHERE status = 'paid'").fetchone()["cnt"]
    pending_rewards = conn.execute("SELECT COUNT(*) as cnt FROM reward_notifications WHERE status = 'draft'").fetchone()["cnt"]
    conn.close()

    return templates.TemplateResponse("referrals.html", {
        "request": request, "active": "referrals",
        "leaderboard": leaderboard,
        "stats": {"total": total_referrals, "pending": pending, "qualified": qualified, "paid": paid},
        "pending_rewards": pending_rewards,
        "ghl_configured": ghl_is_configured(),
    })


@router.get("/referrals/patient/{patient_id}", response_class=HTMLResponse)
async def referral_patient_detail(request: Request, patient_id: int):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    if not patient:
        return RedirectResponse(url="/dashboard/referrals", status_code=303)
    patient = dict(patient)

    referrals = get_referrals_by_referrer(patient_id)
    code_record = get_referral_code_by_patient(patient_id)
    credits = get_or_create_patient_credits(patient_id)
    transactions = get_credit_transactions(patient_id)

    return templates.TemplateResponse("referral_patient.html", {
        "request": request, "active": "referrals",
        "patient": patient, "referrals": referrals,
        "referral_code": code_record["code"] if code_record else None,
        "credits": credits, "transactions": transactions,
    })


@router.get("/referrals/events", response_class=HTMLResponse)
async def ghl_events_page(request: Request, event_type: str = "", page: int = 1):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    per_page = 50
    offset = (page - 1) * per_page
    events = get_ghl_events(event_type=event_type or None, limit=per_page, offset=offset)
    total = get_ghl_event_count(event_type=event_type or None)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return templates.TemplateResponse("ghl_events.html", {
        "request": request, "active": "referrals",
        "events": events, "current_type": event_type,
        "page": page, "total_pages": total_pages, "total": total,
    })


@router.get("/referrals/rewards", response_class=HTMLResponse)
async def reward_queue_page(request: Request, status: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    notifications = get_reward_notifications(status=status or None)
    return templates.TemplateResponse("reward_queue.html", {
        "request": request, "active": "referrals",
        "notifications": notifications, "current_status": status,
    })

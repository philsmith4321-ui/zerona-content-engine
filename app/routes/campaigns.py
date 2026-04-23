import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.campaign_db import (
    get_campaigns, get_campaign, get_campaign_metrics,
    get_segments, get_segment_count, get_patient_stats,
    get_import_history, get_patients, get_patient_count,
)
from app.database import get_db
from app.services.campaign_service import CAMPAIGN_TEMPLATES
from app.services.mailgun_service import test_connection, is_configured

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_list(request: Request, status: str = ""):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    campaigns = get_campaigns(status=status or None)
    # Add metrics to each campaign
    for c in campaigns:
        c["metrics"] = get_campaign_metrics(c["id"])
    patient_stats = get_patient_stats()
    return templates.TemplateResponse("campaigns.html", {
        "request": request, "active": "campaigns",
        "campaigns": campaigns, "patient_stats": patient_stats,
        "current_status": status, "templates": CAMPAIGN_TEMPLATES,
    })


@router.get("/campaigns/diagnostics", response_class=HTMLResponse)
async def campaign_diagnostics(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect

    # Mailgun connection
    mailgun_status = test_connection()
    mailgun_configured = is_configured()

    # DNS verification (from Mailgun domain info)
    dns_records = {}
    if mailgun_configured:
        try:
            import requests as req
            from app.config import settings
            resp = req.get(
                f"https://api.mailgun.net/v3/domains/{settings.mailgun_domain}",
                auth=("api", settings.mailgun_api_key), timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                for record in data.get("sending_dns_records", []):
                    rtype = record.get("record_type", "")
                    name = record.get("name", "")
                    if "spf" in name or rtype == "TXT" and "spf" in record.get("value", ""):
                        dns_records["SPF"] = record.get("valid", "unknown")
                    elif "domainkey" in name:
                        dns_records["DKIM"] = record.get("valid", "unknown")
                for record in data.get("receiving_dns_records", []):
                    rtype = record.get("record_type", "")
                    if rtype == "MX":
                        dns_records["MX"] = record.get("valid", "unknown")
        except Exception:
            pass

    # Database table counts
    conn = get_db()
    table_counts = {}
    for table in ["patients", "campaigns", "campaign_sends", "campaign_events", "segments", "import_history"]:
        try:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            table_counts[table] = row["cnt"]
        except Exception:
            table_counts[table] = "N/A"

    # Recent webhook events (last 20)
    try:
        recent_events = [dict(r) for r in conn.execute(
            "SELECT * FROM campaign_events ORDER BY id DESC LIMIT 20"
        ).fetchall()]
    except Exception:
        recent_events = []

    # Failed sends in last 24 hours
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    try:
        failed_sends = [dict(r) for r in conn.execute(
            """SELECT cs.*, p.email, p.first_name FROM campaign_sends cs
               JOIN patients p ON cs.patient_id = p.id
               WHERE cs.status = 'failed' AND cs.sent_at >= ?
               ORDER BY cs.sent_at DESC LIMIT 50""",
            (cutoff,),
        ).fetchall()]
    except Exception:
        failed_sends = []

    # Patient stats
    patient_stats = get_patient_stats()

    conn.close()

    return templates.TemplateResponse("campaign_diagnostics.html", {
        "request": request, "active": "campaigns",
        "mailgun_configured": mailgun_configured,
        "mailgun_status": mailgun_status,
        "dns_records": dns_records,
        "table_counts": table_counts,
        "recent_events": recent_events,
        "failed_sends": failed_sends,
        "patient_stats": patient_stats,
    })


@router.get("/campaigns/{campaign_id}", response_class=HTMLResponse)
async def campaign_detail(request: Request, campaign_id: int):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    campaign = get_campaign(campaign_id)
    if not campaign:
        return RedirectResponse(url="/dashboard/campaigns", status_code=303)
    metrics = get_campaign_metrics(campaign_id)
    segments = get_segments()
    segment_count = get_segment_count(campaign["segment_id"]) if campaign.get("segment_id") else 0
    return templates.TemplateResponse("campaign_detail.html", {
        "request": request, "active": "campaigns",
        "campaign": campaign, "metrics": metrics,
        "segments": segments, "segment_count": segment_count,
    })


@router.get("/campaigns/{campaign_id}/edit", response_class=HTMLResponse)
async def campaign_edit(request: Request, campaign_id: int):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    campaign = get_campaign(campaign_id)
    if not campaign:
        return RedirectResponse(url="/dashboard/campaigns", status_code=303)
    segments = get_segments()
    for s in segments:
        s["count"] = get_segment_count(s["id"])
    return templates.TemplateResponse("campaign_builder.html", {
        "request": request, "active": "campaigns",
        "campaign": campaign, "segments": segments,
    })


@router.get("/campaigns/new/builder", response_class=HTMLResponse)
async def campaign_new(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    segments = get_segments()
    for s in segments:
        s["count"] = get_segment_count(s["id"])
    return templates.TemplateResponse("campaign_builder.html", {
        "request": request, "active": "campaigns",
        "campaign": None, "segments": segments,
    })


@router.get("/campaigns/{campaign_id}/preview", response_class=HTMLResponse)
async def campaign_preview(request: Request, campaign_id: int):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    campaign = get_campaign(campaign_id)
    if not campaign:
        return RedirectResponse(url="/dashboard/campaigns", status_code=303)
    # Render with sample merge tags
    preview_html = campaign.get("body_html", "")
    preview_html = preview_html.replace("{{first_name}}", "Sarah")
    preview_html = preview_html.replace("{{last_visit_date}}", "March 15, 2026")
    preview_html = preview_html.replace("%recipient.first_name%", "Sarah")
    preview_html = preview_html.replace("%recipient.last_visit_date%", "March 15, 2026")
    return templates.TemplateResponse("campaign_preview.html", {
        "request": request, "active": "campaigns",
        "campaign": campaign, "preview_html": preview_html,
    })


@router.get("/patients", response_class=HTMLResponse)
async def patients_list(request: Request, tier: str = "", search: str = "", page: int = 1):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    per_page = 50
    offset = (page - 1) * per_page
    patients = get_patients(tier=tier or None, search=search or None, limit=per_page, offset=offset)
    total = get_patient_count(tier=tier or None)
    total_pages = max(1, (total + per_page - 1) // per_page)
    stats = get_patient_stats()
    imports = get_import_history(limit=5)
    return templates.TemplateResponse("patients.html", {
        "request": request, "active": "campaigns",
        "patients": patients, "stats": stats, "imports": imports,
        "current_tier": tier, "current_search": search,
        "page": page, "total_pages": total_pages, "total": total,
    })


@router.get("/patients/import", response_class=HTMLResponse)
async def patient_import_page(request: Request):
    redirect = _require_auth(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("patient_import.html", {
        "request": request, "active": "campaigns",
        "step": "upload", "preview": None, "result": None,
    })

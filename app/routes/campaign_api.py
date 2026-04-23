import json

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import is_authenticated
from app.campaign_db import (
    create_campaign, update_campaign, get_campaign, get_segments,
    create_segment, get_segment_count,
)
from app.services.campaign_service import (
    create_campaign_from_template, generate_email_copy,
    prepare_and_send_campaign, CAMPAIGN_TEMPLATES,
)
from app.services.patient_service import preview_csv, import_patients
from app.services.mailgun_service import test_connection, send_single, is_configured
from app.services.ghl_service import test_connection as ghl_test_connection, is_configured as ghl_is_configured
from app.database import log_event

router = APIRouter(prefix="/api/campaigns")
templates = Jinja2Templates(directory="app/templates")


def _require_auth(request: Request):
    if not is_authenticated(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return None


# ── Campaign CRUD ─────────────────────────────────────────

@router.post("/create")
async def api_create_campaign(request: Request, name: str = Form(...), segment_id: int = Form(0),
                               subject: str = Form(""), template_key: str = Form("")):
    auth = _require_auth(request)
    if auth:
        return auth

    if template_key and template_key in CAMPAIGN_TEMPLATES:
        cid = create_campaign_from_template(template_key)
        if segment_id:
            update_campaign(cid, segment_id=segment_id)
    else:
        cid = create_campaign({
            "name": name, "segment_id": segment_id if segment_id else None,
            "subject": subject, "status": "draft",
        })

    return RedirectResponse(url=f"/dashboard/campaigns/{cid}/edit", status_code=303)


@router.post("/{campaign_id}/update")
async def api_update_campaign(request: Request, campaign_id: int,
                               name: str = Form(""), subject: str = Form(""),
                               body_html: str = Form(""), body_text: str = Form(""),
                               segment_id: int = Form(0)):
    auth = _require_auth(request)
    if auth:
        return auth
    kwargs = {}
    if name:
        kwargs["name"] = name
    if subject:
        kwargs["subject"] = subject
    if body_html:
        kwargs["body_html"] = body_html
    if body_text:
        kwargs["body_text"] = body_text
    if segment_id:
        kwargs["segment_id"] = segment_id
    update_campaign(campaign_id, **kwargs)
    return RedirectResponse(url=f"/dashboard/campaigns/{campaign_id}/edit", status_code=303)


@router.post("/{campaign_id}/approve")
async def api_approve_campaign(request: Request, campaign_id: int):
    auth = _require_auth(request)
    if auth:
        return auth
    update_campaign(campaign_id, status="approved")
    log_event("campaign", f"Campaign {campaign_id} approved")
    return RedirectResponse(url=f"/dashboard/campaigns/{campaign_id}", status_code=303)


# ── AI Copy Generation ────────────────────────────────────

@router.post("/{campaign_id}/generate")
async def api_generate_copy(request: Request, campaign_id: int, brief: str = Form("")):
    auth = _require_auth(request)
    if auth:
        return auth
    result = generate_email_copy(campaign_id, brief=brief or None)
    if result.get("error"):
        return HTMLResponse(f'<p class="text-red-500 text-sm">{result["error"]}</p>')
    return RedirectResponse(url=f"/dashboard/campaigns/{campaign_id}/edit", status_code=303)


# ── Sending ───────────────────────────────────────────────

@router.post("/{campaign_id}/send")
async def api_send_campaign(request: Request, campaign_id: int,
                             force_no_warmup: bool = Form(False)):
    auth = _require_auth(request)
    if auth:
        return auth
    campaign = get_campaign(campaign_id)
    if not campaign:
        return JSONResponse({"error": "Not found"}, status_code=404)
    if campaign["status"] != "approved":
        return JSONResponse({"error": "Campaign must be approved first"}, status_code=400)
    result = prepare_and_send_campaign(campaign_id, force_no_warmup=force_no_warmup)
    if result.get("error"):
        return HTMLResponse(f'<p class="text-red-500 text-sm mt-2">{result["error"]}</p>')
    return RedirectResponse(url=f"/dashboard/campaigns/{campaign_id}", status_code=303)


@router.post("/{campaign_id}/test-send")
async def api_test_send(request: Request, campaign_id: int, test_email: str = Form(...)):
    auth = _require_auth(request)
    if auth:
        return auth
    campaign = get_campaign(campaign_id)
    if not campaign:
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Replace merge tags with sample data
    html = campaign.get("body_html", "")
    html = html.replace("{{first_name}}", "Test")
    html = html.replace("{{last_visit_date}}", "March 15, 2026")
    result = send_single(
        to_email=test_email,
        subject=f"[TEST] {campaign.get('subject', 'Test')}",
        html=html,
        text=campaign.get("body_text", ""),
    )
    if result["success"]:
        return HTMLResponse(f'<p class="text-green-600 text-sm mt-2">Test sent to {test_email}</p>')
    return HTMLResponse(f'<p class="text-red-500 text-sm mt-2">Failed: {result.get("error")}</p>')


@router.get("/mailgun/test")
async def api_mailgun_test(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    result = test_connection()
    return JSONResponse(result)


# ── Segments ──────────────────────────────────────────────

@router.post("/segments/create")
async def api_create_segment(request: Request, name: str = Form(...),
                              segment_type: str = Form("tier"), criteria: str = Form("{}")):
    auth = _require_auth(request)
    if auth:
        return auth
    try:
        criteria_dict = json.loads(criteria)
    except json.JSONDecodeError:
        criteria_dict = {}
    sid = create_segment(name, segment_type, criteria_dict)
    return RedirectResponse(url="/dashboard/campaigns", status_code=303)


@router.get("/segments/{segment_id}/count")
async def api_segment_count(request: Request, segment_id: int):
    auth = _require_auth(request)
    if auth:
        return auth
    count = get_segment_count(segment_id)
    return HTMLResponse(f'<span class="font-semibold">{count:,}</span> patients')


# ── Patient Import ────────────────────────────────────────

@router.post("/patients/upload")
async def api_upload_csv(request: Request, file: UploadFile = File(...)):
    auth = _require_auth(request)
    if auth:
        return auth
    content = (await file.read()).decode("utf-8-sig")
    preview = preview_csv(content)
    return templates.TemplateResponse("patient_import.html", {
        "request": request, "active": "campaigns",
        "step": "mapping", "preview": preview,
        "csv_content": content, "filename": file.filename,
        "result": None,
    })


@router.post("/patients/import")
async def api_import_patients(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    form = await request.form()
    csv_content = form.get("csv_content", "")
    filename = form.get("filename", "upload.csv")

    # Build column mapping from form fields
    mapping = {}
    for field in ["email", "first_name", "last_name", "phone", "last_visit_date", "gender", "age", "tags"]:
        csv_col = form.get(f"map_{field}", "")
        if csv_col:
            mapping[field] = csv_col

    if "email" not in mapping:
        return templates.TemplateResponse("patient_import.html", {
            "request": request, "active": "campaigns",
            "step": "mapping", "preview": preview_csv(csv_content),
            "csv_content": csv_content, "filename": filename,
            "result": None, "error": "Email column mapping is required",
        })

    result = import_patients(csv_content, mapping, filename)
    return templates.TemplateResponse("patient_import.html", {
        "request": request, "active": "campaigns",
        "step": "result", "preview": None,
        "result": result,
    })


# ── GHL Connection Test ──────────────────────────────────

@router.get("/ghl/test")
async def api_ghl_test(request: Request):
    auth = _require_auth(request)
    if auth:
        return auth
    result = ghl_test_connection()
    return JSONResponse(result)

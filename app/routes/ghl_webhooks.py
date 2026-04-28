from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.ghl_service import verify_webhook
from app.ghl_db import insert_ghl_event, upsert_ghl_contact, get_ghl_contact
from app.services.referral_service import (
    create_referral_from_webhook, advance_referral_to_qualified,
    advance_referral_to_paid,
)
from app.database import log_event

router = APIRouter()


def _extract_utm_campaign(payload: dict) -> str:
    """Extract referral code from UTM campaign field in webhook payload."""
    # Check top-level fields
    utm = payload.get("utm_campaign", "") or payload.get("utmCampaign", "")
    if utm:
        return utm

    # Check custom fields array
    for cf in payload.get("customFields", []):
        field_key = cf.get("key", "") or cf.get("id", "")
        if "utm_campaign" in field_key.lower() or "utmcampaign" in field_key.lower():
            return cf.get("value", "")

    # Check source field as fallback
    source = payload.get("source", "")
    # If source looks like a referral code pattern (name-digits-chars)
    import re
    if re.match(r"^[a-z]+-\d{4}-[a-z0-9]{3}$", source):
        return source

    return ""


def _extract_contact_data(payload: dict) -> dict:
    """Extract contact fields from GHL webhook payload."""
    custom_fields = {}
    for cf in payload.get("customFields", []):
        key = cf.get("key", cf.get("id", ""))
        custom_fields[key] = cf.get("value", "")

    return {
        "ghl_contact_id": payload.get("id", ""),
        "name": payload.get("name", ""),
        "first_name": payload.get("firstName", ""),
        "last_name": payload.get("lastName", ""),
        "email": payload.get("email", ""),
        "phone": payload.get("phone", ""),
        "source": payload.get("source", ""),
        "utm_source": payload.get("utm_source", "") or custom_fields.get("utm_source", ""),
        "utm_medium": payload.get("utm_medium", "") or custom_fields.get("utm_medium", ""),
        "utm_campaign": payload.get("utm_campaign", "") or custom_fields.get("utm_campaign", ""),
        "tags": payload.get("tags", []),
        "custom_fields": custom_fields,
    }


@router.post("/webhooks/ghl")
async def ghl_webhook(request: Request):
    """Receive GHL webhook events. Public endpoint — verified via signature/secret."""
    try:
        body = await request.body()
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    # Verify webhook authenticity
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not verify_webhook(body, headers):
        return JSONResponse({"error": "Invalid signature"}, status_code=403)

    event_type = payload.get("type", "unknown")
    location_id = payload.get("locationId", "")

    # Determine contact_id based on event type
    if event_type in ("ContactCreate", "ContactUpdate"):
        contact_id = payload.get("id", "")
    elif event_type in ("OpportunityStageUpdate", "OpportunityStatusUpdate"):
        contact_id = payload.get("contactId", "")
    elif event_type in ("AppointmentCreate", "AppointmentUpdate"):
        appt = payload.get("appointment", {})
        contact_id = appt.get("contactId", "")
    else:
        contact_id = payload.get("contactId", payload.get("id", ""))

    # Build a unique event ID for idempotency
    ghl_event_id = payload.get("eventId", "") or payload.get("id", "")
    if ghl_event_id:
        ghl_event_id = f"{event_type}_{ghl_event_id}"

    # Store event (returns None if duplicate)
    event_id = insert_ghl_event({
        "ghl_event_id": ghl_event_id or None,
        "event_type": event_type,
        "location_id": location_id,
        "contact_id": contact_id,
        "payload": payload,
    })

    if event_id is None:
        log_event("ghl", f"Duplicate event skipped: {ghl_event_id}")
        return JSONResponse({"status": "duplicate_skipped"})

    # Process by event type
    if event_type == "ContactCreate":
        contact_data = _extract_contact_data(payload)
        upsert_ghl_contact(contact_data)

        # Check for referral UTM
        utm_campaign = _extract_utm_campaign(payload)
        utm_source = payload.get("utm_source", "") or contact_data.get("utm_source", "")
        if utm_source == "referral" and utm_campaign:
            create_referral_from_webhook(
                referral_code=utm_campaign,
                ghl_contact_id=contact_id,
                referee_email=payload.get("email", ""),
                referee_name=payload.get("name", payload.get("firstName", "")),
            )

    elif event_type == "ContactUpdate":
        contact_data = _extract_contact_data(payload)
        upsert_ghl_contact(contact_data)

    elif event_type == "AppointmentCreate":
        appt = payload.get("appointment", {})
        appt_contact_id = appt.get("contactId", "")
        if appt_contact_id:
            advance_referral_to_qualified(appt_contact_id)

    elif event_type in ("OpportunityStageUpdate", "OpportunityStatusUpdate"):
        opp_contact_id = payload.get("contactId", "")
        opp_status = payload.get("status", "")
        if opp_status == "won" and opp_contact_id:
            advance_referral_to_paid(opp_contact_id)

    from app.ghl_db import mark_ghl_event_processed
    mark_ghl_event_processed(event_id)

    return JSONResponse({"status": "ok", "event_id": event_id})

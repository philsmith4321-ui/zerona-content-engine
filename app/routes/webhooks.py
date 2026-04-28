from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.mailgun_service import verify_webhook_signature
from app.campaign_db import (
    insert_campaign_event, find_campaign_by_message_id,
    mark_patient_unsubscribed, mark_patient_invalid,
    get_soft_bounce_count,
)
from app.database import log_event

router = APIRouter()


@router.post("/webhooks/mailgun")
async def mailgun_webhook(request: Request):
    """Receive Mailgun webhook events. Public endpoint — verified via signature."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    signature_data = payload.get("signature", {})
    token = signature_data.get("token", "")
    timestamp = signature_data.get("timestamp", "")
    signature = signature_data.get("signature", "")

    if not verify_webhook_signature(token, timestamp, signature):
        return JSONResponse({"error": "Invalid signature"}, status_code=403)

    event_data = payload.get("event-data", {})
    event_type = event_data.get("event", "unknown")
    recipient = event_data.get("recipient", "")
    message_id = event_data.get("message", {}).get("headers", {}).get("message-id", "")
    timestamp_val = event_data.get("timestamp", "")

    # Map Mailgun event names to our event types
    event_map = {
        "delivered": "delivered",
        "opened": "opened",
        "clicked": "clicked",
        "failed": "bounced",
        "complained": "complained",
        "unsubscribed": "unsubscribed",
    }
    our_event_type = event_map.get(event_type)
    if not our_event_type:
        return JSONResponse({"status": "ignored"})

    # Find campaign from message ID
    campaign_id = find_campaign_by_message_id(message_id)

    # Store event
    insert_campaign_event({
        "campaign_id": campaign_id,
        "recipient_email": recipient,
        "event_type": our_event_type,
        "event_data": event_data,
        "mailgun_message_id": message_id,
        "timestamp": timestamp_val,
    })

    # Side effects
    if our_event_type == "unsubscribed":
        mark_patient_unsubscribed(recipient)
        log_event("unsubscribe", f"Patient unsubscribed: {recipient}")

    elif our_event_type == "bounced":
        severity = event_data.get("severity", "")
        if severity == "permanent":
            mark_patient_invalid(recipient)
            log_event("bounce", f"Hard bounce — marked invalid: {recipient}")
        elif severity == "temporary" and campaign_id:
            bounce_count = get_soft_bounce_count(recipient, campaign_id)
            if bounce_count >= 3:
                mark_patient_invalid(recipient)
                log_event("bounce", f"Soft bounce limit reached — marked invalid: {recipient}")

    return JSONResponse({"status": "ok"})

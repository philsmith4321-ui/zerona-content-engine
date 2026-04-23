import json
import re
from datetime import datetime
from typing import Optional
from pathlib import Path

import anthropic

from app.config import settings
from app.campaign_db import (
    get_campaign, update_campaign, resolve_segment,
    create_campaign_sends, get_campaign_sends, update_campaign_send,
    create_campaign, get_segment_count,
)
from app.services.mailgun_service import send_batch, check_unsubscribes_bulk, get_warmup_schedule
from app.database import log_event


# ── Pre-built email templates ─────────────────────────────

CAMPAIGN_TEMPLATES = {
    "week1_teaser": {
        "name": "Week 1: Teaser",
        "subject": "Something exciting is coming to White House Chiropractic...",
        "brief": "A teaser email hinting that an exciting new service is coming soon. Build curiosity without revealing what it is. Mention that loyal patients will get first access.",
    },
    "week2_education": {
        "name": "Week 2: Education",
        "subject": "What if you could lose inches without surgery?",
        "brief": "Educational email explaining what cold laser body contouring is. Focus on the science, FDA clearance, and the Erchonia clinical data. Position it as a natural fit alongside chiropractic wellness.",
    },
    "week3_vip": {
        "name": "Week 3: VIP Early Access",
        "subject": "{{first_name}}, you're invited: exclusive founding member pricing",
        "brief": "VIP early access offer for Tier 1 (active) patients only. Founding member pricing at a significant discount. Limited spots. This is the first email that mentions specific pricing — make them feel special for being loyal patients.",
    },
    "week4_social_proof": {
        "name": "Week 4: Social Proof",
        "subject": "The clinical results speak for themselves",
        "brief": "Share Erchonia's clinical trial data — average 3.64 inches lost. Include testimonial-style language (from clinical studies, not fabricated). Position Dr. Banning as carefully selecting this technology after extensive research.",
    },
    "week5_urgency": {
        "name": "Week 5: Urgency",
        "subject": "{{first_name}}, founding member pricing ends soon",
        "brief": "Urgency email — founding member pricing deadline is approaching. Recap the offer, the results, and the limited availability. Include a strong CTA to book a consultation.",
    },
    "week6_launch": {
        "name": "Week 6: Official Launch",
        "subject": "We're live! Zerona Z6 is here at White House Chiropractic",
        "brief": "Official launch announcement. Regular pricing now in effect. Mention the open house event. Celebrate with the community. Include booking CTA.",
    },
}


def create_campaign_from_template(template_key: str) -> Optional[int]:
    """Create a draft campaign from a pre-built template."""
    template = CAMPAIGN_TEMPLATES.get(template_key)
    if not template:
        return None
    return create_campaign({
        "name": template["name"],
        "subject": template["subject"],
        "template_key": template_key,
        "body_html": f"<!-- Generated from template: {template_key} -->\n<p>Use 'Generate Copy' to create the email content.</p>",
        "body_text": "",
        "from_email": settings.mailgun_from_email,
        "from_name": settings.mailgun_from_name,
        "status": "draft",
    })


def generate_email_copy(campaign_id: int, brief: Optional[str] = None) -> dict:
    """Use Claude to generate email HTML from a brief or template."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}

    prompt_text = Path("prompts/email_campaign.txt").read_text() if Path("prompts/email_campaign.txt").exists() else ""

    # Use template brief if available
    if not brief and campaign.get("template_key"):
        template = CAMPAIGN_TEMPLATES.get(campaign["template_key"])
        if template:
            brief = template["brief"]

    if not brief:
        return {"error": "No brief provided and no template found"}

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": f"""{prompt_text}

TASK: Write an email for this campaign.

Subject line: {campaign.get('subject', 'TBD')}

Brief: {brief}

Respond with ONLY valid JSON (no code fences):
{{
    "subject": "the email subject line (with merge tags if appropriate)",
    "body_html": "the full HTML email body with inline CSS, mobile-friendly",
    "body_text": "plain text version of the email"
}}""",
        }],
    )

    text = message.content[0].text.strip()
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response"}

    update_campaign(
        campaign_id,
        subject=result.get("subject", campaign["subject"]),
        body_html=result.get("body_html", ""),
        body_text=result.get("body_text", ""),
    )
    log_event("campaign", f"Generated email copy for campaign {campaign_id}")
    return {"success": True, "subject": result.get("subject"), "campaign_id": campaign_id}


def apply_merge_tags(html: str, patient: dict) -> str:
    """Replace merge tags with patient-specific values."""
    result = html
    result = result.replace("{{first_name}}", patient.get("first_name", ""))
    result = result.replace("{{last_visit_date}}", patient.get("last_visit_date", ""))
    result = result.replace("%recipient.first_name%", patient.get("first_name", ""))
    result = result.replace("%recipient.last_visit_date%", patient.get("last_visit_date", ""))
    return result


def prepare_and_send_campaign(campaign_id: int, force_no_warmup: bool = False) -> dict:
    """Resolve segment, filter suppressions, create sends, dispatch via Mailgun."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}
    if campaign["status"] not in ("approved", "sending"):
        return {"error": f"Campaign must be approved before sending (current: {campaign['status']})"}
    if not campaign.get("segment_id"):
        return {"error": "No segment assigned to this campaign"}

    # Resolve segment to patient list
    patients = resolve_segment(campaign["segment_id"])
    if not patients:
        return {"error": "No patients match this segment"}

    # Filter out unsubscribed/invalid from our DB
    patients = [p for p in patients if p["email_status"] == "valid"]

    # Check Mailgun's unsubscribe list
    emails = [p["email"] for p in patients]
    mg_unsubs = check_unsubscribes_bulk(emails)
    patients = [p for p in patients if p["email"].lower() not in mg_unsubs]

    if not patients:
        return {"error": "All recipients are suppressed"}

    # Check warmup
    total = len(patients)
    warmup = None
    if not force_no_warmup:
        warmup = get_warmup_schedule(total)
        if warmup and len(warmup) > 1:
            update_campaign(campaign_id, warmup_schedule=json.dumps(warmup), total_recipients=total,
                            status="sending", started_at=datetime.now().isoformat())
            # Send first batch only
            first_batch_size = warmup[0]["count"]
            patients_batch = patients[:first_batch_size]
            create_campaign_sends(campaign_id, [p["id"] for p in patients_batch])
            return _dispatch_batch(campaign_id, campaign, patients_batch)

    # No warmup needed or forced — send all
    update_campaign(campaign_id, total_recipients=total, status="sending",
                    started_at=datetime.now().isoformat(), warmup_schedule=None)
    create_campaign_sends(campaign_id, [p["id"] for p in patients])
    return _dispatch_batch(campaign_id, campaign, patients)


def send_next_warmup_batch(campaign_id: int) -> Optional[dict]:
    """Send the next batch in a warmup schedule. Called by scheduler."""
    campaign = get_campaign(campaign_id)
    if not campaign or campaign["status"] != "sending":
        return None
    if not campaign.get("warmup_schedule"):
        return None

    schedule = json.loads(campaign["warmup_schedule"])
    already_sent = len(get_campaign_sends(campaign_id, limit=100000))

    # Find next batch
    cumulative = 0
    for batch_info in schedule:
        cumulative += batch_info["count"]
        if cumulative > already_sent:
            # This is the next batch to send
            offset = already_sent
            batch_size = batch_info["count"]
            break
    else:
        # All batches done
        update_campaign(campaign_id, status="sent", completed_at=datetime.now().isoformat())
        return {"done": True}

    # Resolve full patient list again and pick the next slice
    patients = resolve_segment(campaign["segment_id"])
    patients = [p for p in patients if p["email_status"] == "valid"]
    patients_batch = patients[offset : offset + batch_size]
    if not patients_batch:
        update_campaign(campaign_id, status="sent", completed_at=datetime.now().isoformat())
        return {"done": True}

    create_campaign_sends(campaign_id, [p["id"] for p in patients_batch])
    return _dispatch_batch(campaign_id, campaign, patients_batch)


def _dispatch_batch(campaign_id: int, campaign: dict, patients: list[dict]) -> dict:
    """Actually send a batch of emails via Mailgun."""
    sends = get_campaign_sends(campaign_id, status="queued")
    send_map = {s["email"]: s for s in sends}

    recipients = []
    for p in patients:
        send = send_map.get(p["email"])
        if send:
            recipients.append({
                "email": p["email"],
                "first_name": p.get("first_name", ""),
                "last_visit_date": p.get("last_visit_date", ""),
                "send_id": send["id"],
            })

    # Use Mailgun recipient-variables for merge tags
    # Convert our {{var}} syntax to Mailgun's %recipient.var% syntax in the HTML
    html = campaign["body_html"]
    html = html.replace("{{first_name}}", "%recipient.first_name%")
    html = html.replace("{{last_visit_date}}", "%recipient.last_visit_date%")
    text = campaign.get("body_text", "")
    text = text.replace("{{first_name}}", "%recipient.first_name%")
    text = text.replace("{{last_visit_date}}", "%recipient.last_visit_date%")

    results = send_batch(
        recipients=recipients,
        subject=campaign["subject"],
        html=html, text=text,
        from_email=campaign.get("from_email") or settings.mailgun_from_email,
        from_name=campaign.get("from_name") or settings.mailgun_from_name,
        campaign_id=campaign_id,
    )

    sent_count = 0
    failed_count = 0
    for r in results:
        if r["success"]:
            update_campaign_send(r["send_id"], status="sent",
                                  mailgun_message_id=r.get("message_id"),
                                  sent_at=datetime.now().isoformat())
            sent_count += 1
        else:
            update_campaign_send(r["send_id"], status="failed",
                                  error_message=r.get("error", "Unknown"))
            failed_count += 1

    # Check if campaign is complete (no warmup or last batch)
    if not campaign.get("warmup_schedule"):
        update_campaign(campaign_id, status="sent", completed_at=datetime.now().isoformat())

    log_event("campaign", f"Campaign {campaign_id}: sent {sent_count}, failed {failed_count}")
    return {"sent": sent_count, "failed": failed_count, "total": len(recipients)}

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException

from app.database import get_db
from app.models.lead import OutreachSendRequest, EmailRecord, WebsiteSpec
from app.services.ai_analyzer import analyze_website
from app.services.email_generator import generate_initial_email, generate_followup_email
from app.services.email_sender import send_email
from app.services.website_generator import generate_website_spec

router = APIRouter(prefix="/api/outreach", tags=["outreach"])
logger = logging.getLogger(__name__)

# Same headers/limit as evaluator.py
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
_HTML_SIZE_LIMIT = 50 * 1024


async def _fetch_homepage(url: str) -> str:
    """Fetch homepage HTML, capped at 50KB. Returns empty string on failure."""
    try:
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
            async with client.stream("GET", url, timeout=10.0) as resp:
                if resp.status_code >= 400:
                    return ""
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes(4096):
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= _HTML_SIZE_LIMIT:
                        break
                return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _get_lead(lead_id: str) -> dict:
    result = get_db().table("leads").select("*").eq("id", lead_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result.data


@router.post("/{lead_id}/analyze")
async def analyze_lead(lead_id: str):
    """Run AI website analysis and store result in leads.ai_analysis."""
    from app.config import settings
    if not (settings.groq_api_key or settings.sambanova_api_key):
        raise HTTPException(status_code=503, detail="No AI API key configured (GROQ or SAMBANOVA)")

    lead = _get_lead(lead_id)

    # Re-fetch homepage HTML (not stored in DB)
    html = ""
    if lead.get("website_url"):
        html = await _fetch_homepage(lead["website_url"])

    analysis = await analyze_website(
        business_name=lead["business_name"],
        website_url=lead.get("website_url") or "",
        homepage_html=html,
        score_reason=lead.get("score_reason") or "",
        category=lead.get("category"),
        city=lead.get("city"),
        state=lead.get("state"),
    )

    get_db().table("leads").update({
        "ai_analysis": analysis,
        "outreach_status": "queued",
    }).eq("id", lead_id).execute()

    return {"lead_id": lead_id, "ai_analysis": analysis, "outreach_status": "queued"}


@router.post("/{lead_id}/send")
async def send_outreach(lead_id: str, body: OutreachSendRequest = OutreachSendRequest()):
    """Full pipeline: analyze (if needed) → generate email → send → log."""
    from app.services.outreach_engine import send_outreach_to_lead

    lead = _get_lead(lead_id)

    if not lead.get("email"):
        raise HTTPException(status_code=400, detail="Lead has no email address")

    result = await send_outreach_to_lead(lead, dry_run=body.dry_run)

    if not result.get("success") and not result.get("dry_run"):
        if result.get("error") in ("no_email", "bounced", "opted_out", "replied", "max_followups_reached"):
            raise HTTPException(status_code=400, detail=result["error"])

    return {
        "lead_id": lead_id,
        "email_id": result.get("email_id"),
        "resend_id": result.get("resend_id"),
        "status": result.get("status", "failed"),
        "subject": result.get("subject"),
        "body": result.get("body"),
        "dry_run": result.get("dry_run", False),
        "error": result.get("error"),
    }


@router.get("/{lead_id}/emails", response_model=list[EmailRecord])
async def get_email_history(lead_id: str):
    """Return all emails sent for a lead, oldest first."""
    _get_lead(lead_id)  # 404 if not found
    result = (
        get_db()
        .table("email_outreach")
        .select("*")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


@router.post("/{lead_id}/generate-site")
async def generate_site(lead_id: str):
    """Generate a complete website PRD for a lead."""
    from app.config import settings
    if not (settings.groq_api_key or settings.sambanova_api_key):
        raise HTTPException(status_code=503, detail="No AI API key configured (GROQ or SAMBANOVA)")

    lead = _get_lead(lead_id)

    spec = await generate_website_spec(
        business_name=lead["business_name"],
        category=lead.get("category"),
        city=lead["city"],
        state=lead["state"],
        ai_analysis=lead.get("ai_analysis"),
        phone=lead.get("phone"),
        email=lead.get("email"),
    )
    return spec


@router.post("/webhooks/resend")
async def resend_webhook(payload: dict):
    """Handle Resend event webhooks (email.opened, email.bounced, etc.)."""
    event_type = payload.get("type", "")
    data = payload.get("data", {})
    resend_id = data.get("email_id") or data.get("id")

    if not resend_id:
        return {"ok": True}

    status_map = {
        "email.opened": "opened",
        "email.bounced": "bounced",
        "email.clicked": "clicked",
        "email.delivered": "sent",
    }
    new_status = status_map.get(event_type)
    if not new_status:
        return {"ok": True}

    db = get_db()

    # Find the email_outreach row
    result = db.table("email_outreach").select("id, lead_id").eq("resend_id", resend_id).execute()
    if not result.data:
        return {"ok": True}

    row = result.data[0]
    now = datetime.now(timezone.utc).isoformat()

    # Update email status + timestamps
    update_data: dict = {"status": new_status}
    if event_type == "email.opened":
        update_data["opened_at"] = now
    elif event_type == "email.clicked":
        update_data["clicked_at"] = now

    db.table("email_outreach").update(update_data).eq("id", row["id"]).execute()

    if event_type == "email.bounced":
        db.table("leads").update({"outreach_status": "bounced"}).eq("id", row["lead_id"]).execute()

    return {"ok": True}


@router.post("/webhooks/resend/inbound")
async def resend_inbound_webhook(payload: dict):
    """Handle inbound emails (replies) forwarded by Resend."""
    from_email = payload.get("from", "") or payload.get("sender", "")
    subject = payload.get("subject", "")
    text_body = payload.get("text", "") or payload.get("html", "")

    if not from_email:
        return {"ok": True}

    # Normalize: Resend may send from as "Name <email>" or just "email"
    if "<" in from_email and ">" in from_email:
        from_email = from_email.split("<")[1].split(">")[0]
    from_email = from_email.strip().lower()

    db = get_db()

    # Look up lead by email
    result = db.table("leads").select("id, business_name").eq("email", from_email).execute()
    if not result.data:
        # Try case-insensitive match
        result = db.table("leads").select("id, business_name").ilike("email", from_email).execute()
    if not result.data:
        logger.info(f"Inbound email from {from_email} — no matching lead found")
        return {"ok": True}

    lead = result.data[0]
    now = datetime.now(timezone.utc).isoformat()

    # Update lead as replied
    db.table("leads").update({
        "replied": True,
        "replied_at": now,
        "outreach_status": "replied",
    }).eq("id", lead["id"]).execute()

    # Log the reply in email_outreach (sequence_step -1 = inbound)
    db.table("email_outreach").insert({
        "lead_id": lead["id"],
        "sequence_step": -1,
        "subject": subject[:500],
        "body": text_body[:5000],
        "sent_at": now,
        "status": "reply_received",
    }).execute()

    # Insert system message into chat so Alex can surface it
    db.table("chat_messages").insert({
        "role": "system",
        "content": f"Reply received from {lead['business_name']} ({from_email}): \"{subject}\". Lead status updated to replied.",
    }).execute()

    logger.info(f"Reply detected from {lead['business_name']} ({from_email})")
    return {"ok": True}

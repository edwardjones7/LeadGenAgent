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
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

    lead = _get_lead(lead_id)

    if not lead.get("website_url") and not lead.get("email"):
        raise HTTPException(status_code=400, detail="Lead has no website URL or email — nothing to analyze")

    # Re-fetch homepage HTML (not stored in DB)
    html = ""
    if lead.get("website_url"):
        html = await _fetch_homepage(lead["website_url"])

    analysis = await analyze_website(
        business_name=lead["business_name"],
        website_url=lead.get("website_url") or "",
        homepage_html=html,
        score_reason=lead.get("score_reason") or "",
    )

    get_db().table("leads").update({
        "ai_analysis": analysis,
        "outreach_status": "queued",
    }).eq("id", lead_id).execute()

    return {"lead_id": lead_id, "ai_analysis": analysis, "outreach_status": "queued"}


@router.post("/{lead_id}/send")
async def send_outreach(lead_id: str, body: OutreachSendRequest = OutreachSendRequest()):
    """Full pipeline: analyze (if needed) → generate email → send → log."""
    lead = _get_lead(lead_id)

    if not lead.get("email"):
        raise HTTPException(status_code=400, detail="Lead has no email address")

    # Analyze if not yet done
    ai_analysis = lead.get("ai_analysis")
    if not ai_analysis:
        html = ""
        if lead.get("website_url"):
            html = await _fetch_homepage(lead["website_url"])
        ai_analysis = await analyze_website(
            business_name=lead["business_name"],
            website_url=lead.get("website_url") or "",
            homepage_html=html,
            score_reason=lead.get("score_reason") or "",
        )
        get_db().table("leads").update({"ai_analysis": ai_analysis}).eq("id", lead_id).execute()

    # Generate email
    follow_up_count = lead.get("follow_up_count") or 0
    if follow_up_count == 0:
        email_content = await generate_initial_email(
            business_name=lead["business_name"],
            owner_name=None,
            ai_analysis=ai_analysis,
        )
    else:
        email_content = await generate_followup_email(
            business_name=lead["business_name"],
            follow_up_number=follow_up_count,
            ai_analysis=ai_analysis,
        )

    if body.dry_run:
        return {
            "lead_id": lead_id,
            "email_id": None,
            "resend_id": None,
            "status": "dry_run",
            "subject": email_content["subject"],
            "body": email_content["body"],
            "dry_run": True,
        }

    # Send
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: send_email(lead["email"], email_content["subject"], email_content["body"]),
    )

    now = datetime.now(timezone.utc).isoformat()
    sequence_step = follow_up_count

    # Log in email_outreach table
    row = get_db().table("email_outreach").insert({
        "lead_id": lead_id,
        "sequence_step": sequence_step,
        "subject": email_content["subject"],
        "body": email_content["body"],
        "sent_at": now if result["status"] == "sent" else None,
        "resend_id": result["id"],
        "status": result["status"],
        "error_message": result["error"],
    }).execute()

    email_id = row.data[0]["id"] if row.data else None

    # Update lead only on successful send
    if result["status"] == "sent":
        new_outreach_status = f"emailed_{sequence_step + 1}"
        lead_updates: dict = {
            "outreach_status": new_outreach_status,
            "last_emailed_at": now,
            "follow_up_count": follow_up_count,
        }
        # Advance CRM status from New → Contacted
        if lead.get("status") == "New":
            lead_updates["status"] = "Contacted"
        get_db().table("leads").update(lead_updates).eq("id", lead_id).execute()
    else:
        new_outreach_status = lead.get("outreach_status", "idle")

    return {
        "lead_id": lead_id,
        "email_id": email_id,
        "resend_id": result["id"],
        "status": result["status"],
        "subject": email_content["subject"],
        "body": email_content["body"],
        "dry_run": False,
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
    """Generate a complete website spec for a lead."""
    from app.config import settings
    if not settings.groq_api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")

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
        "email.clicked": "opened",
        "email.delivered": "sent",
    }
    new_status = status_map.get(event_type)
    if not new_status:
        return {"ok": True}

    # Find the email_outreach row
    result = get_db().table("email_outreach").select("id, lead_id").eq("resend_id", resend_id).execute()
    if not result.data:
        return {"ok": True}

    row = result.data[0]
    get_db().table("email_outreach").update({"status": new_status}).eq("id", row["id"]).execute()

    if event_type == "email.bounced":
        get_db().table("leads").update({"outreach_status": "bounced"}).eq("id", row["lead_id"]).execute()

    return {"ok": True}

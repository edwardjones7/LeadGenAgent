"""Centralized outreach engine — shared by agent tools, API routes, and scheduler."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.database import get_db

logger = logging.getLogger(__name__)


def is_lead_eligible(lead: dict) -> tuple[bool, str]:
    """Check if a lead can receive an outreach email. Returns (eligible, reason)."""
    if not lead.get("email"):
        return False, "no_email"
    if lead.get("outreach_status") == "bounced":
        return False, "bounced"
    if lead.get("outreach_status") == "opted_out" or lead.get("opted_out"):
        return False, "opted_out"
    if lead.get("replied"):
        return False, "replied"
    follow_up_count = lead.get("follow_up_count") or 0
    if follow_up_count >= 3:
        return False, "max_followups_reached"
    return True, "eligible"


async def get_outreach_config() -> dict:
    """Read outreach config from DB. Returns defaults if table is empty."""
    defaults = {
        "max_per_hour": 50,
        "max_per_day": 200,
        "followup_1_days": 3,
        "followup_2_days": 5,
        "followup_3_days": 7,
        "smart_schedule_enabled": False,
        "min_score_auto": 7,
    }
    try:
        result = get_db().table("outreach_config").select("*").limit(1).execute()
        if result.data:
            row = result.data[0]
            for k in defaults:
                if k in row and row[k] is not None:
                    defaults[k] = row[k]
    except Exception as e:
        logger.warning(f"Could not read outreach_config, using defaults: {e}")
    return defaults


async def get_daily_send_count() -> int:
    """Count emails sent today."""
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    try:
        result = (
            get_db()
            .table("email_outreach")
            .select("id", count="exact")
            .gte("sent_at", today_start)
            .not_.is_("sent_at", "null")
            .execute()
        )
        return result.count or 0
    except Exception as e:
        logger.warning(f"Could not count daily sends: {e}")
        return 0


async def send_outreach_to_lead(lead: dict, dry_run: bool = False) -> dict:
    """
    Unified outreach pipeline: check eligibility → analyze if needed → generate → send → log → update.
    Works for both initial emails and follow-ups based on lead's follow_up_count.
    """
    from app.services.ai_analyzer import analyze_website
    from app.services.email_generator import generate_initial_email, generate_followup_email
    from app.services.email_sender import send_email

    lead_id = lead["id"]
    business_name = lead["business_name"]

    # Eligibility check
    eligible, reason = is_lead_eligible(lead)
    if not eligible:
        return {"success": False, "lead_id": lead_id, "error": reason}

    # Analyze website if not yet done
    ai_analysis = lead.get("ai_analysis")
    if not ai_analysis:
        html = ""
        if lead.get("website_url"):
            import httpx
            try:
                async with httpx.AsyncClient(
                    timeout=10.0,
                    follow_redirects=True,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    },
                ) as client:
                    resp = await client.get(lead["website_url"])
                    html = resp.text[:50_000]
            except Exception:
                html = ""

        ai_analysis = await analyze_website(
            business_name=business_name,
            website_url=lead.get("website_url") or "",
            homepage_html=html,
            score_reason=lead.get("score_reason") or "",
            category=lead.get("category"),
            city=lead.get("city"),
            state=lead.get("state"),
        )
        get_db().table("leads").update({"ai_analysis": ai_analysis}).eq("id", lead_id).execute()

    # Generate email
    follow_up_count = lead.get("follow_up_count") or 0
    if follow_up_count == 0:
        email_content = await generate_initial_email(
            business_name=business_name,
            owner_name=None,
            ai_analysis=ai_analysis,
        )
    else:
        email_content = await generate_followup_email(
            business_name=business_name,
            follow_up_number=follow_up_count,
            ai_analysis=ai_analysis,
        )

    if dry_run:
        return {
            "success": True,
            "lead_id": lead_id,
            "status": "dry_run",
            "subject": email_content["subject"],
            "body": email_content["body"],
            "dry_run": True,
        }

    # Send via Resend
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: send_email(lead["email"], email_content["subject"], email_content["body"]),
    )

    now = datetime.now(timezone.utc).isoformat()
    sequence_step = follow_up_count

    # Log to email_outreach
    db = get_db()
    row = db.table("email_outreach").insert({
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

    # Update lead on success
    if result["status"] == "sent":
        new_outreach_status = f"emailed_{sequence_step + 1}"
        lead_updates = {
            "outreach_status": new_outreach_status,
            "last_emailed_at": now,
            "follow_up_count": follow_up_count if follow_up_count == 0 else follow_up_count,
        }
        # Advance CRM status from New → Contacted on first send
        if lead.get("status") == "New":
            lead_updates["status"] = "Contacted"
        db.table("leads").update(lead_updates).eq("id", lead_id).execute()

    return {
        "success": result["status"] == "sent",
        "lead_id": lead_id,
        "email_id": email_id,
        "resend_id": result["id"],
        "status": result["status"],
        "subject": email_content["subject"],
        "body": email_content["body"],
        "error": result.get("error"),
    }


async def bulk_send(leads: list[dict], delay_seconds: float = 72.0) -> dict:
    """
    Send outreach emails to a list of leads with rate limiting.
    delay_seconds=72 → ~50 emails/hour.
    """
    config = await get_outreach_config()
    daily_count = await get_daily_send_count()
    daily_cap = config["max_per_day"]

    sent = 0
    skipped = 0
    errors = 0
    skipped_reasons: dict[str, int] = {}
    details: list[str] = []

    for lead in leads:
        # Check daily cap
        if daily_count + sent >= daily_cap:
            remaining = len(leads) - (sent + skipped + errors)
            details.append(f"Stopped: daily cap of {daily_cap} reached ({remaining} leads remaining)")
            break

        eligible, reason = is_lead_eligible(lead)
        if not eligible:
            skipped += 1
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
            continue

        result = await send_outreach_to_lead(lead)

        if result.get("success"):
            sent += 1
            details.append(f"Sent to {lead['business_name']} ({lead['email']})")
        else:
            errors += 1
            details.append(f"Failed: {lead['business_name']} — {result.get('error', 'unknown')}")

        # Rate limit delay (skip after last email)
        if delay_seconds > 0 and (sent + errors) < len(leads):
            await asyncio.sleep(delay_seconds)

    return {
        "sent": sent,
        "skipped": skipped,
        "skipped_reasons": skipped_reasons,
        "errors": errors,
        "total_attempted": len(leads),
        "details": details,
    }

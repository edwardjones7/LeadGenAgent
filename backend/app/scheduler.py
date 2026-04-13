import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler_instance = AsyncIOScheduler()


def add_schedule_job(row: dict) -> None:
    """Register a scheduled search job from a search_schedules DB row."""
    job_id = f"search_{row['id']}"
    parts = row["cron_expression"].split()
    if len(parts) != 5:
        logger.warning(f"Invalid cron expression for schedule {row['id']}: {row['cron_expression']}")
        return

    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week
    )

    scheduler_instance.add_job(
        _run_scheduled_search,
        trigger=trigger,
        id=job_id,
        kwargs={
            "schedule_id": str(row["id"]),
            "location": row["location"],
            "categories": row["categories"],
        },
        replace_existing=True,
    )
    logger.info(f"Registered schedule job {job_id}: {row['cron_expression']}")


def remove_schedule_job(schedule_id: str) -> None:
    job_id = f"search_{schedule_id}"
    if scheduler_instance.get_job(job_id):
        scheduler_instance.remove_job(job_id)
        logger.info(f"Removed schedule job {job_id}")


async def _run_scheduled_search(schedule_id: str, location: str, categories: list[str]) -> None:
    from app.services.lead_processor import run_search
    from app.database import get_db
    from datetime import datetime, timezone

    logger.info(f"Running scheduled search schedule_id={schedule_id} location={location}")
    try:
        await run_search(location, categories)
        get_db().table("search_schedules").update(
            {"last_run_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", schedule_id).execute()
    except Exception as e:
        logger.error(f"Scheduled search failed for {schedule_id}: {e}")


def register_followup_job() -> None:
    """Register interval job that checks for overdue follow-up emails every 6 hours."""
    scheduler_instance.add_job(
        _check_and_send_followups,
        trigger="interval",
        hours=6,
        id="followup_checker",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered follow-up checker job (every 6 hours)")


async def _check_and_send_followups() -> None:
    from app.database import get_db
    from app.services.outreach_engine import get_outreach_config, get_daily_send_count
    from datetime import datetime, timezone, timedelta

    config = await get_outreach_config()
    daily_count = await get_daily_send_count()
    daily_cap = config["max_per_day"]

    if daily_count >= daily_cap:
        logger.info(f"Follow-up check skipped: daily cap reached ({daily_count}/{daily_cap})")
        return

    now = datetime.now(timezone.utc)
    cutoff_1 = (now - timedelta(days=config["followup_1_days"])).isoformat()
    cutoff_2 = (now - timedelta(days=config["followup_2_days"])).isoformat()
    cutoff_3 = (now - timedelta(days=config["followup_3_days"])).isoformat()

    db = get_db()

    try:
        due_1 = (
            db.table("leads")
            .select("*")
            .eq("outreach_status", "emailed_1")
            .eq("follow_up_count", 0)
            .eq("replied", False)
            .eq("opted_out", False)
            .lte("last_emailed_at", cutoff_1)
            .not_.is_("email", "null")
            .execute()
        ).data or []

        due_2 = (
            db.table("leads")
            .select("*")
            .eq("outreach_status", "emailed_2")
            .eq("follow_up_count", 1)
            .eq("replied", False)
            .eq("opted_out", False)
            .lte("last_emailed_at", cutoff_2)
            .not_.is_("email", "null")
            .execute()
        ).data or []

        due_3 = (
            db.table("leads")
            .select("*")
            .eq("outreach_status", "emailed_3")
            .eq("follow_up_count", 2)
            .eq("replied", False)
            .eq("opted_out", False)
            .lte("last_emailed_at", cutoff_3)
            .not_.is_("email", "null")
            .execute()
        ).data or []
    except Exception as e:
        logger.error(f"Follow-up query failed: {e}")
        return

    # Filter out leads whose emails have been opened/clicked (they engaged, don't auto-follow-up)
    sent_count = 0
    for step_leads, step_num in [(due_1, 1), (due_2, 2), (due_3, 3)]:
        for lead in step_leads:
            if daily_count + sent_count >= daily_cap:
                logger.info("Follow-up stopped: daily cap reached mid-run")
                break

            # Check if any email for this lead was opened or clicked
            try:
                email_statuses = (
                    db.table("email_outreach")
                    .select("status")
                    .eq("lead_id", lead["id"])
                    .in_("status", ["opened", "clicked"])
                    .execute()
                ).data or []
                if email_statuses:
                    logger.debug(f"Skipping follow-up for {lead['business_name']}: email was opened/clicked")
                    continue
            except Exception:
                pass

            await _send_followup(db, lead, follow_up_number=step_num)
            sent_count += 1

    if sent_count:
        logger.info(f"Follow-up run complete: {sent_count} emails sent")


async def _send_followup(db, lead: dict, follow_up_number: int) -> None:
    import asyncio
    from app.services.email_generator import generate_followup_email
    from app.services.email_sender import send_email
    from datetime import datetime, timezone

    try:
        email_content = await generate_followup_email(
            business_name=lead["business_name"],
            follow_up_number=follow_up_number,
            ai_analysis=lead.get("ai_analysis") or {},
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: send_email(lead["email"], email_content["subject"], email_content["body"]),
        )

        now = datetime.now(timezone.utc).isoformat()

        db.table("email_outreach").insert({
            "lead_id": lead["id"],
            "sequence_step": follow_up_number,
            "subject": email_content["subject"],
            "body": email_content["body"],
            "sent_at": now if result["status"] == "sent" else None,
            "resend_id": result["id"],
            "status": result["status"],
            "error_message": result["error"],
        }).execute()

        if result["status"] == "sent":
            db.table("leads").update({
                "outreach_status": f"emailed_{follow_up_number + 1}",
                "last_emailed_at": now,
                "follow_up_count": follow_up_number,
            }).eq("id", lead["id"]).execute()
            logger.info(f"Follow-up {follow_up_number} sent to {lead['business_name']} ({lead['email']})")
        else:
            logger.warning(f"Follow-up {follow_up_number} failed for {lead['business_name']}: {result['error']}")
    except Exception as e:
        logger.error(f"Follow-up {follow_up_number} error for lead {lead['id']}: {e}")


def register_smart_outreach_job() -> None:
    """Register interval job that auto-sends initial outreach to high-score leads every 4 hours."""
    scheduler_instance.add_job(
        _run_smart_outreach,
        trigger="interval",
        hours=4,
        id="smart_outreach",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info("Registered smart outreach job (every 4 hours)")


async def _run_smart_outreach() -> None:
    from app.database import get_db
    from app.services.outreach_engine import (
        get_outreach_config,
        get_daily_send_count,
        send_outreach_to_lead,
    )

    config = await get_outreach_config()
    if not config["smart_schedule_enabled"]:
        return

    daily_count = await get_daily_send_count()
    daily_cap = config["max_per_day"]
    remaining = daily_cap - daily_count
    if remaining <= 0:
        logger.info("Smart outreach skipped: daily cap reached")
        return

    # Cap per run to avoid monopolizing sends (leave room for follow-ups and manual sends)
    batch_size = min(remaining, 25)

    db = get_db()
    try:
        result = (
            db.table("leads")
            .select("*")
            .eq("outreach_status", "idle")
            .eq("replied", False)
            .eq("opted_out", False)
            .gte("score", config["min_score_auto"])
            .not_.is_("email", "null")
            .order("score", desc=True)
            .limit(batch_size)
            .execute()
        )
        leads = result.data or []
    except Exception as e:
        logger.error(f"Smart outreach query failed: {e}")
        return

    if not leads:
        return

    sent = 0
    for lead in leads:
        try:
            send_result = await send_outreach_to_lead(lead)
            if send_result.get("success"):
                sent += 1
                # Rate limit: ~50/hr = one every 72 seconds
                import asyncio
                await asyncio.sleep(72)
        except Exception as e:
            logger.error(f"Smart outreach failed for {lead['business_name']}: {e}")

    if sent:
        logger.info(f"Smart outreach sent {sent} initial emails to high-score leads")


async def load_schedules_from_db() -> None:
    """On startup, load all enabled schedules from Supabase and register them."""
    from app.database import get_db

    try:
        result = get_db().table("search_schedules").select("*").eq("enabled", True).execute()
        for row in result.data:
            add_schedule_job(row)
        logger.info(f"Loaded {len(result.data)} schedule(s) from DB")
    except Exception as e:
        logger.error(f"Could not load schedules from DB: {e}")

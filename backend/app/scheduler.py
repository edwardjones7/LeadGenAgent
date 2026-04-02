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

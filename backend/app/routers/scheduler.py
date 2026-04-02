from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.scheduler import add_schedule_job, remove_schedule_job

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    name: str
    location: str
    categories: list[str]
    cron_expression: str  # standard 5-part cron, e.g. "0 8 * * *" for 8am daily
    enabled: bool = True


class ScheduleToggle(BaseModel):
    enabled: bool


@router.get("")
def list_schedules():
    db = get_db()
    result = db.table("search_schedules").select("*").order("created_at", desc=True).execute()
    return result.data


@router.post("", status_code=201)
def create_schedule(body: ScheduleCreate):
    db = get_db()
    result = db.table("search_schedules").insert({
        "name": body.name,
        "location": body.location,
        "categories": body.categories,
        "cron_expression": body.cron_expression,
        "enabled": body.enabled,
    }).execute()
    row = result.data[0]
    if row["enabled"]:
        add_schedule_job(row)
    return row


@router.patch("/{schedule_id}")
def toggle_schedule(schedule_id: str, body: ScheduleToggle):
    db = get_db()
    result = db.table("search_schedules").update({"enabled": body.enabled}).eq("id", schedule_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Schedule not found")
    row = result.data[0]
    if body.enabled:
        add_schedule_job(row)
    else:
        remove_schedule_job(schedule_id)
    return row


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str):
    db = get_db()
    remove_schedule_job(schedule_id)
    db.table("search_schedules").delete().eq("id", schedule_id).execute()
    return {"ok": True}

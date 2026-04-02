import csv
import io
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.models.lead import LeadUpdate

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("")
def list_leads(
    status: str | None = Query(None),
    category: str | None = Query(None),
    min_score: int | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    limit: int = Query(50),
    offset: int = Query(0),
):
    db = get_db()
    q = db.table("leads").select("*")

    if status:
        q = q.eq("status", status)
    if category:
        q = q.eq("category", category)
    if min_score is not None:
        q = q.gte("score", min_score)

    ascending = sort_dir.lower() == "asc"
    q = q.order(sort_by, desc=not ascending)
    q = q.range(offset, offset + limit - 1)

    result = q.execute()
    return result.data


@router.get("/export")
def export_leads(
    status: str | None = Query(None),
    category: str | None = Query(None),
    min_score: int | None = Query(None),
):
    db = get_db()
    q = db.table("leads").select("*").order("score", desc=True)

    if status:
        q = q.eq("status", status)
    if category:
        q = q.eq("category", category)
    if min_score is not None:
        q = q.gte("score", min_score)

    result = q.execute()
    leads = result.data

    output = io.StringIO()
    fieldnames = [
        "business_name", "city", "state", "phone", "email",
        "website_url", "score", "score_reason", "status", "category", "source", "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(leads)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=elenos_leads.csv"},
    )


@router.get("/{lead_id}")
def get_lead(lead_id: str):
    db = get_db()
    result = db.table("leads").select("*").eq("id", lead_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result.data


@router.patch("/{lead_id}")
def update_lead(lead_id: str, update: LeadUpdate):
    db = get_db()
    data = update.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = db.table("leads").update(data).eq("id", lead_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result.data[0]


@router.delete("/{lead_id}")
def delete_lead(lead_id: str):
    db = get_db()
    db.table("leads").delete().eq("id", lead_id).execute()
    return {"ok": True}

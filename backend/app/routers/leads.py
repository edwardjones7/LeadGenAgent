import csv
import io
import json
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


@router.post("/find-emails/stream")
async def find_emails_stream(limit: int = Query(20)):
    """Stream email-finding progress as SSE events."""
    from app.services.email_extractor import find_email_for_lead

    async def event_generator():
        db = get_db()
        result = (
            db.table("leads")
            .select("id,business_name,city,state,phone,website_url,email")
            .is_("email", "null")
            .order("score", desc=True)
            .limit(limit)
            .execute()
        )
        leads = result.data or []

        if not leads:
            yield f"data: {json.dumps({'type': 'log', 'message': 'All leads already have emails!'})}\n\n"
            yield f"data: {json.dumps({'type': 'result', 'found': 0, 'total': 0})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'log', 'message': f'Found {len(leads)} leads without emails. Starting search...'})}\n\n"

        found_count = 0
        for i, lead in enumerate(leads):
            yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': len(leads), 'message': f'Searching for {lead[\"business_name\"]}...'})}\n\n"

            try:
                result = await find_email_for_lead(
                    business_name=lead["business_name"],
                    city=lead["city"],
                    state=lead["state"],
                    website_url=lead.get("website_url"),
                    phone=lead.get("phone"),
                )
                if result["email"]:
                    db.table("leads").update({"email": result["email"]}).eq("id", lead["id"]).execute()
                    found_count += 1
                    yield f"data: {json.dumps({'type': 'found', 'business': lead['business_name'], 'email': result['email'], 'source': result['source']})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'log', 'message': f'No email found for {lead[\"business_name\"]}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'log', 'message': f'Error searching {lead[\"business_name\"]}: {str(e)[:100]}'})}\n\n"

        yield f"data: {json.dumps({'type': 'result', 'found': found_count, 'total': len(leads), 'message': f'Done — found {found_count}/{len(leads)} emails'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.lead import SearchRequest, SearchResponse
from app.services.lead_processor import run_search, run_search_stream
from app.database import get_db
from app.services.search_queue import enqueue_search, get_queue, get_logs, cancel_search, stop_search, remove_search, clear_finished, stream_logs

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def trigger_search(request: SearchRequest):
    return await run_search(request.location, request.categories)


@router.post("/stream")
async def trigger_search_stream(request: SearchRequest):
    """Stream search progress as Server-Sent Events."""

    async def event_generator():
        async for event in run_search_stream(request.location, request.categories):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Search Queue ──

@router.post("/queue")
async def queue_search(request: SearchRequest):
    """Add a search to the background queue."""
    entry = await enqueue_search(request.location, request.categories)
    return entry


@router.get("/queue")
def list_queue():
    """List all queued/running/completed searches."""
    return get_queue()


@router.get("/queue/{queue_id}/logs")
async def stream_queue_logs(queue_id: str):
    """Stream logs for a running queue search as SSE."""

    async def event_generator():
        async for event in stream_logs(queue_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/queue/{queue_id}/logs/snapshot")
def get_queue_logs(queue_id: str):
    """Get current logs snapshot for a queue entry (for polling)."""
    return get_logs(queue_id)


@router.post("/queue/clear")
def clear_queue():
    """Remove all finished entries from the queue."""
    count = clear_finished()
    return {"ok": True, "removed": count}


@router.delete("/queue/{queue_id}")
def cancel_queued_search(queue_id: str):
    """Cancel a pending queued search."""
    cancelled = cancel_search(queue_id)
    if not cancelled:
        return {"ok": False, "message": "Search not found or already running"}
    return {"ok": True}


@router.post("/queue/{queue_id}/stop")
def stop_running_search(queue_id: str):
    """Force-stop a running search."""
    stopped = stop_search(queue_id)
    if not stopped:
        return {"ok": False, "message": "Search not found or not running"}
    return {"ok": True}


@router.delete("/queue/{queue_id}/remove")
def remove_queue_entry(queue_id: str):
    """Remove a finished (complete/failed/cancelled) entry from the queue."""
    removed = remove_search(queue_id)
    if not removed:
        return {"ok": False, "message": "Entry not found or still active"}
    return {"ok": True}


@router.post("/clear-leads")
def clear_all_leads():
    """Delete all leads."""
    db = get_db()
    try:
        db.table("leads").delete().gte("created_at", "2000-01-01").execute()
    except Exception:
        pass
    return {"ok": True, "message": "All leads deleted"}

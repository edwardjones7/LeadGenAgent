"""Search queue — background worker that processes queued searches one at a time."""

import asyncio
import logging
from datetime import datetime, timezone

from app.database import get_db

logger = logging.getLogger(__name__)

_queue_event = asyncio.Event()

# In-memory log storage for currently running search — keyed by queue_id
_active_logs: dict[str, list[dict]] = {}
_log_events: dict[str, asyncio.Event] = {}


async def enqueue_search(location: str, categories: list[str]) -> dict:
    """Add a search to the queue table. Returns the new queue entry."""
    db = get_db()
    result = db.table("search_queue").insert({
        "location": location,
        "categories": categories,
        "status": "pending",
    }).execute()
    entry = result.data[0]
    _queue_event.set()  # wake the worker
    return entry


def get_queue() -> list[dict]:
    """List all queue entries, newest first."""
    db = get_db()
    result = (
        db.table("search_queue")
        .select("*")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


def get_logs(queue_id: str) -> list[dict]:
    """Get current in-memory logs for a running search."""
    return _active_logs.get(queue_id, [])


def cancel_search(queue_id: str) -> bool:
    """Cancel a pending search. Returns True if cancelled."""
    db = get_db()
    result = (
        db.table("search_queue")
        .update({"status": "cancelled"})
        .eq("id", queue_id)
        .eq("status", "pending")
        .execute()
    )
    return bool(result.data)


def stop_search(queue_id: str) -> bool:
    """Force-stop a running search by marking it as failed."""
    db = get_db()
    result = (
        db.table("search_queue")
        .update({
            "status": "failed",
            "error": "Manually stopped",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", queue_id)
        .eq("status", "running")
        .execute()
    )
    # Clean up logs
    _active_logs.pop(queue_id, None)
    _log_events.pop(queue_id, None)
    return bool(result.data)


def remove_search(queue_id: str) -> bool:
    """Remove a completed/failed/cancelled entry from the queue."""
    db = get_db()
    result = (
        db.table("search_queue")
        .delete()
        .eq("id", queue_id)
        .in_("status", ["complete", "failed", "cancelled"])
        .execute()
    )
    return bool(result.data)


def clear_finished() -> int:
    """Remove all completed, failed, and cancelled entries. Returns count removed."""
    db = get_db()
    result = (
        db.table("search_queue")
        .delete()
        .in_("status", ["complete", "failed", "cancelled"])
        .execute()
    )
    return len(result.data) if result.data else 0


async def stream_logs(queue_id: str):
    """Async generator that yields log dicts for a running search as they arrive."""
    # Yield any existing logs first
    seen = 0
    for log in _active_logs.get(queue_id, []):
        yield log
        seen += 1

    # Then wait for new ones
    while queue_id in _log_events:
        event = _log_events[queue_id]
        event.clear()
        try:
            await asyncio.wait_for(event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            # Send keepalive
            yield {"type": "keepalive"}
            continue

        # Yield new logs since last seen
        logs = _active_logs.get(queue_id, [])
        while seen < len(logs):
            yield logs[seen]
            seen += 1

    # Yield any final logs
    for log in _active_logs.get(queue_id, [])[seen:]:
        yield log

    yield {"type": "done"}


async def queue_worker():
    """Long-running background task that processes queued searches one at a time."""
    while True:
        await _queue_event.wait()
        _queue_event.clear()

        db = get_db()

        while True:
            # Grab next pending entry
            pending = (
                db.table("search_queue")
                .select("*")
                .eq("status", "pending")
                .order("created_at")
                .limit(1)
                .execute()
            )

            if not pending.data:
                break

            entry = pending.data[0]
            queue_id = entry["id"]

            # Set up log tracking
            _active_logs[queue_id] = []
            _log_events[queue_id] = asyncio.Event()

            # Mark as running
            db.table("search_queue").update({
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", queue_id).execute()

            try:
                from app.services.lead_processor import run_search_stream

                result = None
                async for event in run_search_stream(entry["location"], entry["categories"]):
                    # Check if search was stopped
                    check = db.table("search_queue").select("status").eq("id", queue_id).limit(1).execute()
                    if check.data and check.data[0]["status"] != "running":
                        break

                    # Store log and notify listeners
                    _active_logs[queue_id].append(event)
                    if queue_id in _log_events:
                        _log_events[queue_id].set()

                    # Update progress in DB for polling clients
                    if event.get("type") == "progress":
                        db.table("search_queue").update({
                            "progress": event.get("progress", {}),
                        }).eq("id", queue_id).execute()

                    if event.get("type") == "result":
                        result = event.get("data")

                if result:
                    db.table("search_queue").update({
                        "status": "complete",
                        "result": result,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", queue_id).execute()
                    logger.info(f"Queue search {queue_id} complete: {result['new_leads']} new leads")
                else:
                    # Might have been stopped mid-search
                    check = db.table("search_queue").select("status").eq("id", queue_id).limit(1).execute()
                    if check.data and check.data[0]["status"] == "running":
                        db.table("search_queue").update({
                            "status": "failed",
                            "error": "Search produced no result",
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", queue_id).execute()

            except Exception as e:
                logger.error(f"Queue search {queue_id} failed: {e}")
                db.table("search_queue").update({
                    "status": "failed",
                    "error": str(e)[:500],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", queue_id).execute()

            finally:
                # Clean up — notify any listeners that we're done, then remove
                if queue_id in _log_events:
                    _log_events[queue_id].set()
                _log_events.pop(queue_id, None)
                # Keep logs briefly for clients to catch up
                await asyncio.sleep(5)
                _active_logs.pop(queue_id, None)

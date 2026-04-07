"""Chat endpoint — SSE streaming responses from the agent."""

import json
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any

from app.database import get_db
from agent.chat_agent import chat_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


@router.post("")
async def send_message(req: ChatRequest):
    """Stream a chat response as Server-Sent Events."""

    async def event_generator():
        async for event in chat_stream(req.message, req.context):
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


@router.get("/history")
def get_history(limit: int = Query(50)):
    """Load recent chat messages for display."""
    db = get_db()
    try:
        result = (
            db.table("chat_messages")
            .select("id,role,content,tool_calls,tool_call_id,created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        rows.reverse()  # chronological
        return rows
    except Exception:
        return []


@router.delete("/history")
def clear_history():
    """Clear all chat messages."""
    db = get_db()
    try:
        db.table("chat_messages").delete().gte("created_at", "2000-01-01").execute()
    except Exception:
        pass
    return {"ok": True}

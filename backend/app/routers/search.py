import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.lead import SearchRequest, SearchResponse
from app.services.lead_processor import run_search, run_search_stream

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

from fastapi import APIRouter
from app.models.lead import SearchRequest, SearchResponse
from app.services.lead_processor import run_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def trigger_search(request: SearchRequest):
    return await run_search(request.location, request.categories)

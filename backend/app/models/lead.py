from pydantic import BaseModel
from typing import Any
from datetime import datetime


class Lead(BaseModel):
    id: str | None = None
    business_name: str
    city: str
    state: str
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    score: int = 0
    score_reason: str | None = None
    status: str = "New"
    category: str | None = None
    source: str | None = None
    raw_data: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeadUpdate(BaseModel):
    status: str | None = None
    email: str | None = None


class SearchRequest(BaseModel):
    location: str
    categories: list[str]
    limit: int = 50


class SearchResponse(BaseModel):
    run_id: str
    new_leads: int
    dupes_skipped: int
    leads: list[Lead]

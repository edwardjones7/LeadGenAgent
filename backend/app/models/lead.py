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
    ai_analysis: dict[str, Any] | None = None
    outreach_status: str = "idle"
    last_emailed_at: datetime | None = None
    follow_up_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeadUpdate(BaseModel):
    business_name: str | None = None
    city: str | None = None
    state: str | None = None
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    category: str | None = None
    status: str | None = None
    outreach_status: str | None = None


class ManualLeadCreate(BaseModel):
    business_name: str
    city: str
    state: str
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    category: str | None = None


class ChatMessage(BaseModel):
    id: str | None = None
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    context: dict[str, Any] | None = None
    created_at: datetime | None = None


class ChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


class OutreachSendRequest(BaseModel):
    dry_run: bool = False


class EmailRecord(BaseModel):
    id: str
    lead_id: str
    sequence_step: int
    subject: str
    body: str
    sent_at: datetime | None = None
    resend_id: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime | None = None


class WebsiteSpec(BaseModel):
    business_name: str
    tagline: str
    hero_headline: str
    hero_subheadline: str
    sections: list[dict[str, Any]]
    color_palette: dict[str, str]
    design_direction: str
    seo_title: str
    meta_description: str
    suggested_domain: str


class SearchRequest(BaseModel):
    location: str
    categories: list[str]
    limit: int = 50


class SearchResponse(BaseModel):
    run_id: str
    new_leads: int
    dupes_skipped: int
    leads: list[Lead]

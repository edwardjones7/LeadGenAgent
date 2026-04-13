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
    replied: bool = False
    replied_at: datetime | None = None
    opted_out: bool = False
    # Deep research fields
    contact_name: str | None = None
    contact_title: str | None = None
    additional_phones: list[str] | None = None
    additional_emails: list[str] | None = None
    social_links: dict[str, str] | None = None
    business_hours: str | None = None
    rating: float | None = None
    review_count: int | None = None
    years_in_business: int | None = None
    bbb_accredited: bool | None = None
    yelp_categories: list[str] | None = None
    address: str | None = None
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
    opted_out: bool | None = None
    contact_name: str | None = None
    contact_title: str | None = None
    additional_phones: list[str] | None = None
    additional_emails: list[str] | None = None
    social_links: dict[str, str] | None = None


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
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
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


class OutreachConfig(BaseModel):
    id: str | None = None
    max_per_hour: int = 50
    max_per_day: int = 200
    followup_1_days: int = 3
    followup_2_days: int = 5
    followup_3_days: int = 7
    smart_schedule_enabled: bool = False
    min_score_auto: int = 7
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueueEntry(BaseModel):
    id: str | None = None
    location: str
    categories: list[str]
    status: str = "pending"
    progress: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SearchRequest(BaseModel):
    location: str
    categories: list[str]
    limit: int = 50


class SearchResponse(BaseModel):
    run_id: str
    new_leads: int
    dupes_skipped: int
    leads: list[Lead]

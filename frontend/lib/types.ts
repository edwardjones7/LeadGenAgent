export type LeadStatus = "New" | "Contacted" | "Closed";

export type OutreachStatus =
  | "idle"
  | "analyzing"
  | "queued"
  | "emailed_1"
  | "emailed_2"
  | "emailed_3"
  | "bounced"
  | "opted_out";

export interface AiAnalysis {
  summary: string;
  business_overview?: string;
  opportunity?: string;
  problems: { category: string; description: string }[];
  severity: "low" | "medium" | "high";
  personalization_hooks: string[];
  gap_analysis?: {
    missing_pages?: string[];
    missing_trust_signals?: string[];
    cta_quality?: string;
    contact_accessibility?: string;
  } | null;
}

export interface EmailRecord {
  id: string;
  lead_id: string;
  sequence_step: number;
  subject: string;
  body: string;
  sent_at: string | null;
  resend_id: string | null;
  status: "pending" | "sent" | "failed" | "opened";
  error_message: string | null;
  created_at: string;
}

export interface WebsiteSpec {
  business_name: string;
  project_title?: string;
  overview?: string;
  objectives?: string[];
  target_audience?: { primary?: string[]; secondary?: string[] };
  user_personas?: { name: string; bio?: string; needs?: string[] }[];
  core_features?: { section: string; purpose?: string; components?: string[] }[];
  design?: {
    style_direction?: string;
    color_palette?: Record<string, string>;
    typography?: string;
    ui_notes?: string[];
  };
  ux_requirements?: string[];
  technical_requirements?: {
    recommended_platform?: string;
    integrations?: string[];
    hosting?: string;
  };
  success_metrics?: string[];
  future_enhancements?: string[];
  sitemap?: string[];
  copy_tone?: string[];
  key_differentiator?: string;

  // Legacy / homepage-level fields
  tagline: string;
  hero_headline: string;
  hero_subheadline: string;
  sections: { name: string; headline: string; body_copy: string; cta_text: string | null }[];
  color_palette?: Record<string, string>;
  design_direction?: string;
  seo_title: string;
  meta_description: string;
  suggested_domain: string;
}

export interface Lead {
  id: string;
  business_name: string;
  city: string;
  state: string;
  phone: string | null;
  email: string | null;
  website_url: string | null;
  score: number;
  score_reason: string | null;
  status: LeadStatus;
  category: string | null;
  source: string | null;
  ai_analysis: AiAnalysis | null;
  outreach_status: OutreachStatus;
  last_emailed_at: string | null;
  follow_up_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface SearchRequest {
  location: string;
  categories: string[];
}

export interface SearchResponse {
  run_id: string;
  new_leads: number;
  dupes_skipped: number;
  leads: Lead[];
}

/* ── Chat ── */

export interface ChatToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_calls?: ChatToolCall[];
  tool_call_id?: string;
  created_at?: string;
}

export interface QueueEntry {
  id: string;
  location: string;
  categories: string[];
  status: "pending" | "running" | "complete" | "failed" | "cancelled";
  progress: { current: number; total: number } | null;
  result: SearchResponse | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface PageContext {
  selected_lead: Lead | null;
  visible_lead_ids: string[];
  filters: {
    status?: string;
    min_score?: number;
  };
  search_state: {
    location: string;
    categories: string[];
  };
}

export interface SearchLogEntry {
  type: "log" | "progress" | "result" | "error";
  stage: string;
  message: string;
  detail?: Record<string, unknown>;
  progress?: { current: number; total: number };
  data?: SearchResponse;
}

export interface ChatSSEEvent {
  type: "chunk" | "tool_call" | "tool_result" | "done";
  content?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown>;
}

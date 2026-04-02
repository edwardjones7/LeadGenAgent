export type LeadStatus = "New" | "Contacted" | "Closed";

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

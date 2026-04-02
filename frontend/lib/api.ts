import type { Lead, SearchRequest, SearchResponse } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  getLeads(params?: {
    status?: string;
    category?: string;
    min_score?: number;
    sort_by?: string;
    sort_dir?: string;
    limit?: number;
    offset?: number;
  }): Promise<Lead[]> {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined) qs.set(k, String(v));
      });
    }
    const query = qs.toString() ? `?${qs}` : "";
    return request<Lead[]>(`/api/leads${query}`);
  },

  getLead(id: string): Promise<Lead> {
    return request<Lead>(`/api/leads/${id}`);
  },

  updateLead(id: string, data: { status?: string; email?: string }): Promise<Lead> {
    return request<Lead>(`/api/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  deleteLead(id: string): Promise<void> {
    return request<void>(`/api/leads/${id}`, { method: "DELETE" });
  },

  triggerSearch(data: SearchRequest): Promise<SearchResponse> {
    return request<SearchResponse>("/api/search", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  exportUrl(params?: { status?: string; category?: string; min_score?: number }): string {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined) qs.set(k, String(v));
      });
    }
    const query = qs.toString() ? `?${qs}` : "";
    return `${BASE}/api/leads/export${query}`;
  },
};

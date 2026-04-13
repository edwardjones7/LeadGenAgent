import type { Lead, SearchRequest, SearchResponse, EmailRecord, WebsiteSpec, AiAnalysis, ChatMessage, PageContext, QueueEntry } from "./types";

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

  updateLead(id: string, data: { status?: string; email?: string; outreach_status?: string }): Promise<Lead> {
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

  analyzeOutreach(leadId: string): Promise<{ lead_id: string; ai_analysis: AiAnalysis; outreach_status: string }> {
    return request(`/api/outreach/${leadId}/analyze`, { method: "POST" });
  },

  sendOutreach(
    leadId: string,
    dryRun = false,
  ): Promise<{
    lead_id: string;
    email_id: string | null;
    resend_id: string | null;
    status: string;
    subject: string;
    body: string;
    dry_run: boolean;
    error?: string | null;
  }> {
    return request(`/api/outreach/${leadId}/send`, {
      method: "POST",
      body: JSON.stringify({ dry_run: dryRun }),
    });
  },

  getEmailHistory(leadId: string): Promise<EmailRecord[]> {
    return request(`/api/outreach/${leadId}/emails`);
  },

  generateWebsiteSpec(leadId: string): Promise<WebsiteSpec> {
    return request(`/api/outreach/${leadId}/generate-site`, { method: "POST" });
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

  /* ── Clear All ── */

  clearAllLeads(): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>("/api/search/clear-leads", { method: "POST" });
  },

  /* ── Search Queue ── */

  queueSearch(data: SearchRequest): Promise<QueueEntry> {
    return request<QueueEntry>("/api/search/queue", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  getSearchQueue(): Promise<QueueEntry[]> {
    return request<QueueEntry[]>("/api/search/queue");
  },

  cancelQueuedSearch(id: string): Promise<void> {
    return request<void>(`/api/search/queue/${id}`, { method: "DELETE" });
  },

  stopRunningSearch(id: string): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/api/search/queue/${id}/stop`, { method: "POST" });
  },

  removeQueueEntry(id: string): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>(`/api/search/queue/${id}/remove`, { method: "DELETE" });
  },

  clearFinishedSearches(): Promise<{ ok: boolean; removed: number }> {
    return request<{ ok: boolean; removed: number }>("/api/search/queue/clear", { method: "POST" });
  },

  streamQueueLogs(id: string): Promise<Response> {
    return fetch(`${BASE}/api/search/queue/${id}/logs`);
  },

  /* ── Email Finder ── */

  findEmailsStream(limit = 20): Promise<Response> {
    return fetch(`${BASE}/api/leads/find-emails/stream?limit=${limit}`, {
      method: "POST",
    });
  },

  /* ── Chat ── */

  searchStream(data: SearchRequest): Promise<Response> {
    return fetch(`${BASE}/api/search/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  },

  sendChatMessage(message: string, context: PageContext): Promise<Response> {
    return fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context }),
    });
  },

  getChatHistory(limit = 50): Promise<ChatMessage[]> {
    return request<ChatMessage[]>(`/api/chat/history?limit=${limit}`);
  },

  clearChatHistory(): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>("/api/chat/history", { method: "DELETE" });
  },
};

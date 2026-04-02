"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { Lead } from "@/lib/types";

export function useLeads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getLeads({ sort_by: "score", sort_dir: "desc", limit: 200 });
      setLeads(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch leads");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const updateLead = useCallback(async (id: string, data: { status?: string; email?: string }) => {
    const updated = await api.updateLead(id, data);
    setLeads((prev) => prev.map((l) => (l.id === id ? updated : l)));
    return updated;
  }, []);

  const deleteLead = useCallback(async (id: string) => {
    await api.deleteLead(id);
    setLeads((prev) => prev.filter((l) => l.id !== id));
  }, []);

  const addLeads = useCallback((newLeads: Lead[]) => {
    setLeads((prev) => {
      const existingIds = new Set(prev.map((l) => l.id));
      const toAdd = newLeads.filter((l) => !existingIds.has(l.id));
      return [...toAdd, ...prev];
    });
  }, []);

  return { leads, loading, error, fetchLeads, updateLead, deleteLead, addLeads };
}

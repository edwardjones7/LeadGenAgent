"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

export function useSearch() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<SearchResponse | null>(null);

  const runSearch = async (location: string, categories: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.triggerSearch({ location, categories });
      setLastResult(result);
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Search failed";
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { loading, error, lastResult, runSearch };
}

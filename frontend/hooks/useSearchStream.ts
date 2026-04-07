"use client";

import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { SearchLogEntry, SearchResponse } from "@/lib/types";

export function useSearchStream() {
  const [logs, setLogs] = useState<SearchLogEntry[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async (location: string, categories: string[]) => {
    setIsSearching(true);
    setLogs([]);
    setProgress(null);
    setResult(null);
    setError(null);

    try {
      const res = await api.searchStream({ location, categories });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`API ${res.status}: ${errText}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult: SearchResponse | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event: SearchLogEntry;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          if (event.type === "result") {
            finalResult = event.data ?? null;
            setResult(finalResult);
          } else {
            setLogs((prev) => [...prev, event]);
            if (event.progress) {
              setProgress(event.progress);
            }
          }
        }
      }

      return finalResult;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Search failed";
      setError(msg);
      return null;
    } finally {
      setIsSearching(false);
      setProgress(null);
    }
  }, []);

  const clearLogs = useCallback(() => {
    setLogs([]);
    setResult(null);
    setError(null);
  }, []);

  return { logs, isSearching, progress, result, error, runSearch, clearLogs };
}

"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { QueueEntry, SearchRequest } from "@/lib/types";

export function useSearchQueue(onComplete?: () => void) {
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevActiveRef = useRef<Set<string>>(new Set());

  const fetchQueue = useCallback(async () => {
    try {
      const data = await api.getSearchQueue();
      setQueue(data);

      const currentActive = new Set(
        data.filter((e) => e.status === "pending" || e.status === "running").map((e) => e.id)
      );
      const prevActive = prevActiveRef.current;

      let justCompleted = false;
      for (const id of prevActive) {
        if (!currentActive.has(id)) {
          const entry = data.find((e) => e.id === id);
          if (entry && entry.status === "complete") {
            justCompleted = true;
          }
        }
      }

      prevActiveRef.current = currentActive;

      if (justCompleted && onComplete) {
        onComplete();
      }

      return data;
    } catch {
      return [];
    }
  }, [onComplete]);

  const enqueue = useCallback(async (data: SearchRequest) => {
    setLoading(true);
    try {
      const entry = await api.queueSearch(data);
      await fetchQueue();
      return entry;
    } finally {
      setLoading(false);
    }
  }, [fetchQueue]);

  const cancel = useCallback(async (id: string) => {
    try {
      await api.cancelQueuedSearch(id);
      await fetchQueue();
    } catch { /* ignore */ }
  }, [fetchQueue]);

  const stop = useCallback(async (id: string) => {
    try {
      await api.stopRunningSearch(id);
      await fetchQueue();
    } catch { /* ignore */ }
  }, [fetchQueue]);

  const remove = useCallback(async (id: string) => {
    try {
      await api.removeQueueEntry(id);
      await fetchQueue();
    } catch { /* ignore */ }
  }, [fetchQueue]);

  const clearFinished = useCallback(async () => {
    try {
      await api.clearFinishedSearches();
      await fetchQueue();
    } catch { /* ignore */ }
  }, [fetchQueue]);

  // Poll while there are active entries. We key the effect on a boolean (not
  // the whole queue) so it only re-runs on the active→idle transitions —
  // otherwise every fetchQueue update would tear down and fail to rebuild the
  // interval, killing polling after the first tick.
  const hasActive = queue.some((e) => e.status === "pending" || e.status === "running");
  useEffect(() => {
    if (!hasActive) return;
    const id = setInterval(fetchQueue, 3000);
    intervalRef.current = id;
    return () => {
      clearInterval(id);
      intervalRef.current = null;
    };
  }, [hasActive, fetchQueue]);

  // Initial load
  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const activeCount = queue.filter((e) => e.status === "pending" || e.status === "running").length;

  return { queue, activeCount, loading, enqueue, cancel, stop, remove, clearFinished, fetchQueue };
}

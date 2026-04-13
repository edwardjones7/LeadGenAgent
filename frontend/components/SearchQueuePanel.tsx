"use client";

import { useRef, useEffect, useState } from "react";
import { Loader2, CheckCircle2, XCircle, Clock, X, Trash2, Square, Eraser, ChevronDown, ChevronRight } from "lucide-react";
import clsx from "clsx";
import type { QueueEntry, SearchLogEntry } from "@/lib/types";
import { api } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  queue: QueueEntry[];
  onCancel: (id: string) => void;
  onStop: (id: string) => void;
  onRemove: (id: string) => void;
  onClearFinished: () => void;
  onRefresh: () => void;
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  pending: {
    icon: <Clock size={12} />,
    color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    label: "Queued",
  },
  running: {
    icon: <Loader2 size={12} className="animate-spin" />,
    color: "text-[#c060ff] bg-[#a200ff]/10 border-[#a200ff]/20",
    label: "Running",
  },
  complete: {
    icon: <CheckCircle2 size={12} />,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    label: "Complete",
  },
  failed: {
    icon: <XCircle size={12} />,
    color: "text-red-400 bg-red-500/10 border-red-500/20",
    label: "Failed",
  },
  cancelled: {
    icon: <X size={12} />,
    color: "text-zinc-500 bg-zinc-500/10 border-zinc-500/20",
    label: "Cancelled",
  },
};

const STAGE_COLORS: Record<string, string> = {
  yelp: "bg-red-500/20 text-red-400 border-red-500/30",
  yellowpages: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  bbb: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  manta: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  superpages: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  dedup: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/30",
  enrich: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/30",
  research: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/30",
  collect: "bg-zinc-700/40 text-zinc-400 border-zinc-600/30",
  done: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function QueueLogStream({ queueId }: { queueId: string }) {
  const [logs, setLogs] = useState<SearchLogEntry[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();

    (async () => {
      try {
        const resp = await api.streamQueueLogs(queueId);
        const reader = resp.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          if (controller.signal.aborted) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const event = JSON.parse(line.slice(6));
                if (event.type === "done" || event.type === "keepalive") continue;
                setLogs((prev) => [...prev, event]);
              } catch { /* skip */ }
            }
          }
        }
      } catch { /* stream ended */ }
    })();

    return () => { controller.abort(); };
  }, [queueId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [logs]);

  const progress = logs.findLast((l) => l.progress)?.progress;

  return (
    <div className="flex flex-col">
      {progress && (
        <div className="px-3 py-1.5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-zinc-500 font-mono">{progress.current}/{progress.total}</span>
          </div>
          <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[#a200ff] to-[#c060ff] rounded-full transition-all duration-300"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}
      <div ref={scrollRef} className="max-h-[200px] overflow-y-auto px-3 py-1 space-y-0.5">
        {logs.filter((l) => l.type === "log" || l.type === "progress").map((log, i) => (
          <div key={i} className="flex items-start gap-1.5 py-0.5">
            <span className={clsx(
              "shrink-0 text-[8px] font-mono px-1 py-0.5 rounded border mt-0.5 leading-none",
              STAGE_COLORS[log.stage] ?? STAGE_COLORS.collect
            )}>
              {log.stage}
            </span>
            <span className="text-[11px] text-zinc-500 leading-relaxed">{log.message}</span>
          </div>
        ))}
        {logs.length === 0 && (
          <div className="flex items-center gap-2 py-3 text-zinc-600 text-[11px]">
            <Loader2 size={11} className="animate-spin text-[#a200ff]" />
            Starting search...
          </div>
        )}
      </div>
    </div>
  );
}

export function SearchQueuePanel({ open, onClose, queue, onCancel, onStop, onRemove, onClearFinished, onRefresh }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const runningEntry = queue.find((e) => e.status === "running");
  const activeExpandedId = expandedId ?? runningEntry?.id ?? null;

  if (!open) return null;

  const hasFinished = queue.some((e) => e.status === "complete" || e.status === "failed" || e.status === "cancelled");

  return (
    <div className="fixed top-12 right-4 z-40 w-[420px] max-h-[560px] flex flex-col bg-[#0c0c14] border border-zinc-800/80 rounded-xl shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-zinc-800/60">
        <span className="text-xs font-semibold text-zinc-200">Search Queue</span>
        <div className="flex items-center gap-1">
          {hasFinished && (
            <button
              onClick={onClearFinished}
              className="flex items-center gap-1 px-2 py-1 rounded text-[10px] text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
              title="Clear finished"
            >
              <Eraser size={11} />
              Clear
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-zinc-300 transition-colors"
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {/* Queue list */}
      <div className="flex-1 overflow-y-auto">
        {queue.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-zinc-600 text-xs gap-2">
            <Clock size={18} className="text-zinc-700" />
            <p>No searches queued</p>
            <p className="text-[10px] text-zinc-700">Use &quot;Queue Search&quot; to add background searches</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/40">
            {queue.map((entry) => {
              const config = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.pending;
              const cats = Array.isArray(entry.categories) ? entry.categories : [];
              const isExpanded = activeExpandedId === entry.id && entry.status === "running";

              return (
                <div key={entry.id} className="hover:bg-zinc-800/20 transition-colors">
                  <div
                    className={clsx("px-4 py-3", entry.status === "running" && "cursor-pointer")}
                    onClick={() => entry.status === "running" && setExpandedId(isExpanded ? "__none__" : entry.id)}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={clsx(
                            "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border",
                            config.color
                          )}>
                            {config.icon}
                            {config.label}
                          </span>
                          <span className="text-[10px] text-zinc-600">{timeAgo(entry.created_at)}</span>
                          {entry.status === "running" && (
                            isExpanded
                              ? <ChevronDown size={10} className="text-zinc-600" />
                              : <ChevronRight size={10} className="text-zinc-600" />
                          )}
                        </div>
                        <p className="text-xs text-zinc-300 font-medium truncate">{entry.location}</p>
                        <p className="text-[10px] text-zinc-600 truncate mt-0.5">
                          {cats.length} {cats.length === 1 ? "category" : "categories"}
                          {cats.length <= 3 && cats.length > 0 && `: ${cats.join(", ")}`}
                        </p>

                        {entry.status === "complete" && entry.result && (
                          <p className="text-[10px] text-emerald-500 mt-1">
                            {(entry.result as { new_leads?: number }).new_leads ?? 0} new leads found
                          </p>
                        )}
                        {entry.status === "failed" && entry.error && (
                          <p className="text-[10px] text-red-400 mt-1 truncate">{entry.error}</p>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div className="flex items-center gap-0.5 shrink-0">
                        {entry.status === "pending" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onCancel(entry.id); }}
                            className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400 transition-colors"
                            title="Cancel"
                          >
                            <Trash2 size={11} />
                          </button>
                        )}
                        {entry.status === "running" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onStop(entry.id); }}
                            className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-red-400 transition-colors"
                            title="Stop"
                          >
                            <Square size={11} />
                          </button>
                        )}
                        {(entry.status === "complete" || entry.status === "failed" || entry.status === "cancelled") && (
                          <button
                            onClick={(e) => { e.stopPropagation(); onRemove(entry.id); }}
                            className="p-1 rounded hover:bg-zinc-800 text-zinc-600 hover:text-zinc-400 transition-colors"
                            title="Remove"
                          >
                            <X size={11} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Log stream for running search */}
                  {isExpanded && (
                    <div className="border-t border-zinc-800/40 bg-zinc-900/30">
                      <QueueLogStream queueId={entry.id} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

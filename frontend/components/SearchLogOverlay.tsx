"use client";

import { useRef, useEffect } from "react";
import { X, Loader2, CheckCircle2 } from "lucide-react";
import clsx from "clsx";
import type { SearchLogEntry, SearchResponse } from "@/lib/types";

interface Props {
  logs: SearchLogEntry[];
  isSearching: boolean;
  progress: { current: number; total: number } | null;
  result: SearchResponse | null;
  error: string | null;
  onClose: () => void;
}

const STAGE_COLORS: Record<string, string> = {
  yelp: "bg-red-500/20 text-red-400 border-red-500/30",
  yellowpages: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  bbb: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  manta: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  superpages: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
  dedup: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/30",
  enrich: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/30",
  score: "bg-[#a200ff]/20 text-[#c060ff] border-[#a200ff]/30",
  collect: "bg-zinc-700/40 text-zinc-400 border-zinc-600/30",
  done: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
};

export function SearchLogOverlay({ logs, isSearching, progress, result, error, onClose }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const done = !isSearching && (result || error);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [logs]);

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-[45] bg-black/30" onClick={done ? onClose : undefined} />

      {/* Card */}
      <div className="fixed inset-0 z-[46] flex items-center justify-center pointer-events-none">
        <div className="pointer-events-auto w-[560px] max-h-[70vh] flex flex-col bg-[#0e0e16] border border-zinc-800 rounded-xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="shrink-0 flex items-center justify-between px-5 py-3.5 border-b border-zinc-800/60">
            <div className="flex items-center gap-3">
              {isSearching ? (
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#a200ff] opacity-75" />
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#a200ff]" />
                </span>
              ) : result ? (
                <CheckCircle2 size={14} className="text-emerald-400" />
              ) : (
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
              )}
              <span className="text-sm font-semibold text-zinc-200">
                {isSearching ? "Search Running" : result ? "Search Complete" : "Search Failed"}
              </span>
            </div>
            {done && (
              <button onClick={onClose} className="text-zinc-600 hover:text-zinc-300 transition-colors p-1 rounded hover:bg-zinc-800">
                <X size={14} />
              </button>
            )}
          </div>

          {/* Logs */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-3 space-y-1 min-h-[200px]">
            {logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2 py-0.5">
                <span className={clsx("shrink-0 text-[9px] font-mono px-1.5 py-0.5 rounded border mt-0.5", STAGE_COLORS[log.stage] ?? STAGE_COLORS.collect)}>
                  {log.stage}
                </span>
                <span className="text-xs text-zinc-400 leading-relaxed">{log.message}</span>
              </div>
            ))}
            {isSearching && logs.length === 0 && (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={20} className="animate-spin text-[#a200ff]" />
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="shrink-0 px-5 py-3 border-t border-zinc-800/60 flex items-center justify-between">
            {progress ? (
              <div className="flex-1 flex items-center gap-3">
                <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#a200ff] rounded-full transition-all duration-300 shadow-[0_0_6px_rgba(162,0,255,0.5)]"
                    style={{ width: `${(progress.current / progress.total) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-zinc-500 font-mono shrink-0">{progress.current}/{progress.total}</span>
              </div>
            ) : result ? (
              <span className="text-xs text-zinc-500">
                <span className="text-[#a200ff] font-semibold">{result.new_leads}</span> new leads · {result.dupes_skipped} skipped
              </span>
            ) : error ? (
              <span className="text-xs text-red-400">{error}</span>
            ) : (
              <span className="text-xs text-zinc-600">Initializing...</span>
            )}
            {done && (
              <button onClick={onClose} className="text-xs text-zinc-500 hover:text-zinc-300 ml-4 transition-colors">
                Dismiss
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

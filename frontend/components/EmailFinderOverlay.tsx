"use client";

import { useState, useRef, useEffect } from "react";
import { X, Mail, Loader2, CheckCircle2, Search, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";

interface LogEntry {
  type: "log" | "progress" | "found" | "result";
  message?: string;
  business?: string;
  email?: string;
  source?: string;
  current?: number;
  total?: number;
  found?: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onComplete: () => void;
}

export function EmailFinderOverlay({ open, onClose, onComplete }: Props) {
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const [result, setResult] = useState<{ found: number; total: number } | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleStart = async () => {
    setRunning(true);
    setLogs([]);
    setProgress(null);
    setResult(null);

    try {
      const res = await api.findEmailsStream(20);
      if (!res.ok) {
        setLogs([{ type: "log", message: `Error: ${res.status}` }]);
        setRunning(false);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

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

          try {
            const event: LogEntry = JSON.parse(raw);
            setLogs((prev) => [...prev, event]);

            if (event.type === "progress" && event.current && event.total) {
              setProgress({ current: event.current, total: event.total });
            }
            if (event.type === "result") {
              setResult({ found: event.found ?? 0, total: event.total ?? 0 });
            }
          } catch {
            continue;
          }
        }
      }

      onComplete();
    } catch (e) {
      setLogs((prev) => [...prev, { type: "log", message: `Error: ${e}` }]);
    } finally {
      setRunning(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[520px] max-h-[80vh] flex flex-col bg-[#0c0c14] border border-zinc-800/80 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-5 py-3.5 border-b border-zinc-800/60">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#a200ff]/15 border border-[#a200ff]/25 flex items-center justify-center">
              <Mail size={13} className="text-[#a200ff]" />
            </div>
            <div>
              <span className="text-sm font-semibold text-zinc-100">Email Finder</span>
              <p className="text-[10px] text-zinc-500">Search websites, Google, Yelp, BBB & more</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-600 hover:text-zinc-300 transition-colors">
            <X size={14} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {logs.length === 0 && !running ? (
            /* Start screen */
            <div className="flex flex-col items-center justify-center py-12 px-6 gap-4">
              <div className="w-14 h-14 rounded-2xl bg-[#a200ff]/10 border border-[#a200ff]/20 flex items-center justify-center">
                <Search size={22} className="text-[#a200ff]" />
              </div>
              <div className="text-center space-y-1">
                <p className="text-sm text-zinc-200 font-medium">Find missing emails</p>
                <p className="text-xs text-zinc-500 max-w-[300px]">
                  Searches up to 20 leads that don't have emails yet. Checks their website, Google, Yelp, BBB, Yellow Pages, and common patterns.
                </p>
              </div>
              <button
                onClick={handleStart}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#a200ff] hover:bg-[#b030ff] text-white text-sm font-medium transition-colors shadow-[0_0_20px_rgba(162,0,255,0.3)]"
              >
                <Mail size={14} />
                Start Email Search
              </button>
            </div>
          ) : (
            /* Logs */
            <>
              {/* Progress bar */}
              {progress && (
                <div className="shrink-0 px-5 py-2.5 border-b border-zinc-800/40 bg-zinc-900/30">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span className="text-zinc-400">
                      {running ? "Searching..." : "Complete"}
                    </span>
                    <span className="text-zinc-500 tabular-nums">
                      {progress.current}/{progress.total}
                    </span>
                  </div>
                  <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-[#a200ff] to-[#c060ff] rounded-full transition-all duration-300"
                      style={{ width: `${(progress.current / progress.total) * 100}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Log entries */}
              <div className="flex-1 overflow-y-auto px-5 py-3 space-y-1.5 min-h-[200px] max-h-[400px]">
                {logs.map((entry, i) => (
                  <LogLine key={i} entry={entry} />
                ))}
                <div ref={logsEndRef} />
              </div>

              {/* Result / actions */}
              <div className="shrink-0 px-5 py-3 border-t border-zinc-800/60 flex items-center justify-between">
                {result ? (
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={14} className="text-emerald-500" />
                    <span className="text-xs text-zinc-300">
                      Found <span className="text-[#a200ff] font-semibold">{result.found}</span> emails out of {result.total} leads
                    </span>
                  </div>
                ) : running ? (
                  <div className="flex items-center gap-2 text-xs text-zinc-500">
                    <Loader2 size={12} className="animate-spin text-[#a200ff]" />
                    Working...
                  </div>
                ) : (
                  <div />
                )}
                <div className="flex gap-2">
                  {!running && logs.length > 0 && (
                    <button
                      onClick={handleStart}
                      className="px-3 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-zinc-200 border border-zinc-800 hover:border-zinc-600 transition-colors"
                    >
                      Run Again
                    </button>
                  )}
                  <button
                    onClick={onClose}
                    className="px-3 py-1.5 rounded-lg text-xs bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition-colors"
                  >
                    Close
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  if (entry.type === "found") {
    return (
      <div className="flex items-start gap-2 text-xs py-1 px-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
        <CheckCircle2 size={12} className="text-emerald-500 mt-0.5 shrink-0" />
        <div>
          <span className="text-emerald-400 font-medium">{entry.business}</span>
          <span className="text-zinc-500 mx-1">&rarr;</span>
          <span className="text-zinc-300 font-mono">{entry.email}</span>
          <span className="text-zinc-600 ml-1.5">via {entry.source}</span>
        </div>
      </div>
    );
  }

  if (entry.type === "progress") {
    return (
      <div className="flex items-center gap-2 text-xs text-zinc-500 py-0.5">
        <Loader2 size={10} className="animate-spin text-[#a200ff] shrink-0" />
        <span>{entry.message}</span>
      </div>
    );
  }

  if (entry.type === "result") {
    return (
      <div className="flex items-center gap-2 text-xs py-1 px-2 rounded-lg bg-[#a200ff]/5 border border-[#a200ff]/10 text-[#c060ff] font-medium mt-1">
        <CheckCircle2 size={12} className="shrink-0" />
        {entry.message}
      </div>
    );
  }

  // Default log
  const isError = entry.message?.toLowerCase().includes("error") || entry.message?.toLowerCase().includes("no email");
  return (
    <div className="flex items-center gap-2 text-xs text-zinc-500 py-0.5">
      {isError ? (
        <AlertCircle size={10} className="text-zinc-600 shrink-0" />
      ) : (
        <span className="w-1 h-1 rounded-full bg-zinc-700 shrink-0 ml-0.5" />
      )}
      <span className={isError ? "text-zinc-600" : ""}>{entry.message}</span>
    </div>
  );
}

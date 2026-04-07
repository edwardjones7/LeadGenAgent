"use client";

import { useState } from "react";
import { Search, Loader2, MapPin, Tag, ChevronDown, X } from "lucide-react";
import clsx from "clsx";
import { NICHE_CATEGORIES } from "@/lib/constants";
import type { SearchResponse } from "@/lib/types";

interface Props {
  open: boolean;
  onClose: () => void;
  onSearch: (location: string, categories: string[]) => Promise<SearchResponse | null>;
  searching: boolean;
  lastResult: SearchResponse | null;
  error: string | null;
}

export function SearchPanel({ open, onClose, onSearch, searching, lastResult, error }: Props) {
  const [location, setLocation] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState(true);

  const toggle = (cat: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(NICHE_CATEGORIES));
  const clearAll = () => setSelected(new Set());

  const handleSubmit = () => {
    if (!location.trim() || selected.size === 0 || searching) return;
    onSearch(location.trim(), Array.from(selected));
  };

  const canRun = location.trim() && selected.size > 0 && !searching;

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-30 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <aside className="fixed inset-y-0 left-0 z-40 w-[360px] flex flex-col bg-[#0c0c12] border-r border-zinc-800/80 shadow-2xl animate-slide-in-left" style={{ willChange: "transform" }}>
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-5 py-4 border-b border-zinc-800/60">
          <div className="flex items-center gap-2">
            <Search size={14} className="text-[#a200ff]" />
            <span className="text-sm font-semibold text-zinc-200">Search Leads</span>
          </div>
          <button onClick={onClose} className="text-zinc-700 hover:text-zinc-300 transition-colors p-1 rounded hover:bg-zinc-800">
            <X size={15} />
          </button>
        </div>

        {/* Location */}
        <div className="px-5 pt-4 pb-3 border-b border-zinc-800/60">
          <label className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase tracking-widest mb-2 font-medium">
            <MapPin size={10} /> Location
          </label>
          <input
            type="text"
            placeholder="City, State — e.g. Camden, NJ"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            className="w-full bg-zinc-900/60 border border-zinc-800 rounded-md px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-700 focus:outline-none focus:border-[#a200ff]/60 focus:bg-zinc-900 transition-all"
          />
        </div>

        {/* Niches */}
        <div className="px-5 pt-3 pb-3 flex-1 overflow-y-auto">
          <div className="flex items-center justify-between mb-2.5">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1.5 text-[10px] text-zinc-500 uppercase tracking-widest font-medium hover:text-zinc-300 transition-colors"
            >
              <Tag size={10} /> Niches
              {selected.size > 0 && (
                <span className="ml-1 bg-[#a200ff]/20 text-[#c060ff] border border-[#a200ff]/30 rounded-full px-1.5 py-0 text-[9px] font-bold">{selected.size}</span>
              )}
              <ChevronDown size={10} className={clsx("transition-transform ml-0.5", expanded ? "rotate-180" : "")} />
            </button>
            <div className="flex gap-2.5">
              <button onClick={selectAll} className="text-[10px] text-zinc-600 hover:text-[#c060ff] transition-colors">All</button>
              <button onClick={clearAll} className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors">None</button>
            </div>
          </div>

          {expanded && (
            <div className="grid grid-cols-3 gap-1">
              {NICHE_CATEGORIES.map((cat) => {
                const active = selected.has(cat);
                return (
                  <button
                    key={cat}
                    onClick={() => toggle(cat)}
                    className={clsx(
                      "text-left px-2 py-1.5 rounded-md text-[11px] capitalize transition-all border font-medium",
                      active
                        ? "bg-[#a200ff]/15 border-[#a200ff]/40 text-[#c878ff] shadow-[inset_0_0_8px_rgba(162,0,255,0.08)]"
                        : "bg-zinc-900/40 border-zinc-800/70 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400"
                    )}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Run button */}
        <div className="px-5 py-4 mt-auto border-t border-zinc-800/60">
          <button
            onClick={handleSubmit}
            disabled={!canRun}
            className={clsx(
              "w-full flex items-center justify-center gap-2 py-2.5 rounded-md font-semibold text-sm transition-all",
              canRun
                ? "bg-[#a200ff] hover:bg-[#8c00e0] text-white shadow-[0_0_20px_rgba(162,0,255,0.35)] hover:shadow-[0_0_28px_rgba(162,0,255,0.5)]"
                : "bg-zinc-900 text-zinc-600 border border-zinc-800 cursor-not-allowed"
            )}
          >
            {searching ? (
              <><Loader2 size={13} className="animate-spin" /><span>Searching…</span></>
            ) : (
              <><Search size={13} /><span>Run Search</span></>
            )}
          </button>

          {selected.size > 0 && location.trim() && !searching && (
            <p className="text-center text-[10px] text-zinc-600 mt-2">
              {selected.size} {selected.size === 1 ? "category" : "categories"} · {location.trim()}
            </p>
          )}

          {error && (
            <div className="mt-3 text-[11px] text-red-400 border border-red-900/40 rounded-md p-2.5 bg-red-950/20 leading-relaxed">{error}</div>
          )}
        </div>
      </aside>
    </>
  );
}

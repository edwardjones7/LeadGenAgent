"use client";

import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import clsx from "clsx";
import { NICHE_CATEGORIES } from "@/lib/constants";
import type { SearchResponse } from "@/lib/types";

interface Props {
  onSearch: (location: string, categories: string[]) => Promise<SearchResponse | null>;
  searching: boolean;
  lastResult: SearchResponse | null;
  error: string | null;
}

export function SearchPanel({ onSearch, searching, lastResult, error }: Props) {
  const [location, setLocation] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

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

  return (
    <aside className="w-72 shrink-0 flex flex-col gap-4 border-r border-zinc-800 p-5 overflow-y-auto">
      {/* Logo / Brand */}
      <div className="mb-1">
        <span className="text-[#a200ff] font-bold text-lg tracking-tight">elenos</span>
        <span className="text-zinc-400 text-xs ml-2 uppercase tracking-widest">Lead Intel</span>
      </div>

      {/* Location */}
      <div>
        <label className="text-xs text-zinc-400 uppercase tracking-widest mb-1.5 block">
          Location
        </label>
        <input
          type="text"
          placeholder="e.g. Camden, NJ"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          className="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-[#a200ff] transition-colors"
        />
      </div>

      {/* Niches */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs text-zinc-400 uppercase tracking-widest">Niches</label>
          <div className="flex gap-2">
            <button
              onClick={selectAll}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              All
            </button>
            <span className="text-zinc-700">|</span>
            <button
              onClick={clearAll}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              None
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {NICHE_CATEGORIES.map((cat) => {
            const active = selected.has(cat);
            return (
              <button
                key={cat}
                onClick={() => toggle(cat)}
                className={clsx(
                  "text-left px-2 py-1.5 rounded text-xs capitalize transition-all border",
                  active
                    ? "bg-[#a200ff]/20 border-[#a200ff]/50 text-[#c060ff]"
                    : "bg-zinc-900 border-zinc-800 text-zinc-500 hover:border-zinc-600 hover:text-zinc-300"
                )}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Run button */}
      <button
        onClick={handleSubmit}
        disabled={!location.trim() || selected.size === 0 || searching}
        className={clsx(
          "flex items-center justify-center gap-2 py-2.5 rounded font-semibold text-sm transition-all",
          !location.trim() || selected.size === 0 || searching
            ? "bg-zinc-800 text-zinc-600 cursor-not-allowed"
            : "bg-[#a200ff] hover:bg-[#8800d9] text-white shadow-[0_0_16px_rgba(162,0,255,0.3)]"
        )}
      >
        {searching ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            Searching…
          </>
        ) : (
          <>
            <Search size={14} />
            Run Search
          </>
        )}
      </button>

      {/* Last run stats */}
      {lastResult && !searching && (
        <div className="text-xs text-zinc-500 border border-zinc-800 rounded p-3 space-y-1">
          <div className="text-zinc-300 font-medium">Last run</div>
          <div>
            <span className="text-[#a200ff] font-semibold">{lastResult.new_leads}</span> new leads
          </div>
          <div>
            <span className="text-zinc-400">{lastResult.dupes_skipped}</span> skipped (duplicates)
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-xs text-red-400 border border-red-900/50 rounded p-3 bg-red-950/20">
          {error}
        </div>
      )}
    </aside>
  );
}

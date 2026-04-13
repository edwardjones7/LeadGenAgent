"use client";

import { useState } from "react";
import { Search, Loader2, ChevronDown, ChevronRight, Square, Filter, Users, Mail, Target, Activity } from "lucide-react";
import clsx from "clsx";
import { NICHE_CATEGORIES } from "@/lib/constants";
import type { Lead, QueueEntry, SearchResponse } from "@/lib/types";

interface Props {
  leads: Lead[];
  queue: QueueEntry[];
  searching: boolean;
  onSearch: (location: string, categories: string[]) => Promise<SearchResponse | null>;
  onQueueSearch: (location: string, categories: string[]) => void;
  onStop: (id: string) => void;
  // Filters
  statusFilter: string;
  scoreFilter: number;
  onStatusFilter: (s: string) => void;
  onScoreFilter: (n: number) => void;
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#111113] border border-zinc-800/50">
      <div className="text-zinc-600">{icon}</div>
      <div>
        <div className="text-sm font-semibold text-zinc-100 tabular-nums">{value}</div>
        <div className="text-[10px] text-zinc-600">{label}</div>
      </div>
    </div>
  );
}

export function Sidebar({
  leads, queue, searching, onSearch, onQueueSearch, onStop,
  statusFilter, scoreFilter, onStatusFilter, onScoreFilter,
}: Props) {
  const [location, setLocation] = useState("");
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [catsOpen, setCatsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const totalLeads = leads.length;
  const withEmail = leads.filter((l) => l.email).length;
  const avgScore = totalLeads > 0 ? (leads.reduce((s, l) => s + l.score, 0) / totalLeads).toFixed(1) : "—";
  const contacted = leads.filter((l) => l.status === "Contacted").length;

  const toggleCat = (cat: string) => {
    setSelectedCats((prev) => prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]);
  };

  const handleSearch = async () => {
    if (!location.trim() || selectedCats.length === 0) return;
    await onSearch(location.trim(), selectedCats);
  };

  const handleQueue = () => {
    if (!location.trim() || selectedCats.length === 0) return;
    onQueueSearch(location.trim(), selectedCats);
  };

  const activeQueue = queue.filter((e) => e.status === "running" || e.status === "pending");

  return (
    <aside className="w-[240px] shrink-0 border-r border-zinc-800 bg-[#09090B] overflow-y-auto">
      <div className="p-3 space-y-4">

        {/* Stats */}
        <div className="grid grid-cols-2 gap-2">
          <StatCard icon={<Users size={14} />} label="Leads" value={totalLeads} />
          <StatCard icon={<Mail size={14} />} label="Emails" value={withEmail} />
          <StatCard icon={<Target size={14} />} label="Avg Score" value={avgScore} />
          <StatCard icon={<Activity size={14} />} label="Contacted" value={contacted} />
        </div>

        {/* Queue */}
        {activeQueue.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-1">Queue</div>
            {activeQueue.map((entry) => (
              <div key={entry.id} className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-[#111113] border border-zinc-800/50">
                {entry.status === "running" ? (
                  <Loader2 size={10} className="shrink-0 text-violet-400 animate-spin" />
                ) : (
                  <div className="w-2.5 h-2.5 shrink-0 rounded-full bg-amber-500/40 border border-amber-500/60" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] text-zinc-300 truncate">{entry.location}</div>
                  <div className="text-[10px] text-zinc-600 truncate">
                    {(Array.isArray(entry.categories) ? entry.categories : []).join(", ")}
                  </div>
                </div>
                {entry.status === "running" && (
                  <button
                    onClick={() => onStop(entry.id)}
                    className="p-0.5 rounded text-zinc-600 hover:text-red-400 transition-colors"
                  >
                    <Square size={10} />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Search */}
        <div>
          <button
            onClick={() => setSearchOpen((v) => !v)}
            className="flex items-center gap-2 w-full text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-1 py-1 hover:text-zinc-400 transition-colors"
          >
            {searchOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            New Search
          </button>

          {searchOpen && (
            <div className="mt-1.5 space-y-2">
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="City, State"
                className="w-full px-3 py-2 rounded-lg bg-[#111113] border border-zinc-800 text-sm text-zinc-200 placeholder:text-zinc-600 outline-none focus:border-violet-500/50 transition-colors"
              />

              <div>
                <button
                  onClick={() => setCatsOpen((v) => !v)}
                  className="flex items-center justify-between w-full px-3 py-2 rounded-lg bg-[#111113] border border-zinc-800 text-sm text-zinc-400 hover:border-zinc-600 transition-colors"
                >
                  <span>
                    {selectedCats.length > 0
                      ? `${selectedCats.length} selected`
                      : "Select categories"}
                  </span>
                  <ChevronDown size={12} className={clsx("transition-transform", catsOpen && "rotate-180")} />
                </button>

                {catsOpen && (
                  <div className="mt-1 max-h-[200px] overflow-y-auto rounded-lg border border-zinc-800 bg-[#111113] p-1.5 space-y-0.5">
                    {NICHE_CATEGORIES.map((cat) => (
                      <button
                        key={cat}
                        onClick={() => toggleCat(cat)}
                        className={clsx(
                          "w-full text-left px-2.5 py-1.5 rounded text-xs transition-colors",
                          selectedCats.includes(cat)
                            ? "bg-violet-500/15 text-violet-300 font-medium"
                            : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
                        )}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-1.5">
                <button
                  onClick={handleSearch}
                  disabled={!location.trim() || selectedCats.length === 0 || searching}
                  className={clsx(
                    "flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all",
                    location.trim() && selectedCats.length > 0 && !searching
                      ? "bg-violet-600 hover:bg-violet-700 text-white"
                      : "bg-zinc-800/50 text-zinc-600 cursor-not-allowed"
                  )}
                >
                  {searching ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
                  Search
                </button>
                <button
                  onClick={handleQueue}
                  disabled={!location.trim() || selectedCats.length === 0}
                  className={clsx(
                    "px-3 py-2 rounded-lg text-xs font-medium border transition-all",
                    location.trim() && selectedCats.length > 0
                      ? "border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600"
                      : "border-zinc-800/50 text-zinc-700 cursor-not-allowed"
                  )}
                >
                  Queue
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Filters */}
        <div>
          <button
            onClick={() => setFiltersOpen((v) => !v)}
            className="flex items-center gap-2 w-full text-[10px] font-medium text-zinc-600 uppercase tracking-wider px-1 py-1 hover:text-zinc-400 transition-colors"
          >
            {filtersOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
            <Filter size={10} />
            Filters
          </button>

          {filtersOpen && (
            <div className="mt-1.5 space-y-2.5 px-1">
              <div>
                <div className="text-[10px] text-zinc-600 mb-1">Status</div>
                <div className="flex gap-1 flex-wrap">
                  {["All", "New", "Contacted", "Closed"].map((s) => (
                    <button
                      key={s}
                      onClick={() => onStatusFilter(s === "All" ? "" : s)}
                      className={clsx(
                        "px-2.5 py-1 rounded text-[11px] font-medium transition-colors",
                        (s === "All" && !statusFilter) || statusFilter === s
                          ? "bg-violet-500/15 text-violet-300 border border-violet-500/30"
                          : "text-zinc-500 border border-zinc-800/50 hover:border-zinc-600"
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-600 mb-1">Min Score</div>
                <div className="flex gap-1">
                  {[0, 5, 7, 9].map((n) => (
                    <button
                      key={n}
                      onClick={() => onScoreFilter(n)}
                      className={clsx(
                        "px-2.5 py-1 rounded text-[11px] font-medium transition-colors",
                        scoreFilter === n
                          ? "bg-violet-500/15 text-violet-300 border border-violet-500/30"
                          : "text-zinc-500 border border-zinc-800/50 hover:border-zinc-600"
                      )}
                    >
                      {n === 0 ? "Any" : `${n}+`}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

      </div>
    </aside>
  );
}

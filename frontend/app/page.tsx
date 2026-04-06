"use client";

import { useState } from "react";
import { Zap } from "lucide-react";
import { SearchPanel } from "@/components/SearchPanel";
import { LeadsTable } from "@/components/LeadsTable";
import { LeadDetailPanel } from "@/components/LeadDetailPanel";
import { useLeads } from "@/hooks/useLeads";
import { useSearch } from "@/hooks/useSearch";
import type { Lead } from "@/lib/types";

export default function Home() {
  const { leads, loading, updateLead, deleteLead, addLeads, fetchLeads } = useLeads();
  const { loading: searching, error: searchError, lastResult, runSearch } = useSearch();
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const handleSearch = async (location: string, categories: string[]) => {
    const result = await runSearch(location, categories);
    if (result?.new_leads > 0) await fetchLeads();
    return result;
  };

  const handleSelectLead = (lead: Lead) => {
    setSelectedLead((prev) => (prev?.id === lead.id ? null : lead));
  };

  const handleUpdateLead = async (id: string, data: { status?: string; email?: string; outreach_status?: string }) => {
    const updated = await updateLead(id, data);
    if (selectedLead?.id === id) setSelectedLead(updated);
    return updated;
  };

  const handleDeleteLead = async (id: string) => {
    await deleteLead(id);
    if (selectedLead?.id === id) setSelectedLead(null);
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#0a0a0f] text-zinc-100">
      {/* Top nav */}
      <header className="shrink-0 flex items-center justify-between px-5 py-3 border-b border-zinc-800/80 bg-[#0a0a0f]">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-[#a200ff] flex items-center justify-center shadow-[0_0_12px_rgba(162,0,255,0.5)]">
            <Zap size={13} className="text-white fill-white" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-white font-bold text-sm tracking-tight">elenos</span>
            <span className="text-zinc-600 text-xs">/</span>
            <span className="text-zinc-500 text-xs tracking-wide">lead intel</span>
          </div>
        </div>

        <div className="flex items-center gap-5 text-xs text-zinc-500">
          {lastResult && !searching && (
            <span className="text-zinc-500">
              Last run:{" "}
              <span className="text-[#a200ff] font-semibold">{lastResult.new_leads}</span> new ·{" "}
              <span className="text-zinc-400">{lastResult.dupes_skipped}</span> skipped
            </span>
          )}
          <div className="h-4 w-px bg-zinc-800" />
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]" />
            <span className="text-zinc-400">US</span>
          </div>
          <div className="h-4 w-px bg-zinc-800" />
          <span>
            <span className="text-zinc-200 font-semibold">{leads.length}</span>{" "}
            <span className="text-zinc-600">leads</span>
          </span>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <SearchPanel
          onSearch={handleSearch}
          searching={searching}
          lastResult={lastResult}
          error={searchError}
        />

        <LeadsTable
          leads={leads}
          loading={loading}
          onSelectLead={handleSelectLead}
          selectedId={selectedLead?.id ?? null}
        />

        {selectedLead && (
          <LeadDetailPanel
            lead={selectedLead}
            onClose={() => setSelectedLead(null)}
            onUpdate={handleUpdateLead}
            onDelete={handleDeleteLead}
          />
        )}
      </div>
    </div>
  );
}

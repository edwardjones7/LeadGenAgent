"use client";

import { useState } from "react";
import { Zap, Search, MessageSquare, Mail } from "lucide-react";
import { SearchPanel } from "@/components/SearchPanel";
import { LeadsTable } from "@/components/LeadsTable";
import { LeadDetailPanel } from "@/components/LeadDetailPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { SearchLogOverlay } from "@/components/SearchLogOverlay";
import { EmailFinderOverlay } from "@/components/EmailFinderOverlay";
import { useLeads } from "@/hooks/useLeads";
import { useSearchStream } from "@/hooks/useSearchStream";
import type { Lead } from "@/lib/types";

export default function Home() {
  const { leads, loading, updateLead, deleteLead, fetchLeads } = useLeads();
  const { logs, isSearching, progress, result, error: searchError, runSearch, clearLogs } = useSearchStream();

  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [emailFinderOpen, setEmailFinderOpen] = useState(false);
  const [lastSearchState, setLastSearchState] = useState({ location: "", categories: [] as string[] });

  const handleSearch = async (location: string, categories: string[]) => {
    setLastSearchState({ location, categories });
    setShowLogs(true);
    const res = await runSearch(location, categories);
    if (res && res.new_leads > 0) await fetchLeads();
    return res;
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

  const handleCloseSearchLog = () => {
    setShowLogs(false);
    clearLogs();
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#0a0a0f] text-zinc-100">
      {/* Header */}
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

        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {/* Search button */}
          <button
            onClick={() => setSearchOpen((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              searchOpen
                ? "bg-[#a200ff]/20 text-[#c060ff] border border-[#a200ff]/40"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 border border-zinc-800"
            }`}
          >
            <Search size={12} />
            Search
          </button>

          {/* Email Finder button */}
          <button
            onClick={() => setEmailFinderOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 border border-zinc-800"
          >
            <Mail size={12} />
            Find Emails
          </button>

          <div className="h-4 w-px bg-zinc-800" />

          {result && !isSearching && (
            <>
              <span className="text-zinc-500">
                Last: <span className="text-[#a200ff] font-semibold">{result.new_leads}</span> new · <span className="text-zinc-400">{result.dupes_skipped}</span> skipped
              </span>
              <div className="h-4 w-px bg-zinc-800" />
            </>
          )}

          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]" />
            <span className="text-zinc-400">US</span>
          </div>
          <div className="h-4 w-px bg-zinc-800" />
          <span>
            <span className="text-zinc-200 font-semibold">{leads.length}</span>{" "}
            <span className="text-zinc-600">leads</span>
          </span>
          <div className="h-4 w-px bg-zinc-800" />

          {/* Chat button */}
          <button
            onClick={() => setChatOpen((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              chatOpen
                ? "bg-[#a200ff]/20 text-[#c060ff] border border-[#a200ff]/40"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 border border-zinc-800"
            }`}
          >
            <MessageSquare size={12} />
            AI
          </button>
        </div>
      </header>

      {/* Main content — full width table */}
      <div className="flex-1 overflow-hidden">
        <LeadsTable
          leads={leads}
          loading={loading}
          onSelectLead={handleSelectLead}
          selectedId={selectedLead?.id ?? null}
        />
      </div>

      {/* Overlays */}
      <SearchPanel
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSearch={handleSearch}
        searching={isSearching}
        lastResult={result}
        error={searchError}
      />

      {selectedLead && (
        <LeadDetailPanel
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
          onUpdate={handleUpdateLead}
          onDelete={handleDeleteLead}
        />
      )}

      {chatOpen && (
        <ChatPanel
          onClose={() => setChatOpen(false)}
          selectedLead={selectedLead}
          visibleLeadIds={leads.map((l) => l.id)}
          filters={{}}
          searchState={lastSearchState}
          onLeadsMutated={fetchLeads}
          detailOpen={!!selectedLead}
        />
      )}

      <EmailFinderOverlay
        open={emailFinderOpen}
        onClose={() => setEmailFinderOpen(false)}
        onComplete={fetchLeads}
      />

      {showLogs && (
        <SearchLogOverlay
          logs={logs}
          isSearching={isSearching}
          progress={progress}
          result={result}
          error={searchError}
          onClose={handleCloseSearchLog}
        />
      )}
    </div>
  );
}

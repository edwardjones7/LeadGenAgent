"use client";

import { useState } from "react";
import { Zap, Search, MessageSquare, Mail, ListTodo, Trash2 } from "lucide-react";
import { SearchPanel } from "@/components/SearchPanel";
import { LeadsTable } from "@/components/LeadsTable";
import { LeadDetailPanel } from "@/components/LeadDetailPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { EmailFinderOverlay } from "@/components/EmailFinderOverlay";
import { SearchQueuePanel } from "@/components/SearchQueuePanel";
import { useLeads } from "@/hooks/useLeads";
import { useSearchQueue } from "@/hooks/useSearchQueue";
import { api } from "@/lib/api";
import type { Lead } from "@/lib/types";

export default function Home() {
  const { leads, loading, updateLead, deleteLead, fetchLeads } = useLeads();
  const { queue, activeCount, enqueue, cancel, stop, remove, clearFinished, fetchQueue } = useSearchQueue(fetchLeads);

  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [searchOpen, setSearchOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [emailFinderOpen, setEmailFinderOpen] = useState(false);
  const [queueOpen, setQueueOpen] = useState(false);
  const [lastSearchState, setLastSearchState] = useState({ location: "", categories: [] as string[] });

  const handleSearch = async (location: string, categories: string[]) => {
    setLastSearchState({ location, categories });
    await enqueue({ location, categories });
    setQueueOpen(true);
  };

  const handleClearAll = async () => {
    const count = leads.length;
    if (count === 0) return;
    const msg = `Delete all ${count} lead${count === 1 ? "" : "s"}? This cannot be undone.`;
    if (!window.confirm(msg)) return;
    try {
      await api.clearAllLeads();
      setSelectedLead(null);
      await fetchLeads();
    } catch { /* ignore */ }
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

          {/* Queue button */}
          <button
            onClick={() => setQueueOpen((v) => !v)}
            className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              queueOpen
                ? "bg-[#a200ff]/20 text-[#c060ff] border border-[#a200ff]/40"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 border border-zinc-800"
            }`}
          >
            <ListTodo size={12} />
            Queue
            {activeCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-[#a200ff] text-white rounded-full w-4 h-4 text-[9px] flex items-center justify-center font-bold shadow-[0_0_8px_rgba(162,0,255,0.6)]">
                {activeCount}
              </span>
            )}
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

          <span>
            <span className="text-zinc-200 font-semibold">{leads.length}</span>{" "}
            <span className="text-zinc-600">leads</span>
          </span>

          {/* Clear all leads */}
          <button
            onClick={handleClearAll}
            disabled={leads.length === 0}
            title="Delete every lead"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all text-zinc-500 hover:text-red-400 hover:bg-red-500/10 hover:border-red-500/30 border border-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:text-zinc-500 disabled:hover:bg-transparent disabled:hover:border-zinc-800"
          >
            <Trash2 size={12} />
            Clear
          </button>

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

      {/* Body — search sidebar + table */}
      <div className="flex flex-1 overflow-hidden">
        {/* Permanent search sidebar */}
        {searchOpen && (
          <SearchPanel
            onSearch={handleSearch}
            searching={activeCount > 0}
          />
        )}

        {/* Table */}
        <div className="flex-1 overflow-hidden">
          <LeadsTable
            leads={leads}
            loading={loading}
            onSelectLead={handleSelectLead}
            selectedId={selectedLead?.id ?? null}
          />
        </div>
      </div>

      {/* Overlays */}
      <SearchQueuePanel
        open={queueOpen}
        onClose={() => setQueueOpen(false)}
        queue={queue}
        onCancel={cancel}
        onStop={stop}
        onRemove={remove}
        onClearFinished={clearFinished}
        onRefresh={fetchQueue}
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
    </div>
  );
}

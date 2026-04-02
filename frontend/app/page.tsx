"use client";

import { useState } from "react";
import { SearchPanel } from "@/components/SearchPanel";
import { LeadsTable } from "@/components/LeadsTable";
import { LeadDetailPanel } from "@/components/LeadDetailPanel";
import { useLeads } from "@/hooks/useLeads";
import { useSearch } from "@/hooks/useSearch";
import type { Lead } from "@/lib/types";

export default function Home() {
  const { leads, loading, updateLead, deleteLead, addLeads } = useLeads();
  const { loading: searching, error: searchError, lastResult, runSearch } = useSearch();
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const handleSearch = async (location: string, categories: string[]) => {
    const result = await runSearch(location, categories);
    if (result?.leads?.length) {
      addLeads(result.leads);
    }
    return result;
  };

  const handleSelectLead = (lead: Lead) => {
    setSelectedLead((prev) => (prev?.id === lead.id ? null : lead));
  };

  const handleUpdateLead = async (id: string, data: { status?: string; email?: string }) => {
    const updated = await updateLead(id, data);
    if (selectedLead?.id === id) setSelectedLead(updated);
    return updated;
  };

  const handleDeleteLead = async (id: string) => {
    await deleteLead(id);
    if (selectedLead?.id === id) setSelectedLead(null);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0a0f] text-zinc-100">
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
  );
}

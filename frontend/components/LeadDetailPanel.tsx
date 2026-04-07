"use client";

import { useState } from "react";
import { X, Trash2, Eye, Send, Code } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { LeadOverviewTab } from "./LeadOverviewTab";
import { LeadOutreachTab } from "./LeadOutreachTab";
import { LeadWebsiteTab } from "./LeadWebsiteTab";
import type { Lead, LeadStatus, AiAnalysis } from "@/lib/types";

interface Props {
  lead: Lead;
  onClose: () => void;
  onUpdate: (id: string, data: { status?: string; email?: string; outreach_status?: string }) => Promise<Lead>;
  onDelete: (id: string) => Promise<void>;
}

type Tab = "overview" | "outreach" | "website";

const TABS: { id: Tab; label: string; icon: typeof Eye }[] = [
  { id: "overview", label: "Overview", icon: Eye },
  { id: "outreach", label: "Outreach", icon: Send },
  { id: "website", label: "Website", icon: Code },
];

export function LeadDetailPanel({ lead, onClose, onUpdate, onDelete }: Props) {
  const [tab, setTab] = useState<Tab>("overview");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [outreachStatus, setOutreachStatus] = useState<string>(lead.outreach_status ?? "idle");
  const [aiAnalysis] = useState<AiAnalysis | null>(lead.ai_analysis ?? null);

  const handleStatusChange = async (newStatus: LeadStatus) => {
    setSaving(true);
    try {
      await onUpdate(lead.id, { status: newStatus });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${lead.business_name}"?`)) return;
    setDeleting(true);
    await onDelete(lead.id);
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-30 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <aside className="fixed inset-y-0 right-0 z-40 w-[420px] flex flex-col bg-[#0c0c12] border-l border-zinc-800/80 shadow-2xl animate-slide-in-right">
        {/* Header */}
        <div className="shrink-0 px-5 pt-5 pb-3 border-b border-zinc-800/60">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <ScoreBadge score={lead.score} />
              <div className="min-w-0">
                <h2 className="text-zinc-100 font-semibold text-sm leading-snug truncate">{lead.business_name}</h2>
                <p className="text-zinc-600 text-xs mt-0.5 capitalize">
                  {lead.category}{lead.city && ` · ${lead.city}, ${lead.state}`}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="text-zinc-700 hover:text-zinc-300 transition-colors shrink-0 p-1 rounded hover:bg-zinc-800">
              <X size={15} />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-3">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
                  tab === id
                    ? "bg-[#a200ff]/15 border border-[#a200ff]/40 text-[#c878ff]"
                    : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800/60 border border-transparent"
                )}
              >
                <Icon size={11} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {tab === "overview" && (
            <LeadOverviewTab lead={lead} aiAnalysis={aiAnalysis} onStatusChange={handleStatusChange} saving={saving} />
          )}
          {tab === "outreach" && (
            <LeadOutreachTab lead={lead} outreachStatus={outreachStatus} onOutreachStatusChange={setOutreachStatus} onUpdate={onUpdate} />
          )}
          {tab === "website" && (
            <LeadWebsiteTab lead={lead} />
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 px-5 py-3 border-t border-zinc-800/60 flex items-center justify-between">
          <button onClick={handleDelete} disabled={deleting} className="flex items-center gap-1.5 text-xs text-zinc-700 hover:text-red-400 transition-colors">
            <Trash2 size={12} /> {deleting ? "Deleting…" : "Delete lead"}
          </button>
          <button onClick={onClose} className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors">Close</button>
        </div>
      </aside>
    </>
  );
}

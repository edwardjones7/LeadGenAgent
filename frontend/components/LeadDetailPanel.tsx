"use client";

import { useState } from "react";
import { X, Phone, Mail, Globe, Trash2, ExternalLink } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { StatusBadge } from "./StatusBadge";
import { LEAD_STATUSES } from "@/lib/constants";
import type { Lead, LeadStatus } from "@/lib/types";

interface Props {
  lead: Lead;
  onClose: () => void;
  onUpdate: (id: string, data: { status?: string; email?: string }) => Promise<Lead>;
  onDelete: (id: string) => Promise<void>;
}

export function LeadDetailPanel({ lead, onClose, onUpdate, onDelete }: Props) {
  const [status, setStatus] = useState<LeadStatus>(lead.status);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleStatusChange = async (newStatus: LeadStatus) => {
    setStatus(newStatus);
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
    <aside className="w-96 shrink-0 border-l border-zinc-800 flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between p-5 border-b border-zinc-800">
        <div className="flex-1 min-w-0 pr-3">
          <h2 className="text-zinc-100 font-semibold text-base leading-tight truncate">
            {lead.business_name}
          </h2>
          <p className="text-zinc-500 text-sm mt-0.5 capitalize">
            {lead.category} · {lead.city}, {lead.state}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-zinc-600 hover:text-zinc-300 transition-colors shrink-0 mt-0.5"
        >
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 p-5 space-y-5">
        {/* Score */}
        <div className="flex items-center gap-4">
          <ScoreBadge score={lead.score} large />
          <div>
            <div className="text-xs text-zinc-500 uppercase tracking-widest mb-1">
              Lead Score
            </div>
            <div className="text-xs text-zinc-300 leading-relaxed">
              {lead.score_reason ?? "No evaluation data"}
            </div>
          </div>
        </div>

        {/* Status */}
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Status</div>
          <div className="flex gap-2">
            {LEAD_STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => handleStatusChange(s as LeadStatus)}
                disabled={saving}
                className={clsx(
                  "px-3 py-1.5 rounded text-xs font-medium border transition-all",
                  status === s
                    ? s === "New"
                      ? "bg-[#a200ff]/20 border-[#a200ff]/50 text-[#c060ff]"
                      : s === "Contacted"
                      ? "bg-blue-500/20 border-blue-500/40 text-blue-300"
                      : "bg-zinc-700/40 border-zinc-600/40 text-zinc-400"
                    : "bg-transparent border-zinc-700 text-zinc-500 hover:border-zinc-500"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Contact info */}
        <div className="space-y-2.5">
          <div className="text-xs text-zinc-500 uppercase tracking-widest">Contact</div>

          {lead.phone && (
            <a
              href={`tel:${lead.phone}`}
              className="flex items-center gap-2.5 text-sm text-zinc-300 hover:text-zinc-100 transition-colors"
            >
              <Phone size={14} className="text-zinc-500 shrink-0" />
              {lead.phone}
            </a>
          )}

          {lead.email ? (
            <a
              href={`mailto:${lead.email}`}
              className="flex items-center gap-2.5 text-sm text-zinc-300 hover:text-[#c060ff] transition-colors"
            >
              <Mail size={14} className="text-zinc-500 shrink-0" />
              {lead.email}
            </a>
          ) : (
            <div className="flex items-center gap-2.5 text-sm text-zinc-600">
              <Mail size={14} className="shrink-0" />
              No email found
            </div>
          )}

          {lead.website_url ? (
            <a
              href={lead.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2.5 text-sm text-zinc-300 hover:text-[#c060ff] transition-colors min-w-0"
            >
              <Globe size={14} className="text-zinc-500 shrink-0" />
              <span className="truncate">{lead.website_url}</span>
              <ExternalLink size={10} className="text-zinc-600 shrink-0" />
            </a>
          ) : (
            <div className="flex items-center gap-2.5 text-sm text-[#c060ff]">
              <Globe size={14} className="shrink-0" />
              No website found
            </div>
          )}
        </div>

        {/* Source */}
        <div>
          <div className="text-xs text-zinc-500 uppercase tracking-widest mb-1">Source</div>
          <span className="text-xs text-zinc-400 capitalize">{lead.source ?? "unknown"}</span>
        </div>

        {/* Added date */}
        {lead.created_at && (
          <div>
            <div className="text-xs text-zinc-500 uppercase tracking-widest mb-1">Added</div>
            <span className="text-xs text-zinc-400">
              {new Date(lead.created_at).toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Delete */}
      <div className="p-5 border-t border-zinc-800">
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="flex items-center gap-2 text-xs text-zinc-600 hover:text-red-400 transition-colors"
        >
          <Trash2 size={13} />
          {deleting ? "Deleting…" : "Delete lead"}
        </button>
      </div>
    </aside>
  );
}

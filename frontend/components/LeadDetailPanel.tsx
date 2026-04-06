"use client";

import { useState } from "react";
import { X, Phone, Mail, Globe, Trash2, ExternalLink, Copy, Check, Send, Brain, Code, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { LEAD_STATUSES, OUTREACH_STATUS_LABELS } from "@/lib/constants";
import { api } from "@/lib/api";
import type { Lead, LeadStatus, AiAnalysis, EmailRecord, WebsiteSpec } from "@/lib/types";

interface Props {
  lead: Lead;
  onClose: () => void;
  onUpdate: (id: string, data: { status?: string; email?: string; outreach_status?: string }) => Promise<Lead>;
  onDelete: (id: string) => Promise<void>;
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-zinc-300 transition-all"
    >
      {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
    </button>
  );
}

const STATUS_STYLES: Record<LeadStatus, { active: string; inactive: string }> = {
  New: {
    active: "bg-[#a200ff]/15 border-[#a200ff]/50 text-[#c878ff]",
    inactive: "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400",
  },
  Contacted: {
    active: "bg-blue-500/15 border-blue-500/40 text-blue-300",
    inactive: "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400",
  },
  Closed: {
    active: "bg-zinc-700/40 border-zinc-600/50 text-zinc-400",
    inactive: "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400",
  },
};

function ScoreBar({ score }: { score: number }) {
  const pct = (score / 10) * 100;
  const color =
    score >= 9 ? "bg-[#a200ff]"
    : score >= 7 ? "bg-red-500"
    : score >= 4 ? "bg-amber-500"
    : "bg-zinc-600";

  return (
    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
      <div
        className={clsx("h-full rounded-full transition-all", color, score >= 9 && "shadow-[0_0_8px_rgba(162,0,255,0.6)]")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

const SEVERITY_COLORS: Record<string, string> = {
  low:    "bg-zinc-800 text-zinc-400 border-zinc-700",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  high:   "bg-red-500/15 text-red-400 border-red-500/30",
};

const STEP_LABELS: Record<number, string> = {
  0: "Initial email",
  1: "Follow-up 1",
  2: "Follow-up 2",
};

const EMAIL_STATUS_COLORS: Record<string, string> = {
  sent:    "text-emerald-400",
  opened:  "text-blue-400",
  failed:  "text-red-400",
  pending: "text-zinc-500",
};

export function LeadDetailPanel({ lead, onClose, onUpdate, onDelete }: Props) {
  const [status, setStatus] = useState<LeadStatus>(lead.status);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Outreach state
  const [outreachStatus, setOutreachStatus] = useState(lead.outreach_status ?? "idle");
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalysis | null>(lead.ai_analysis ?? null);
  const [sendingOutreach, setSendingOutreach] = useState(false);
  const [outreachError, setOutreachError] = useState<string | null>(null);
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [previewEmail, setPreviewEmail] = useState<{ subject: string; body: string } | null>(null);

  // Email history
  const [emailHistory, setEmailHistory] = useState<EmailRecord[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [expandedEmailId, setExpandedEmailId] = useState<string | null>(null);

  // Website spec
  const [generatingSite, setGeneratingSite] = useState(false);
  const [websiteSpec, setWebsiteSpec] = useState<WebsiteSpec | null>(null);
  const [showSpec, setShowSpec] = useState(false);
  const [specCopied, setSpecCopied] = useState(false);

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

  const handleSendOutreach = async (dryRun = false) => {
    setSendingOutreach(true);
    setOutreachError(null);
    setPreviewEmail(null);
    try {
      const result = await api.sendOutreach(lead.id, dryRun);
      if (dryRun) {
        setPreviewEmail({ subject: result.subject, body: result.body });
        setShowEmailPreview(true);
      } else {
        if (result.status === "sent") {
          const newStatus = `emailed_${(lead.follow_up_count ?? 0) + 1}` as any;
          setOutreachStatus(newStatus);
          await onUpdate(lead.id, { outreach_status: newStatus });
          // Refresh history
          const history = await api.getEmailHistory(lead.id);
          setEmailHistory(history);
          setHistoryLoaded(true);
          setShowHistory(true);
        } else {
          setOutreachError(result.error ?? "Send failed");
        }
      }
    } catch (e: any) {
      setOutreachError(e.message ?? "Unknown error");
    } finally {
      setSendingOutreach(false);
    }
  };

  const handleLoadHistory = async () => {
    if (!historyLoaded) {
      const history = await api.getEmailHistory(lead.id);
      setEmailHistory(history);
      setHistoryLoaded(true);
    }
    setShowHistory((v) => !v);
  };

  const handleGenerateSite = async () => {
    setGeneratingSite(true);
    try {
      const spec = await api.generateWebsiteSpec(lead.id);
      setWebsiteSpec(spec);
      setShowSpec(true);
    } catch (e: any) {
      alert(`Site generation failed: ${e.message}`);
    } finally {
      setGeneratingSite(false);
    }
  };

  const handleCopySpec = async () => {
    if (!websiteSpec) return;
    await navigator.clipboard.writeText(JSON.stringify(websiteSpec, null, 2));
    setSpecCopied(true);
    setTimeout(() => setSpecCopied(false), 1500);
  };

  const canSendOutreach = !!lead.email && !["emailed_3", "bounced", "opted_out"].includes(outreachStatus);
  const sendLabel =
    outreachStatus === "idle" || outreachStatus === "queued"
      ? "Analyze & Send Email"
      : outreachStatus === "emailed_1" || outreachStatus === "emailed_2"
      ? "Send Follow-up"
      : outreachStatus === "emailed_3"
      ? "Max follow-ups sent"
      : outreachStatus === "bounced"
      ? "Email bounced"
      : "Send Email";

  const scoreReasons = lead.score_reason
    ? lead.score_reason.split(";").map((s) => s.trim()).filter(Boolean)
    : [];

  return (
    <aside className="w-88 shrink-0 border-l border-zinc-800/80 flex flex-col overflow-y-auto bg-[#0c0c12]">
      {/* Header */}
      <div className="flex items-start justify-between px-5 pt-5 pb-4 border-b border-zinc-800/60">
        <div className="flex-1 min-w-0 pr-3">
          <h2 className="text-zinc-100 font-semibold text-sm leading-snug">
            {lead.business_name}
          </h2>
          <p className="text-zinc-600 text-xs mt-1 capitalize">
            {lead.category}
            {lead.city && ` · ${lead.city}, ${lead.state}`}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-zinc-700 hover:text-zinc-300 transition-colors shrink-0 p-0.5 rounded hover:bg-zinc-800"
        >
          <X size={15} />
        </button>
      </div>

      <div className="flex-1 divide-y divide-zinc-800/60">
        {/* Score section */}
        <div className="px-5 py-4 space-y-3">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium">
            Lead Score
          </span>
          <div className="flex items-center gap-3">
            <ScoreBadge score={lead.score} large />
            <div className="flex-1 space-y-1.5">
              <ScoreBar score={lead.score} />
              <p className="text-[10px] text-zinc-600">
                {lead.score >= 9
                  ? "Hot lead — very weak web presence"
                  : lead.score >= 7
                  ? "Strong lead — clear website issues"
                  : lead.score >= 4
                  ? "Moderate lead"
                  : "Low priority"}
              </p>
            </div>
          </div>
          {scoreReasons.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {scoreReasons.map((r, i) => (
                <span
                  key={i}
                  className="text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 leading-relaxed"
                >
                  {r}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* AI Analysis section */}
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
              <Brain size={10} />
              AI Analysis
            </span>
            {aiAnalysis && (
              <span className={clsx("text-[10px] px-1.5 py-0.5 rounded border font-medium", SEVERITY_COLORS[aiAnalysis.severity])}>
                {aiAnalysis.severity}
              </span>
            )}
          </div>

          {aiAnalysis ? (
            <div className="space-y-2">
              <p className="text-xs text-zinc-500 leading-relaxed">{aiAnalysis.summary}</p>
              <div className="flex flex-wrap gap-1">
                {aiAnalysis.problems.map((p, i) => (
                  <span
                    key={i}
                    title={p.description}
                    className="text-[10px] bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 text-zinc-500"
                  >
                    {p.category}
                  </span>
                ))}
              </div>
              {aiAnalysis.problems.length > 0 && (
                <ul className="space-y-1 mt-1">
                  {aiAnalysis.problems.map((p, i) => (
                    <li key={i} className="text-[10px] text-zinc-600 leading-relaxed">
                      <span className="text-zinc-500 font-medium">{p.category}:</span> {p.description}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <p className="text-[10px] text-zinc-700">
              {lead.website_url
                ? "Click \u201cAnalyze & Send\u201d to run an AI analysis of this website."
                : "No website URL \u2014 analysis will be skipped."}
            </p>
          )}
        </div>

        {/* Status section */}
        <div className="px-5 py-4 space-y-2.5">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium block">
            Status {saving && <span className="text-zinc-700 normal-case tracking-normal">saving…</span>}
          </span>
          <div className="flex gap-1.5">
            {LEAD_STATUSES.map((s) => (
              <button
                key={s}
                onClick={() => handleStatusChange(s as LeadStatus)}
                disabled={saving}
                className={clsx(
                  "flex-1 py-1.5 rounded-md text-xs font-medium border transition-all",
                  status === s ? STATUS_STYLES[s as LeadStatus].active : STATUS_STYLES[s as LeadStatus].inactive
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Contact section */}
        <div className="px-5 py-4 space-y-3">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium block">
            Contact
          </span>

          {lead.phone ? (
            <div className="group flex items-center justify-between">
              <a
                href={`tel:${lead.phone}`}
                className="flex items-center gap-2.5 text-sm text-zinc-300 hover:text-white transition-colors"
              >
                <Phone size={13} className="text-zinc-600 shrink-0" />
                {lead.phone}
              </a>
              <CopyButton value={lead.phone} />
            </div>
          ) : (
            <div className="flex items-center gap-2.5 text-sm text-zinc-700">
              <Phone size={13} className="shrink-0" />
              No phone
            </div>
          )}

          {lead.email ? (
            <div className="group flex items-center justify-between">
              <a
                href={`mailto:${lead.email}`}
                className="flex items-center gap-2.5 text-sm text-[#c060ff] hover:text-[#d580ff] transition-colors truncate"
              >
                <Mail size={13} className="text-zinc-600 shrink-0" />
                <span className="truncate">{lead.email}</span>
              </a>
              <CopyButton value={lead.email} />
            </div>
          ) : (
            <div className="flex items-center gap-2.5 text-sm text-zinc-700">
              <Mail size={13} className="shrink-0" />
              No email found
            </div>
          )}

          {lead.website_url ? (
            <div className="group flex items-center justify-between gap-2">
              <a
                href={lead.website_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2.5 text-sm text-zinc-400 hover:text-zinc-200 transition-colors min-w-0"
              >
                <Globe size={13} className="text-zinc-600 shrink-0" />
                <span className="truncate text-xs">{lead.website_url}</span>
                <ExternalLink size={10} className="text-zinc-700 shrink-0" />
              </a>
            </div>
          ) : (
            <div className="flex items-center gap-2.5 text-sm">
              <Globe size={13} className="text-[#a200ff] shrink-0" />
              <span className="text-[#a200ff]/70 text-xs font-medium">No website — prime target</span>
            </div>
          )}
        </div>

        {/* Outreach section */}
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
              <Send size={10} />
              Outreach
            </span>
            {outreachStatus !== "idle" && (
              <span className="text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5">
                {OUTREACH_STATUS_LABELS[outreachStatus] ?? outreachStatus}
              </span>
            )}
          </div>

          <div className="space-y-2">
            <button
              onClick={() => handleSendOutreach(false)}
              disabled={!canSendOutreach || sendingOutreach}
              title={!lead.email ? "No email address found" : undefined}
              className={clsx(
                "w-full flex items-center justify-center gap-2 py-2 rounded-md text-xs font-medium border transition-all",
                canSendOutreach && !sendingOutreach
                  ? "bg-[#a200ff]/15 border-[#a200ff]/40 text-[#c060ff] hover:bg-[#a200ff]/25"
                  : "bg-zinc-900 border-zinc-800 text-zinc-700 cursor-not-allowed"
              )}
            >
              {sendingOutreach ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Send size={12} />
              )}
              {sendingOutreach ? "Sending…" : sendLabel}
            </button>

            <button
              onClick={() => handleSendOutreach(true)}
              disabled={!canSendOutreach || sendingOutreach}
              className="w-full py-1.5 rounded-md text-[10px] text-zinc-600 border border-zinc-800 hover:text-zinc-400 hover:border-zinc-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Preview email (dry run)
            </button>
          </div>

          {outreachError && (
            <p className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded px-2 py-1.5">
              {outreachError}
            </p>
          )}

          {showEmailPreview && previewEmail && (
            <div className="space-y-1.5 mt-1">
              <p className="text-[10px] text-zinc-500 font-medium">Subject: {previewEmail.subject}</p>
              <pre className="text-[10px] text-zinc-500 whitespace-pre-wrap leading-relaxed bg-zinc-900/60 border border-zinc-800 rounded p-2 max-h-48 overflow-y-auto">
                {previewEmail.body}
              </pre>
              <button
                onClick={() => setShowEmailPreview(false)}
                className="text-[10px] text-zinc-700 hover:text-zinc-500"
              >
                Hide preview
              </button>
            </div>
          )}
        </div>

        {/* Email history section */}
        <div className="px-5 py-4 space-y-2">
          <button
            onClick={handleLoadHistory}
            className="flex items-center gap-1.5 text-[10px] text-zinc-600 uppercase tracking-widest font-medium hover:text-zinc-400 transition-colors w-full"
          >
            <Mail size={10} />
            Email History
            {showHistory ? <ChevronUp size={10} className="ml-auto" /> : <ChevronDown size={10} className="ml-auto" />}
          </button>

          {showHistory && (
            <div className="space-y-2 mt-1">
              {emailHistory.length === 0 ? (
                <p className="text-[10px] text-zinc-700">No emails sent yet.</p>
              ) : (
                emailHistory.map((email) => (
                  <div key={email.id} className="border border-zinc-800 rounded p-2 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-zinc-400 font-medium">
                        {STEP_LABELS[email.sequence_step] ?? `Step ${email.sequence_step}`}
                      </span>
                      <span className={clsx("text-[10px]", EMAIL_STATUS_COLORS[email.status])}>
                        {email.status}
                      </span>
                    </div>
                    <p className="text-[10px] text-zinc-600 truncate">{email.subject}</p>
                    {email.sent_at && (
                      <p className="text-[10px] text-zinc-700">{new Date(email.sent_at).toLocaleString()}</p>
                    )}
                    <button
                      onClick={() => setExpandedEmailId(expandedEmailId === email.id ? null : email.id)}
                      className="text-[10px] text-zinc-700 hover:text-zinc-500"
                    >
                      {expandedEmailId === email.id ? "Hide body" : "Show body"}
                    </button>
                    {expandedEmailId === email.id && (
                      <pre className="text-[10px] text-zinc-500 whitespace-pre-wrap leading-relaxed bg-zinc-900/60 rounded p-1.5 mt-1 max-h-40 overflow-y-auto">
                        {email.body}
                      </pre>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Website generator section */}
        <div className="px-5 py-4 space-y-2.5">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
            <Code size={10} />
            Website Generator
          </span>
          <button
            onClick={handleGenerateSite}
            disabled={generatingSite}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-md text-xs font-medium border border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {generatingSite ? <Loader2 size={12} className="animate-spin" /> : <Code size={12} />}
            {generatingSite ? "Generating…" : "Generate website spec"}
          </button>

          {showSpec && websiteSpec && (
            <div className="space-y-2 mt-1">
              <div className="bg-zinc-900/60 border border-zinc-800 rounded p-2 space-y-1.5">
                <p className="text-xs text-zinc-200 font-semibold">{websiteSpec.hero_headline}</p>
                <p className="text-[10px] text-zinc-500 italic">{websiteSpec.tagline}</p>
                <p className="text-[10px] text-zinc-600">{websiteSpec.hero_subheadline}</p>
                <div className="flex gap-1 mt-1">
                  {Object.entries(websiteSpec.color_palette).map(([name, hex]) => (
                    <div key={name} className="flex items-center gap-1">
                      <span
                        className="w-3 h-3 rounded-sm border border-zinc-700"
                        style={{ backgroundColor: hex }}
                        title={`${name}: ${hex}`}
                      />
                    </div>
                  ))}
                  <span className="text-[10px] text-zinc-700 ml-1">{websiteSpec.design_direction}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCopySpec}
                  className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all"
                >
                  {specCopied ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
                  {specCopied ? "Copied!" : "Copy JSON"}
                </button>
                <button
                  onClick={() => setShowSpec(false)}
                  className="text-[10px] text-zinc-700 hover:text-zinc-500 px-2"
                >
                  Hide
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Meta section */}
        <div className="px-5 py-4 space-y-2">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium block">
            Details
          </span>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <p className="text-zinc-700 text-[10px] mb-0.5">Source</p>
              <p className="text-zinc-400 capitalize">{lead.source ?? "—"}</p>
            </div>
            <div>
              <p className="text-zinc-700 text-[10px] mb-0.5">Category</p>
              <p className="text-zinc-400 capitalize">{lead.category ?? "—"}</p>
            </div>
            {lead.created_at && (
              <div className="col-span-2">
                <p className="text-zinc-700 text-[10px] mb-0.5">Added</p>
                <p className="text-zinc-400">{new Date(lead.created_at).toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-3.5 border-t border-zinc-800/60 flex items-center justify-between">
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="flex items-center gap-1.5 text-xs text-zinc-700 hover:text-red-400 transition-colors"
        >
          <Trash2 size={12} />
          {deleting ? "Deleting…" : "Delete lead"}
        </button>
        <button
          onClick={onClose}
          className="text-xs text-zinc-600 hover:text-zinc-400 transition-colors"
        >
          Close
        </button>
      </div>
    </aside>
  );
}

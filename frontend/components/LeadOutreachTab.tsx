"use client";

import { useState } from "react";
import { Send, Mail, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import { OUTREACH_STATUS_LABELS } from "@/lib/constants";
import type { Lead, EmailRecord } from "@/lib/types";

interface Props {
  lead: Lead;
  outreachStatus: string;
  onOutreachStatusChange: (status: string) => void;
  onUpdate: (id: string, data: { outreach_status?: string }) => Promise<Lead>;
}

const STEP_LABELS: Record<number, string> = { 0: "Initial email", 1: "Follow-up 1", 2: "Follow-up 2" };
const EMAIL_STATUS_COLORS: Record<string, string> = { sent: "text-emerald-400", opened: "text-blue-400", failed: "text-red-400", pending: "text-zinc-500" };

export function LeadOutreachTab({ lead, outreachStatus, onOutreachStatusChange, onUpdate }: Props) {
  const [sendingOutreach, setSendingOutreach] = useState(false);
  const [outreachError, setOutreachError] = useState<string | null>(null);
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [previewEmail, setPreviewEmail] = useState<{ subject: string; body: string } | null>(null);
  const [emailHistory, setEmailHistory] = useState<EmailRecord[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [expandedEmailId, setExpandedEmailId] = useState<string | null>(null);

  const canSendOutreach = !!lead.email && !["emailed_3", "bounced", "opted_out"].includes(outreachStatus);
  const sendLabel =
    outreachStatus === "idle" || outreachStatus === "queued" ? "Analyze & Send Email"
    : outreachStatus === "emailed_1" || outreachStatus === "emailed_2" ? "Send Follow-up"
    : outreachStatus === "emailed_3" ? "Max follow-ups sent"
    : outreachStatus === "bounced" ? "Email bounced"
    : "Send Email";

  const handleSendOutreach = async (dryRun = false) => {
    setSendingOutreach(true);
    setOutreachError(null);
    setPreviewEmail(null);
    try {
      const result = await api.sendOutreach(lead.id, dryRun);
      if (dryRun) {
        setPreviewEmail({ subject: result.subject, body: result.body });
        setShowEmailPreview(true);
      } else if (result.status === "sent") {
        const newStatus = `emailed_${(lead.follow_up_count ?? 0) + 1}`;
        onOutreachStatusChange(newStatus);
        await onUpdate(lead.id, { outreach_status: newStatus });
        const history = await api.getEmailHistory(lead.id);
        setEmailHistory(history);
        setHistoryLoaded(true);
        setShowHistory(true);
      } else {
        setOutreachError(result.error ?? "Send failed");
      }
    } catch (e: unknown) {
      setOutreachError(e instanceof Error ? e.message : "Unknown error");
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

  return (
    <div className="divide-y divide-zinc-800/60">
      {/* Send controls */}
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
            <Send size={10} /> Outreach
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
            {sendingOutreach ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
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
          <p className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 rounded px-2 py-1.5">{outreachError}</p>
        )}

        {showEmailPreview && previewEmail && (
          <div className="space-y-1.5 mt-1">
            <p className="text-[10px] text-zinc-500 font-medium">Subject: {previewEmail.subject}</p>
            <pre className="text-[10px] text-zinc-500 whitespace-pre-wrap leading-relaxed bg-zinc-900/60 border border-zinc-800 rounded p-2 max-h-48 overflow-y-auto">
              {previewEmail.body}
            </pre>
            <button onClick={() => setShowEmailPreview(false)} className="text-[10px] text-zinc-700 hover:text-zinc-500">Hide preview</button>
          </div>
        )}
      </div>

      {/* Email history */}
      <div className="px-5 py-4 space-y-2">
        <button
          onClick={handleLoadHistory}
          className="flex items-center gap-1.5 text-[10px] text-zinc-600 uppercase tracking-widest font-medium hover:text-zinc-400 transition-colors w-full"
        >
          <Mail size={10} /> Email History
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
                    <span className="text-[10px] text-zinc-400 font-medium">{STEP_LABELS[email.sequence_step] ?? `Step ${email.sequence_step}`}</span>
                    <span className={clsx("text-[10px]", EMAIL_STATUS_COLORS[email.status])}>{email.status}</span>
                  </div>
                  <p className="text-[10px] text-zinc-600 truncate">{email.subject}</p>
                  {email.sent_at && <p className="text-[10px] text-zinc-700">{new Date(email.sent_at).toLocaleString()}</p>}
                  <button onClick={() => setExpandedEmailId(expandedEmailId === email.id ? null : email.id)} className="text-[10px] text-zinc-700 hover:text-zinc-500">
                    {expandedEmailId === email.id ? "Hide body" : "Show body"}
                  </button>
                  {expandedEmailId === email.id && (
                    <pre className="text-[10px] text-zinc-500 whitespace-pre-wrap leading-relaxed bg-zinc-900/60 rounded p-1.5 mt-1 max-h-40 overflow-y-auto">{email.body}</pre>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

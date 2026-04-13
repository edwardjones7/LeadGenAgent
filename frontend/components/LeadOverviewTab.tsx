"use client";

import { useState } from "react";
import { Phone, Mail, Globe, ExternalLink, Copy, Check, Brain, Loader2, Sparkles } from "lucide-react";
import clsx from "clsx";
import { ScoreBadge } from "./ScoreBadge";
import { LEAD_STATUSES } from "@/lib/constants";
import { api } from "@/lib/api";
import type { Lead, LeadStatus, AiAnalysis } from "@/lib/types";

interface Props {
  lead: Lead;
  aiAnalysis: AiAnalysis | null;
  onStatusChange: (status: LeadStatus) => void;
  saving: boolean;
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
    <button onClick={handleCopy} className="opacity-0 group-hover:opacity-100 text-zinc-600 hover:text-zinc-300 transition-all">
      {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
    </button>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = (score / 10) * 100;
  const color = score >= 9 ? "bg-[#a200ff]" : score >= 7 ? "bg-red-500" : score >= 4 ? "bg-amber-500" : "bg-zinc-600";
  return (
    <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
      <div className={clsx("h-full rounded-full transition-all", color, score >= 9 && "shadow-[0_0_8px_rgba(162,0,255,0.6)]")} style={{ width: `${pct}%` }} />
    </div>
  );
}

const STATUS_STYLES: Record<LeadStatus, { active: string; inactive: string }> = {
  New: { active: "bg-[#a200ff]/15 border-[#a200ff]/50 text-[#c878ff]", inactive: "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400" },
  Contacted: { active: "bg-blue-500/15 border-blue-500/40 text-blue-300", inactive: "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400" },
  Closed: { active: "bg-zinc-700/40 border-zinc-600/50 text-zinc-400", inactive: "border-zinc-800 text-zinc-600 hover:border-zinc-700 hover:text-zinc-400" },
};

const SEVERITY_COLORS: Record<string, string> = {
  low: "bg-zinc-800 text-zinc-400 border-zinc-700",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  high: "bg-red-500/15 text-red-400 border-red-500/30",
};

export function LeadOverviewTab({ lead, aiAnalysis: initialAnalysis, onStatusChange, saving }: Props) {
  const scoreReasons = lead.score_reason ? lead.score_reason.split(";").map((s) => s.trim()).filter(Boolean) : [];
  const status = lead.status;
  const [analysis, setAnalysis] = useState<AiAnalysis | null>(initialAnalysis);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const res = await api.analyzeOutreach(lead.id);
      setAnalysis(res.ai_analysis);
    } catch (e) {
      setAnalyzeError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="divide-y divide-zinc-800/60">
      {/* Score */}
      <div className="px-5 py-4 space-y-3">
        <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium">Lead Score</span>
        <div className="flex items-center gap-3">
          <ScoreBadge score={lead.score} large />
          <div className="flex-1 space-y-1.5">
            <ScoreBar score={lead.score} />
            <p className="text-[10px] text-zinc-600">
              {lead.score >= 9 ? "Hot lead — very weak web presence" : lead.score >= 7 ? "Strong lead — clear website issues" : lead.score >= 4 ? "Moderate lead" : "Low priority"}
            </p>
          </div>
        </div>
        {scoreReasons.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {scoreReasons.map((r, i) => (
              <span key={i} className="text-[10px] text-zinc-500 bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 leading-relaxed">{r}</span>
            ))}
          </div>
        )}
      </div>

      {/* AI Analysis */}
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
            <Brain size={10} /> AI Analysis
          </span>
          <div className="flex items-center gap-2">
            {analysis && (
              <span className={clsx("text-[10px] px-1.5 py-0.5 rounded border font-medium", SEVERITY_COLORS[analysis.severity])}>{analysis.severity}</span>
            )}
            <button
              onClick={runAnalysis}
              disabled={analyzing}
              className="flex items-center gap-1 px-2 py-1 rounded border border-[#a200ff]/40 text-[10px] text-[#c878ff] hover:bg-[#a200ff]/15 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzing ? <Loader2 size={10} className="animate-spin" /> : <Sparkles size={10} />}
              {analysis ? "Re-analyze" : "Analyze"}
            </button>
          </div>
        </div>

        {analyzeError && (
          <p className="text-[10px] text-red-400">{analyzeError}</p>
        )}

        {analysis ? (
          <div className="space-y-3">
            <p className="text-xs text-zinc-300 leading-relaxed">{analysis.summary}</p>

            {analysis.business_overview && (
              <div>
                <p className="text-[9px] text-zinc-600 uppercase tracking-widest font-medium mb-1">Business</p>
                <p className="text-[11px] text-zinc-400 leading-relaxed">{analysis.business_overview}</p>
              </div>
            )}

            {analysis.opportunity && (
              <div>
                <p className="text-[9px] text-[#c060ff] uppercase tracking-widest font-medium mb-1">Opportunity for Elenos</p>
                <p className="text-[11px] text-zinc-300 leading-relaxed bg-[#a200ff]/5 border border-[#a200ff]/20 rounded p-2">{analysis.opportunity}</p>
              </div>
            )}

            {analysis.problems.length > 0 && (
              <div>
                <p className="text-[9px] text-zinc-600 uppercase tracking-widest font-medium mb-1.5">Problems</p>
                <ul className="space-y-1">
                  {analysis.problems.map((p, i) => (
                    <li key={i} className="text-[10px] text-zinc-500 leading-relaxed">
                      <span className="text-zinc-400 font-medium">{p.category}:</span> {p.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysis.personalization_hooks?.length > 0 && (
              <div>
                <p className="text-[9px] text-zinc-600 uppercase tracking-widest font-medium mb-1.5">Hooks for outreach</p>
                <ul className="space-y-0.5 list-disc list-inside">
                  {analysis.personalization_hooks.map((h, i) => (
                    <li key={i} className="text-[10px] text-zinc-500 leading-relaxed">{h}</li>
                  ))}
                </ul>
              </div>
            )}

            {analysis.gap_analysis && (
              <div>
                <p className="text-[9px] text-zinc-600 uppercase tracking-widest font-medium mb-1.5">Gaps</p>
                <div className="grid grid-cols-1 gap-1 text-[10px] text-zinc-500">
                  {analysis.gap_analysis.missing_pages && analysis.gap_analysis.missing_pages.length > 0 && (
                    <div><span className="text-zinc-400">Missing pages:</span> {analysis.gap_analysis.missing_pages.join(", ")}</div>
                  )}
                  {analysis.gap_analysis.missing_trust_signals && analysis.gap_analysis.missing_trust_signals.length > 0 && (
                    <div><span className="text-zinc-400">Missing trust signals:</span> {analysis.gap_analysis.missing_trust_signals.join(", ")}</div>
                  )}
                  {analysis.gap_analysis.cta_quality && (
                    <div><span className="text-zinc-400">CTAs:</span> {analysis.gap_analysis.cta_quality}</div>
                  )}
                  {analysis.gap_analysis.contact_accessibility && (
                    <div><span className="text-zinc-400">Contact:</span> {analysis.gap_analysis.contact_accessibility}</div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-[10px] text-zinc-700">
            Click <span className="text-[#c878ff]">Analyze</span> to generate a full business opportunity brief.
          </p>
        )}
      </div>

      {/* Status */}
      <div className="px-5 py-4 space-y-2.5">
        <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium block">
          Status {saving && <span className="text-zinc-700 normal-case tracking-normal">saving…</span>}
        </span>
        <div className="flex gap-1.5">
          {LEAD_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => onStatusChange(s as LeadStatus)}
              disabled={saving}
              className={clsx("flex-1 py-1.5 rounded-md text-xs font-medium border transition-all", status === s ? STATUS_STYLES[s as LeadStatus].active : STATUS_STYLES[s as LeadStatus].inactive)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Contact */}
      <div className="px-5 py-4 space-y-3">
        <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium block">Contact</span>
        {lead.phone ? (
          <div className="group flex items-center justify-between">
            <a href={`tel:${lead.phone}`} className="flex items-center gap-2.5 text-sm text-zinc-300 hover:text-white transition-colors">
              <Phone size={13} className="text-zinc-600 shrink-0" /> {lead.phone}
            </a>
            <CopyButton value={lead.phone} />
          </div>
        ) : (
          <div className="flex items-center gap-2.5 text-sm text-zinc-700"><Phone size={13} className="shrink-0" /> No phone</div>
        )}
        {lead.email ? (
          <div className="group flex items-center justify-between">
            <a href={`mailto:${lead.email}`} className="flex items-center gap-2.5 text-sm text-[#c060ff] hover:text-[#d580ff] transition-colors truncate">
              <Mail size={13} className="text-zinc-600 shrink-0" /> <span className="truncate">{lead.email}</span>
            </a>
            <CopyButton value={lead.email} />
          </div>
        ) : (
          <div className="flex items-center gap-2.5 text-sm text-zinc-700"><Mail size={13} className="shrink-0" /> No email found</div>
        )}
        {lead.website_url ? (
          <div className="group flex items-center justify-between gap-2">
            <a href={lead.website_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2.5 text-sm text-zinc-400 hover:text-zinc-200 transition-colors min-w-0">
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

      {/* Meta */}
      <div className="px-5 py-4 space-y-2">
        <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium block">Details</span>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <div><p className="text-zinc-700 text-[10px] mb-0.5">Source</p><p className="text-zinc-400 capitalize">{lead.source ?? "—"}</p></div>
          <div><p className="text-zinc-700 text-[10px] mb-0.5">Category</p><p className="text-zinc-400 capitalize">{lead.category ?? "—"}</p></div>
          {lead.created_at && (
            <div className="col-span-2"><p className="text-zinc-700 text-[10px] mb-0.5">Added</p><p className="text-zinc-400">{new Date(lead.created_at).toLocaleString()}</p></div>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { Code, Copy, Check, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Lead, WebsiteSpec } from "@/lib/types";

interface Props {
  lead: Lead;
}

export function LeadWebsiteTab({ lead }: Props) {
  const [generating, setGenerating] = useState(false);
  const [spec, setSpec] = useState<WebsiteSpec | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await api.generateWebsiteSpec(lead.id);
      setSpec(result);
    } catch (e: unknown) {
      alert(`Site generation failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!spec) return;
    await navigator.clipboard.writeText(JSON.stringify(spec, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="px-5 py-4 space-y-3">
      <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
        <Code size={10} /> Website Generator
      </span>
      <button
        onClick={handleGenerate}
        disabled={generating}
        className="w-full flex items-center justify-center gap-2 py-2 rounded-md text-xs font-medium border border-zinc-800 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {generating ? <Loader2 size={12} className="animate-spin" /> : <Code size={12} />}
        {generating ? "Generating…" : "Generate website spec"}
      </button>

      {spec && (
        <div className="space-y-2 mt-1">
          <div className="bg-zinc-900/60 border border-zinc-800 rounded p-3 space-y-2">
            <p className="text-xs text-zinc-200 font-semibold">{spec.hero_headline}</p>
            <p className="text-[10px] text-zinc-500 italic">{spec.tagline}</p>
            <p className="text-[10px] text-zinc-600">{spec.hero_subheadline}</p>
            <div className="flex gap-1 mt-1">
              {Object.entries(spec.color_palette).map(([name, hex]) => (
                <span key={name} className="w-3 h-3 rounded-sm border border-zinc-700" style={{ backgroundColor: hex }} title={`${name}: ${hex}`} />
              ))}
              <span className="text-[10px] text-zinc-700 ml-1">{spec.design_direction}</span>
            </div>
            {spec.sections.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-zinc-800/60">
                {spec.sections.map((s, i) => (
                  <div key={i}>
                    <p className="text-[10px] text-zinc-400 font-medium">{s.headline}</p>
                    <p className="text-[10px] text-zinc-600 leading-relaxed">{s.body_copy}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={handleCopy} className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all">
              {copied ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
              {copied ? "Copied!" : "Copy JSON"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

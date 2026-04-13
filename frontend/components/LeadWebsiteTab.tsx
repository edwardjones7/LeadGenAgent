"use client";

import { useState } from "react";
import { Code, Copy, Check, Loader2, Download } from "lucide-react";
import { api } from "@/lib/api";
import type { Lead, WebsiteSpec } from "@/lib/types";

interface Props {
  lead: Lead;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] text-[#c060ff] uppercase tracking-widest font-semibold mb-1.5">{title}</p>
      <div className="text-[11px] text-zinc-400 leading-relaxed space-y-1">{children}</div>
    </div>
  );
}

function Bullets({ items }: { items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <ul className="list-disc list-inside space-y-0.5">
      {items.map((s, i) => (
        <li key={i} className="text-[11px] text-zinc-400 leading-relaxed">{s}</li>
      ))}
    </ul>
  );
}

function toMarkdown(spec: WebsiteSpec): string {
  const lines: string[] = [];
  lines.push(`# ${spec.project_title ?? spec.business_name}`);
  lines.push("");
  if (spec.overview) lines.push(spec.overview, "");
  if (spec.objectives?.length) {
    lines.push("## Objectives", ...spec.objectives.map((o) => `- ${o}`), "");
  }
  if (spec.target_audience) {
    lines.push("## Target Audience");
    if (spec.target_audience.primary?.length) {
      lines.push("**Primary**", ...spec.target_audience.primary.map((p) => `- ${p}`));
    }
    if (spec.target_audience.secondary?.length) {
      lines.push("**Secondary**", ...spec.target_audience.secondary.map((p) => `- ${p}`));
    }
    lines.push("");
  }
  if (spec.user_personas?.length) {
    lines.push("## User Personas");
    for (const p of spec.user_personas) {
      lines.push(`### ${p.name}`);
      if (p.bio) lines.push(p.bio);
      if (p.needs?.length) lines.push(...p.needs.map((n) => `- ${n}`));
      lines.push("");
    }
  }
  if (spec.core_features?.length) {
    lines.push("## Core Features");
    for (const f of spec.core_features) {
      lines.push(`### ${f.section}`);
      if (f.purpose) lines.push(f.purpose);
      if (f.components?.length) lines.push(...f.components.map((c) => `- ${c}`));
      lines.push("");
    }
  }
  if (spec.design) {
    lines.push("## Design");
    if (spec.design.style_direction) lines.push(spec.design.style_direction);
    if (spec.design.typography) lines.push(`**Typography:** ${spec.design.typography}`);
    if (spec.design.color_palette) {
      lines.push("**Color palette:**");
      for (const [k, v] of Object.entries(spec.design.color_palette)) lines.push(`- ${k}: ${v}`);
    }
    if (spec.design.ui_notes?.length) {
      lines.push("**UI notes:**", ...spec.design.ui_notes.map((n) => `- ${n}`));
    }
    lines.push("");
  }
  if (spec.ux_requirements?.length) {
    lines.push("## UX Requirements", ...spec.ux_requirements.map((u) => `- ${u}`), "");
  }
  if (spec.technical_requirements) {
    lines.push("## Technical Requirements");
    if (spec.technical_requirements.recommended_platform) lines.push(`**Platform:** ${spec.technical_requirements.recommended_platform}`);
    if (spec.technical_requirements.hosting) lines.push(`**Hosting:** ${spec.technical_requirements.hosting}`);
    if (spec.technical_requirements.integrations?.length) {
      lines.push("**Integrations:**", ...spec.technical_requirements.integrations.map((i) => `- ${i}`));
    }
    lines.push("");
  }
  if (spec.success_metrics?.length) lines.push("## Success Metrics", ...spec.success_metrics.map((m) => `- ${m}`), "");
  if (spec.future_enhancements?.length) lines.push("## Future Enhancements", ...spec.future_enhancements.map((f) => `- ${f}`), "");
  if (spec.sitemap?.length) lines.push("## Sitemap", ...spec.sitemap.map((s) => `- ${s}`), "");
  if (spec.copy_tone?.length) lines.push("## Copy Tone", ...spec.copy_tone.map((t) => `- ${t}`), "");
  if (spec.key_differentiator) lines.push("## Key Differentiator", spec.key_differentiator, "");
  lines.push("## Homepage");
  lines.push(`**Hero:** ${spec.hero_headline}`);
  if (spec.tagline) lines.push(`**Tagline:** ${spec.tagline}`);
  lines.push(spec.hero_subheadline);
  lines.push(`**SEO title:** ${spec.seo_title}`);
  lines.push(`**Meta description:** ${spec.meta_description}`);
  lines.push(`**Suggested domain:** ${spec.suggested_domain}`);
  return lines.join("\n");
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
      alert(`PRD generation failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async () => {
    if (!spec) return;
    await navigator.clipboard.writeText(toMarkdown(spec));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleDownload = () => {
    if (!spec) return;
    const blob = new Blob([toMarkdown(spec)], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${spec.business_name.replace(/\s+/g, "_")}_PRD.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const palette = spec?.design?.color_palette ?? spec?.color_palette;

  return (
    <div className="px-5 py-4 space-y-3">
      <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium flex items-center gap-1.5">
        <Code size={10} /> Website PRD Generator
      </span>
      <button
        onClick={handleGenerate}
        disabled={generating}
        className="w-full flex items-center justify-center gap-2 py-2 rounded-md text-xs font-medium border border-[#a200ff]/40 text-[#c878ff] hover:bg-[#a200ff]/15 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {generating ? <Loader2 size={12} className="animate-spin" /> : <Code size={12} />}
        {generating ? "Generating PRD…" : spec ? "Regenerate PRD" : "Generate PRD"}
      </button>

      {spec && (
        <div className="space-y-4 mt-2">
          {/* Title block */}
          <div className="bg-zinc-900/60 border border-zinc-800 rounded p-3 space-y-2">
            <p className="text-xs text-zinc-100 font-bold">{spec.project_title ?? spec.business_name}</p>
            {spec.tagline && <p className="text-[10px] text-[#c060ff] italic">{spec.tagline}</p>}
            {spec.overview && <p className="text-[11px] text-zinc-400 leading-relaxed">{spec.overview}</p>}
            {palette && (
              <div className="flex gap-1 pt-1">
                {Object.entries(palette).map(([name, hex]) => (
                  <span key={name} className="w-3 h-3 rounded-sm border border-zinc-700" style={{ backgroundColor: hex }} title={`${name}: ${hex}`} />
                ))}
              </div>
            )}
          </div>

          <div className="space-y-4">
            {spec.objectives?.length ? <Section title="Objectives"><Bullets items={spec.objectives} /></Section> : null}

            {spec.target_audience && (
              <Section title="Target Audience">
                {spec.target_audience.primary?.length ? (
                  <div>
                    <p className="text-zinc-500 font-medium">Primary</p>
                    <Bullets items={spec.target_audience.primary} />
                  </div>
                ) : null}
                {spec.target_audience.secondary?.length ? (
                  <div>
                    <p className="text-zinc-500 font-medium">Secondary</p>
                    <Bullets items={spec.target_audience.secondary} />
                  </div>
                ) : null}
              </Section>
            )}

            {spec.user_personas?.length ? (
              <Section title="User Personas">
                <div className="space-y-2">
                  {spec.user_personas.map((p, i) => (
                    <div key={i} className="bg-zinc-900/40 border border-zinc-800/60 rounded p-2">
                      <p className="text-zinc-300 font-medium">{p.name}</p>
                      {p.bio && <p className="text-zinc-500">{p.bio}</p>}
                      <Bullets items={p.needs} />
                    </div>
                  ))}
                </div>
              </Section>
            ) : null}

            {spec.core_features?.length ? (
              <Section title="Core Features">
                <div className="space-y-2">
                  {spec.core_features.map((f, i) => (
                    <div key={i}>
                      <p className="text-zinc-300 font-medium">{f.section}</p>
                      {f.purpose && <p className="text-zinc-500 mb-0.5">{f.purpose}</p>}
                      <Bullets items={f.components} />
                    </div>
                  ))}
                </div>
              </Section>
            ) : null}

            {spec.design && (
              <Section title="Design">
                {spec.design.style_direction && <p>{spec.design.style_direction}</p>}
                {spec.design.typography && <p><span className="text-zinc-500">Typography:</span> {spec.design.typography}</p>}
                <Bullets items={spec.design.ui_notes} />
              </Section>
            )}

            {spec.ux_requirements?.length ? <Section title="UX Requirements"><Bullets items={spec.ux_requirements} /></Section> : null}

            {spec.technical_requirements && (
              <Section title="Technical">
                {spec.technical_requirements.recommended_platform && (
                  <p><span className="text-zinc-500">Platform:</span> {spec.technical_requirements.recommended_platform}</p>
                )}
                {spec.technical_requirements.hosting && (
                  <p><span className="text-zinc-500">Hosting:</span> {spec.technical_requirements.hosting}</p>
                )}
                <Bullets items={spec.technical_requirements.integrations} />
              </Section>
            )}

            {spec.success_metrics?.length ? <Section title="KPIs"><Bullets items={spec.success_metrics} /></Section> : null}
            {spec.future_enhancements?.length ? <Section title="Future Enhancements"><Bullets items={spec.future_enhancements} /></Section> : null}
            {spec.sitemap?.length ? <Section title="Sitemap"><Bullets items={spec.sitemap} /></Section> : null}
            {spec.copy_tone?.length ? <Section title="Copy Tone"><Bullets items={spec.copy_tone} /></Section> : null}
            {spec.key_differentiator ? <Section title="Key Differentiator"><p>{spec.key_differentiator}</p></Section> : null}

            <Section title="Homepage Copy">
              <p><span className="text-zinc-500">Hero:</span> <span className="text-zinc-300 font-medium">{spec.hero_headline}</span></p>
              <p>{spec.hero_subheadline}</p>
              <p><span className="text-zinc-500">SEO title:</span> {spec.seo_title}</p>
              <p><span className="text-zinc-500">Meta description:</span> {spec.meta_description}</p>
              <p><span className="text-zinc-500">Suggested domain:</span> {spec.suggested_domain}</p>
            </Section>
          </div>

          <div className="flex gap-2 pt-1">
            <button onClick={handleCopy} className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all">
              {copied ? <Check size={10} className="text-emerald-400" /> : <Copy size={10} />}
              {copied ? "Copied!" : "Copy Markdown"}
            </button>
            <button onClick={handleDownload} className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-[10px] border border-zinc-800 rounded text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all">
              <Download size={10} /> Download .md
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useRef, useEffect } from "react";
import { X, Send, Loader2, Trash2, Minus, Sparkles } from "lucide-react";
import Image from "next/image";
import { useChat } from "@/hooks/useChat";
import type { Lead, PageContext } from "@/lib/types";

interface Props {
  onClose: () => void;
  selectedLead: Lead | null;
  visibleLeadIds: string[];
  filters: { status?: string; min_score?: number };
  searchState: { location: string; categories: string[] };
  onLeadsMutated: () => void;
  detailOpen: boolean;
}

const WELCOME_SUGGESTIONS = [
  "Find leads in my area",
  "Show my top scored leads",
  "Analyze a website",
];

function AlexAvatar({ size = 28 }: { size?: number }) {
  return (
    <Image
      src="/alex-avatar.svg"
      alt="Alex"
      width={size}
      height={size}
      className="rounded-lg shrink-0"
    />
  );
}

export function ChatPanel({
  onClose,
  selectedLead,
  visibleLeadIds,
  filters,
  searchState,
  onLeadsMutated,
  detailOpen,
}: Props) {
  const { messages, sending, sendMessage, clearHistory } = useChat();
  const [input, setInput] = useState("");
  const [minimized, setMinimized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!minimized) inputRef.current?.focus();
  }, [minimized]);

  const buildContext = (): PageContext => ({
    selected_lead: selectedLead,
    visible_lead_ids: visibleLeadIds,
    filters,
    search_state: searchState,
  });

  const handleSend = (text?: string) => {
    const msg = text || input;
    if (!msg.trim() || sending) return;
    setInput("");
    sendMessage(msg.trim(), buildContext(), onLeadsMutated);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      className={`fixed z-50 ${detailOpen ? "right-[436px]" : "right-4"} bottom-4 w-[400px] transition-all duration-200`}
      style={{ height: minimized ? "auto" : "560px" }}
    >
      <div className="h-full flex flex-col bg-[#0c0c14] border border-zinc-800/80 rounded-2xl shadow-2xl shadow-black/40 overflow-hidden">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-zinc-800/60 bg-gradient-to-r from-[#0c0c14] to-[#12101f]">
          <div className="flex items-center gap-2.5">
            <div className="relative">
              <AlexAvatar size={28} />
              <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 rounded-full border-2 border-[#0c0c14] shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-zinc-100 leading-tight">Alex</span>
              <span className="text-[10px] text-zinc-500 leading-tight">Elenos AI Assistant</span>
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            <button onClick={clearHistory} className="p-1.5 rounded-lg hover:bg-zinc-800/80 text-zinc-600 hover:text-zinc-300 transition-colors" title="Clear history">
              <Trash2 size={12} />
            </button>
            <button onClick={() => setMinimized((v) => !v)} className="p-1.5 rounded-lg hover:bg-zinc-800/80 text-zinc-600 hover:text-zinc-300 transition-colors" title={minimized ? "Expand" : "Minimize"}>
              <Minus size={12} />
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-800/80 text-zinc-600 hover:text-zinc-300 transition-colors">
              <X size={13} />
            </button>
          </div>
        </div>

        {!minimized && (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center text-center pt-6 pb-2 space-y-4">
                  <div className="relative">
                    <AlexAvatar size={48} />
                    <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-500 rounded-full border-2 border-[#0c0c14]" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-zinc-100">Hey, I'm Alex</p>
                    <p className="text-xs text-zinc-500 max-w-[260px] leading-relaxed">
                      Your lead intelligence assistant. I can search for prospects, analyze websites, manage your pipeline, and craft outreach.
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 w-full mt-2">
                    {WELCOME_SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => handleSend(s)}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-zinc-800 bg-zinc-900/50 text-xs text-zinc-400 hover:text-zinc-200 hover:border-[#a200ff]/40 hover:bg-[#a200ff]/5 transition-all text-left"
                      >
                        <Sparkles size={11} className="text-[#a200ff] shrink-0" />
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg) => {
                // Hide empty assistant placeholders (typing indicator handles that state)
                if (msg.role === "assistant" && !msg.content) return null;
                return (
                  <div key={msg.id} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                    {msg.role === "assistant" && <AlexAvatar size={24} />}
                    <div className={`max-w-[80%] rounded-xl px-3.5 py-2.5 text-xs leading-relaxed ${
                      msg.role === "user"
                        ? "bg-[#a200ff]/15 text-zinc-200 border border-[#a200ff]/25 rounded-br-sm"
                        : "bg-zinc-800/40 text-zinc-300 border border-zinc-700/30 rounded-bl-sm"
                    }`}>
                      <MessageContent content={msg.content} />
                    </div>
                  </div>
                );
              })}

              {sending && messages[messages.length - 1]?.role === "assistant" && !messages[messages.length - 1]?.content && (
                <div className="flex gap-2.5">
                  <AlexAvatar size={24} />
                  <div className="bg-zinc-800/40 border border-zinc-700/30 rounded-xl rounded-bl-sm px-3.5 py-2.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#a200ff] animate-pulse" />
                      <span className="w-1.5 h-1.5 rounded-full bg-[#a200ff] animate-pulse" style={{ animationDelay: "0.15s" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-[#a200ff] animate-pulse" style={{ animationDelay: "0.3s" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="shrink-0 border-t border-zinc-800/60 px-3 py-3 bg-[#0a0a12]">
              <div className="flex items-center gap-2 bg-zinc-900/80 border border-zinc-700/40 rounded-xl px-3.5 py-2 focus-within:border-[#a200ff]/40 focus-within:shadow-[0_0_12px_rgba(162,0,255,0.08)] transition-all">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Message Alex..."
                  className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-600 outline-none"
                  disabled={sending}
                />
                <button onClick={() => handleSend()} disabled={!input.trim() || sending} className="p-1.5 rounded-lg text-zinc-500 hover:text-[#a200ff] hover:bg-[#a200ff]/10 disabled:opacity-30 disabled:hover:text-zinc-500 disabled:hover:bg-transparent transition-all">
                  {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                </button>
              </div>
              {selectedLead && (
                <div className="mt-1.5 px-1 text-[10px] text-zinc-600 truncate flex items-center gap-1">
                  <span className="w-1 h-1 rounded-full bg-[#a200ff]/60" />
                  Viewing: {selectedLead.business_name}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MessageContent({ content }: { content: string }) {
  if (!content) return null;
  const lines = content.split("\n");
  return (
    <>
      {lines.map((line, i) => {
        const imgMatch = line.match(/^!\[([^\]]*)\]\((data:image\/[^)]+)\)$/);
        if (imgMatch) {
          return (
            <img
              key={i}
              src={imgMatch[2]}
              alt={imgMatch[1]}
              className="rounded-md border border-zinc-700 mt-1 max-w-full cursor-pointer hover:opacity-90 transition-opacity"
              onClick={() => window.open(imgMatch[2], "_blank")}
            />
          );
        }

        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        const rendered = parts.map((part, j) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return <strong key={j} className="font-semibold text-zinc-100">{part.slice(2, -2)}</strong>;
          }
          return <span key={j}>{part}</span>;
        });
        if (line.startsWith("> ")) {
          return <div key={i} className="text-[#a200ff]/60 text-[10px] italic mt-1">{rendered}</div>;
        }
        return <span key={i}>{rendered}{i < lines.length - 1 && <br />}</span>;
      })}
    </>
  );
}

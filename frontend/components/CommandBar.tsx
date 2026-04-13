"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, Trash2, ChevronDown } from "lucide-react";
import clsx from "clsx";
import { useChat } from "@/hooks/useChat";
import type { Lead, PageContext } from "@/lib/types";

interface Props {
  selectedLead: Lead | null;
  visibleLeadIds: string[];
  filters: Record<string, unknown>;
  searchState: { location: string; categories: string[] };
  onLeadsMutated: () => void;
}

const SUGGESTIONS = [
  "Search for plumbers in Dallas, TX",
  "Find emails for top leads",
  "Analyze weak websites in my list",
  "Show me leads with score 8+",
];

export function CommandBar({ selectedLead, visibleLeadIds, filters, searchState, onLeadsMutated }: Props) {
  const { messages, sending, sendMessage, clearHistory } = useChat();
  const [input, setInput] = useState("");
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current && expanded) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, expanded]);

  const handleSend = () => {
    if (!input.trim() || sending) return;
    const ctx: PageContext = {
      selected_lead: selectedLead,
      visible_lead_ids: visibleLeadIds,
      filters,
      search_state: searchState,
    };
    sendMessage(input.trim(), ctx, onLeadsMutated);
    setInput("");
    setExpanded(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === "Escape") {
      setExpanded(false);
      inputRef.current?.blur();
    }
  };

  const handleSuggestion = (text: string) => {
    setInput(text);
    inputRef.current?.focus();
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="w-full">
      <div className={clsx(
        "border border-zinc-800 rounded-xl bg-[#111113] transition-all duration-200",
        expanded && "shadow-lg shadow-black/20"
      )}>
        {/* Expanded chat thread */}
        {expanded && hasMessages && (
          <div className="border-b border-zinc-800/50">
            <div className="flex items-center justify-between px-4 pt-3 pb-1">
              <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Alex</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={clearHistory}
                  className="p-1 rounded hover:bg-zinc-800/50 text-zinc-600 hover:text-zinc-400 transition-colors"
                  title="Clear history"
                >
                  <Trash2 size={12} />
                </button>
                <button
                  onClick={() => setExpanded(false)}
                  className="p-1 rounded hover:bg-zinc-800/50 text-zinc-600 hover:text-zinc-400 transition-colors"
                >
                  <ChevronDown size={12} />
                </button>
              </div>
            </div>
            <div ref={scrollRef} className="max-h-[320px] overflow-y-auto px-4 pb-3 space-y-3">
              {messages.map((msg) => (
                <div key={msg.id} className={clsx("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                  <div className={clsx(
                    "max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed",
                    msg.role === "user"
                      ? "bg-violet-500/12 text-zinc-200 border border-violet-500/20"
                      : "bg-zinc-800/50 text-zinc-300 border border-zinc-800/50"
                  )}>
                    {msg.content.split("\n").map((line, i) => {
                      if (line.startsWith("![screenshot]")) {
                        const src = line.match(/\(([^)]+)\)/)?.[1];
                        return src ? <img key={i} src={src} alt="screenshot" className="rounded mt-2 max-w-full" /> : null;
                      }
                      if (line.startsWith("> ")) {
                        return <p key={i} className="text-xs text-violet-400 italic mt-1">{line.slice(2)}</p>;
                      }
                      // Bold
                      const formatted = line.replace(/\*\*([^*]+)\*\*/g, "<strong class='font-semibold text-zinc-100'>$1</strong>");
                      return <p key={i} dangerouslySetInnerHTML={{ __html: formatted || "&nbsp;" }} />;
                    })}
                    {msg.role === "assistant" && msg.content === "" && sending && (
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse [animation-delay:150ms]" />
                        <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse [animation-delay:300ms]" />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Input bar */}
        <div className="flex items-center gap-3 px-4 py-3">
          <Sparkles size={16} className="shrink-0 text-violet-400" />
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => hasMessages && setExpanded(true)}
            placeholder="Ask Alex anything... search, analyze, send outreach"
            className="flex-1 bg-transparent text-sm text-zinc-200 placeholder:text-zinc-600 outline-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className={clsx(
              "p-2 rounded-lg transition-all",
              input.trim() && !sending
                ? "bg-violet-600 hover:bg-violet-700 text-white"
                : "text-zinc-600"
            )}
          >
            {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>

        {/* Suggestion chips — only when no messages and not expanded */}
        {!expanded && !hasMessages && (
          <div className="px-4 pb-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => handleSuggestion(s)}
                className="text-xs px-3 py-1.5 rounded-full border border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

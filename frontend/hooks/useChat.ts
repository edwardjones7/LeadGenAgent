"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import type { ChatMessage, ChatSSEEvent, PageContext } from "@/lib/types";

let msgCounter = 0;
function localId() {
  return `local-${++msgCounter}-${Date.now()}`;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /* Load history on mount */
  const loadHistory = useCallback(async () => {
    try {
      const history = await api.getChatHistory();
      // Only keep user + assistant messages for display (skip raw tool messages)
      const display = history.filter((m) => m.role === "user" || m.role === "assistant");
      setMessages(display);
    } catch {
      // Ignore — table might not exist yet
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  /* Send a message and stream the response */
  const sendMessage = useCallback(
    async (text: string, context: PageContext, onLeadsMutated?: () => void) => {
      if (!text.trim() || sending) return;
      setError(null);
      setSending(true);

      // Optimistic: add user message
      const userMsg: ChatMessage = { id: localId(), role: "user", content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);

      // Placeholder for assistant response
      const assistantId = localId();
      setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);

      const controller = new AbortController();
      abortRef.current = controller;

      let mutated = false;

      try {
        const res = await api.sendChatMessage(text.trim(), context);

        if (!res.ok) {
          const errText = await res.text();
          throw new Error(`API ${res.status}: ${errText}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE lines
          const lines = buffer.split("\n");
          buffer = lines.pop() || ""; // keep incomplete line in buffer

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;

            let event: ChatSSEEvent;
            try {
              event = JSON.parse(raw);
            } catch {
              continue;
            }

            if (event.type === "chunk" && event.content) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + event.content } : m,
                ),
              );
            } else if (event.type === "tool_call") {
              // Show a status line in the assistant message
              const toolLabel = `\n> Running **${event.name}**...`;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + toolLabel } : m,
                ),
              );
            } else if (event.type === "tool_result") {
              // Clear the "Running..." line and check for screenshots / mutations
              const resultData = event.result as Record<string, unknown> | undefined;
              const screenshotB64 = resultData?.screenshot_base64 as string | undefined;

              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  let cleaned = m.content.replace(/\n> Running \*\*[^*]+\*\*\.\.\.$/, "");
                  // Embed screenshot as special marker the renderer will pick up
                  if (screenshotB64) {
                    cleaned += `\n![screenshot](data:image/png;base64,${screenshotB64})`;
                  }
                  return { ...m, content: cleaned };
                }),
              );
              const mutatingTools = ["search_leads", "add_lead", "update_lead", "delete_lead"];
              if (event.name && mutatingTools.includes(event.name)) {
                mutated = true;
              }
            } else if (event.type === "done") {
              break;
            }
          }
        }

        if (mutated && onLeadsMutated) {
          onLeadsMutated();
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: m.content || "Sorry, something went wrong." }
              : m,
          ),
        );
      } finally {
        setSending(false);
        abortRef.current = null;
      }
    },
    [sending],
  );

  const clearHistory = useCallback(async () => {
    try {
      await api.clearChatHistory();
      setMessages([]);
    } catch {
      // ignore
    }
  }, []);

  return { messages, sending, error, sendMessage, clearHistory, loadHistory };
}

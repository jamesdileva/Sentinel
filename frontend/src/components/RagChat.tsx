import { useCallback, useRef, useState, useEffect } from "react";

import { ragQuery, getChatHistory, saveChatMessage } from "../api/rag";
import ChatMessage, { type ChatMessageData } from "./ChatMessage";

interface RagChatProps {
  projectId?: string;
}

export default function RagChat({ projectId }: RagChatProps) {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);
  // v1.17.18.5 (audit2 F6): an in-flight ragQuery resolved after the user
  // switched rooms must not append the old room's answer to the new room.
  const roomRef = useRef(projectId ?? "__all__");
  roomRef.current = projectId ?? "__all__";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  useEffect(() => {
    let active = true;
    // v1.17.6.6: the all-projects chat (no `projectId`) lives in the
    // `__all__` room on the backend, so it loads and persists its history
    // like any project room instead of silently resetting on tab switches.
    const room = projectId ?? "__all__";
    setMessages([]);
    nextId.current = 1;
    setHistoryLoaded(false);
    getChatHistory(room)
      .then((rows) => {
        if (!active) return;
        setMessages(
          rows.map((row) => ({
            id: nextId.current++,
            role: row.role,
            text: row.text,
            sources: (row.sources ?? []).map((source) => ({
              source,
              content: "",
              project_id: room,
              file_path: null,
              distance: 0,
            })),
            model: row.model ?? undefined,
            generatedAt: row.created_at,
            confidence: row.confidence ?? undefined,
            error: Boolean(row.error),
          })),
        );
      })
      .catch(() => {
        // History is best-effort: a failed replay just starts a fresh chat.
      })
      .finally(() => {
        if (active) setHistoryLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  const persist = useCallback(
    (
      role: "user" | "assistant",
      text: string,
      extra?: Partial<ChatMessageData>,
    ) => {
      const room = projectId ?? "__all__";
      saveChatMessage(room, {
        role,
        text,
        sources: extra?.sources?.map((s) => s.file_path || s.source),
        model: extra?.model ?? null,
        confidence: extra?.confidence ?? null,
        error: extra?.error ? "answer failed" : null,
      }).catch(() => {
        // Persistence is best-effort — a failed save must not disturb the chat.
      });
    },
    [projectId],
  );

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      const question = input.trim();
      if (!question || loading) return;

      const userMessage = {
        id: nextId.current++,
        role: "user" as const,
        text: question,
      } as ChatMessageData;
      setMessages((current) => [...current, userMessage]);
      persist("user", question);
      setInput("");
      setLoading(true);

      const id = nextId.current++;
      const askedRoom = roomRef.current;
      try {
        const response = await ragQuery(question, projectId);
        if (roomRef.current !== askedRoom) return; // user switched rooms
        const answer = {
          id,
          role: "assistant" as const,
          text: response.answer,
          sources: response.sources,
          model: response.model,
          generatedAt: response.generated_at,
          confidence: response.confidence,
        } as ChatMessageData;
        setMessages((current) => [...current, answer]);
        // v1.17.13: the backend persists the grounded answer itself
        // (/rag/query) — a tab reload during the long local generation
        // can no longer lose it, so the client must not double-save.
      } catch (err) {
        if (roomRef.current !== askedRoom) return;
        const answer = {
          id,
          role: "assistant" as const,
          text:
            err instanceof Error
              ? `Sorry, I couldn't answer that: ${err.message}`
              : "Sorry, I couldn't answer that.",
          error: true,
        } as ChatMessageData;
        setMessages((current) => [...current, answer]);
        persist("assistant", answer.text, answer);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, projectId, persist],
  );

  return (
    <div className="flex min-h-[28rem] flex-col rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Ask about your projects
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Answers are grounded in indexed knowledge and cite their sources.
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="pt-8 text-center text-sm text-slate-400 dark:text-slate-500">
            {historyLoaded
              ? 'Ask anything, e.g. "What does this project do?"'
              : "Loading chat…"}
          </p>
        )}
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500">
              Thinking…
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-200 p-3 dark:border-slate-800"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask a question…"
            disabled={loading}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            Ask
          </button>
        </div>
      </form>
    </div>
  );
}

import { useCallback, useRef, useState, useEffect } from "react";

import { ragQuery } from "../api/rag";
import ChatMessage, { type ChatMessageData } from "./ChatMessage";

interface RagChatProps {
  projectId?: string;
}

export default function RagChat({ projectId }: RagChatProps) {
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      const question = input.trim();
      if (!question || loading) return;

      setMessages((current) => [
        ...current,
        { id: nextId.current++, role: "user", text: question } as ChatMessageData,
      ]);
      setInput("");
      setLoading(true);

      const id = nextId.current++;
      try {
        const response = await ragQuery(question, projectId);
        setMessages((current) => [
          ...current,
          {
            id,
            role: "assistant",
            text: response.answer,
            sources: response.sources,
            model: response.model,
            generatedAt: response.generated_at,
            confidence: response.confidence,
          } as ChatMessageData,
        ]);
      } catch (err) {
        setMessages((current) => [
          ...current,
          {
            id,
            role: "assistant",
            text:
              err instanceof Error
                ? `Sorry, I couldn't answer that: ${err.message}`
                : "Sorry, I couldn't answer that.",
            error: true,
          } as ChatMessageData,
        ]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, projectId],
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
            Ask anything, e.g. "What does this project do?"
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

      <form onSubmit={handleSubmit} className="border-t border-slate-200 p-3 dark:border-slate-800">
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
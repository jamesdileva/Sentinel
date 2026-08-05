import type { RagResult } from "../api/rag";

export interface ChatMessageData {
  id: number;
  role: "user" | "assistant";
  text: string;
  sources?: RagResult[];
  model?: string;
  generatedAt?: string;
  confidence?: number;
  error?: boolean;
}

function sourceLabel(source: RagResult): string {
  return source.file_path || source.source;
}

export default function ChatMessage({ message }: { message: ChatMessageData }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
      data-testid={`message-${message.role}`}
    >
      <div
        className={`max-w-[85%] rounded-xl px-4 py-3 text-sm ${
          isUser
            ? "bg-indigo-600 text-white"
            : message.error
              ? "border border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
              : "border border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.text}</p>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-600">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-400">
              Sources ({message.sources.length})
            </p>
            <ul className="flex flex-col gap-1">
              {message.sources.map((source, index) => (
                <li
                  key={`${source.source}-${index}`}
                  className="flex items-center justify-between gap-2 text-xs"
                >
                  <span className="truncate text-slate-600 dark:text-slate-300">
                    {sourceLabel(source)}
                  </span>
                  <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                    {source.distance.toFixed(3)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {!isUser && message.model && (
          <p className="mt-2 text-[10px] text-slate-400 dark:text-slate-500">
            {message.model}
            {message.generatedAt
              ? ` · ${new Date(message.generatedAt).toLocaleString()}`
              : ""}
            {message.confidence !== undefined
              ? ` · confidence ${message.confidence.toFixed(2)}`
              : ""}
          </p>
        )}
      </div>
    </div>
  );
}
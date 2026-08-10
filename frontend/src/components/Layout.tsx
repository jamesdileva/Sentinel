import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";

import { useUI } from "../contexts/UIContext";
import { NAV_ITEMS } from "./nav";
import { getSyncStatus } from "../api/system";
import type { SyncStatus, ActivityEvent } from "../api/system";
import { useActivity } from "../hooks/useActivity";
import type { ActivityStatus } from "../hooks/useActivity";

const KIND_LABEL: Record<string, string> = {
  sync: "Sync",
  index: "Index",
  knowledge: "Knowledge",
  build: "Build",
  test: "Tests",
  security: "Scan",
  ollama: "Ollama",
  job: "Job",
};

export default function Layout() {
  const { dark, toggleDark, sidebarOpen, setSidebarOpen } = useUI();
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const { events, status } = useActivity();

  useEffect(() => {
    let active = true;
    getSyncStatus()
      .then((data) => {
        if (active) setSync(data);
      })
      .catch(() => {
        if (active) setSync(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const sidebar = (
    <nav className="flex h-full flex-col gap-1 p-4">
      <div className="mb-4 flex items-center gap-2 px-2">
        <span className="text-xl text-indigo-500 dark:text-indigo-400">◉</span>
        <span className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Sentinel
        </span>
      </div>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          onClick={() => setSidebarOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive
                ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            }`
          }
        >
          <span aria-hidden="true">{item.icon}</span>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:block">
        {sidebar}
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-60 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
            {sidebar}
          </aside>
        </div>
      )}

      <div className="lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 lg:hidden"
            aria-label="Toggle navigation"
          >
            ☰
          </button>
          <h1 className="flex-1 text-sm font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            Dashboard
          </h1>
          {sync && <SyncPill sync={sync} />}
          <button
            type="button"
            onClick={toggleDark}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            aria-label="Toggle dark mode"
          >
            {dark ? "☀" : "☾"}
          </button>
        </header>

        <StatusBar events={events} status={status} />

        <main className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>

      <Toasts />
    </div>
  );
}

function StatusBar({
  events,
  status,
}: {
  events: ActivityEvent[];
  status: ActivityStatus;
}) {
  const last = events[0];
  const ollama = events.find((event) => event.kind === "ollama");
  const tokensPerSecond = (() => {
    const data = ollama?.data ?? {};
    const ms = Number(data.eval_duration_ns);
    const tokens = Number(data.tokens);
    if (!ms || !tokens) return null;
    return Math.round((tokens / ms) * 1_000_000_000);
  })();

  return (
    <div className="flex min-h-7 items-center gap-3 overflow-x-auto border-b border-slate-200 bg-white/60 px-4 py-1 text-xs text-slate-500 backdrop-blur dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
      <span className="flex shrink-0 items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            status === "open"
              ? "bg-emerald-500"
              : status === "connecting"
                ? "bg-amber-500"
                : "bg-red-500"
          }`}
          aria-hidden="true"
        />
        {status === "open"
          ? "live"
          : status === "connecting"
            ? "connecting"
            : "offline"}
      </span>

      {ollama && tokensPerSecond !== null && (
        <span className="shrink-0 font-mono text-[11px] text-indigo-600 dark:text-indigo-400">
          Ollama {String(ollama.data.purpose ?? "query")} · {tokensPerSecond}{" "}
          tok/s
        </span>
      )}

      {last ? (
        <span className="truncate" title={last.detail ?? undefined}>
          <span className="font-semibold text-slate-600 dark:text-slate-300">
            {KIND_LABEL[last.kind] ?? last.kind}
          </span>
          : {last.message}
          <span className="ml-2 text-slate-400 dark:text-slate-500">
            {new Date(last.created_at).toLocaleTimeString()}
          </span>
        </span>
      ) : (
        <span className="truncate italic">No activity yet</span>
      )}
    </div>
  );
}

function SyncPill({ sync }: { sync: SyncStatus }) {
  if (!sync.configured) {
    return (
      <span
        title="Repo sync is not configured (set SENTINEL_GITHUB_TOKEN in .env)"
        className="hidden items-center gap-1.5 rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs font-medium text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500 sm:inline-flex"
      >
        Sync not configured
      </span>
    );
  }
  const last = sync.last_run;
  let label = "Sync not run";
  let cls =
    "border-slate-300 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400";
  if (last) {
    if (last.status === "success") {
      const time = last.ran_at
        ? new Date(last.ran_at).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "";
      label = `Synced ${time}`;
      cls =
        "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300";
    } else if (last.status === "error") {
      label = "Sync failed";
      cls =
        "border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300";
    } else {
      label = "Sync skipped";
      cls =
        "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300";
    }
  }
  return (
    <span
      title={
        last?.status === "error" && last.detail
          ? last.detail
          : (last?.detail ?? undefined)
      }
      className={`hidden items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium sm:inline-flex ${cls}`}
    >
      {label}
    </span>
  );
}

function Toasts() {
  const { toasts, dismissToast } = useUI();
  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          type="button"
          onClick={() => dismissToast(toast.id)}
          className={`pointer-events-auto rounded-lg border px-4 py-2 text-sm shadow-lg backdrop-blur ${
            toast.kind === "error"
              ? "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
              : toast.kind === "success"
                ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                : "border-slate-300 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          }`}
        >
          {toast.message}
        </button>
      ))}
    </div>
  );
}

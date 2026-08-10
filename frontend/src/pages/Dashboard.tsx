import { useEffect, useState } from "react";

import { useBuilds } from "../contexts/BuildContext";
import { useProjectList } from "../hooks/useProjects";
import { useActivity } from "../hooks/useActivity";
import { getSummary } from "../api/portfolio";
import type { PortfolioSummary } from "../api/portfolio";

const KIND_COLOR: Record<string, string> = {
  sync: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  index: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  knowledge: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  build: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  test: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  security: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  ollama:
    "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
  job: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

function kindColor(kind: string): string {
  return KIND_COLOR[kind] ?? KIND_COLOR.job;
}

export default function Dashboard() {
  const { projects, loading, error, refresh } = useProjectList();
  const { activeJobs } = useBuilds();
  const { events, status } = useActivity();
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);

  useEffect(() => {
    let active = true;
    getSummary()
      .then((data) => {
        if (active) setSummary(data);
      })
      .catch(() => {
        if (active) setSummary(null);
      });
    return () => {
      active = false;
    };
  }, []);

  const stats = [
    { label: "Projects", value: loading ? "…" : String(projects.length) },
    { label: "Builds", value: String(activeJobs.length) },
    { label: "Findings", value: summary ? String(summary.open_findings) : "—" },
    {
      label: "Health",
      value: summary ? String(summary.avg_health) : "—",
      hint: summary
        ? `${summary.buildable} of ${summary.projects} buildable`
        : undefined,
    },
  ];

  return (
    <section aria-label="Dashboard overview">
      {error && (
        <div className="mb-4 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
          <button
            type="button"
            onClick={() => void refresh()}
            className="ml-3 font-medium underline"
          >
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
          >
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {stat.label}
            </p>
            <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {stat.value}
            </p>
            {stat.hint && (
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {stat.hint}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Live activity
          </h2>
          <span className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <span
              className={`h-2 w-2 rounded-full ${
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
        </div>
        <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800">
          {events.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-slate-400 dark:text-slate-500">
              Nothing happened yet — syncs, indexing, builds and scans will show
              up here.
            </li>
          )}
          {events.slice(0, 30).map((event, index) => (
            <li
              key={event.id ?? `${event.kind}-${index}-${event.created_at}`}
              className="flex items-center gap-3 px-4 py-2 text-xs"
            >
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 font-medium ${kindColor(event.kind)}`}
              >
                {event.kind}
              </span>
              <span className="min-w-0 flex-1 truncate text-slate-600 dark:text-slate-300">
                {event.message}
              </span>
              <span className="shrink-0 text-slate-400 dark:text-slate-500">
                {new Date(event.created_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {projects.length > 0 && (
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <div
              key={project.id}
              className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
            >
              <p className="font-medium text-slate-900 dark:text-slate-100">
                {project.name}
              </p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                {project.language}
                {project.framework ? ` / ${project.framework}` : ""}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

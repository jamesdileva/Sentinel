import { useEffect, useState } from "react";

import { useBuilds } from "../contexts/BuildContext";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";
import { useWebSocket } from "../hooks/useWebSocket";
import type { WsStatus } from "../hooks/useWebSocket";
import { getSummary } from "../api/portfolio";
import type { PortfolioSummary } from "../api/portfolio";

function wsLabel(status: WsStatus): string {
  if (status === "open") return "live";
  if (status === "connecting") return "connecting";
  return "offline";
}

export default function Dashboard() {
  const { projects, loading, error, refresh } = useProjectList();
  const { activeJobs } = useBuilds();
  const { toast } = useUI();
  const { status, lastMessage } = useWebSocket("/api/v1/ws/jobs", {
    onMessage: (message) => {
      if (message.type === "welcome") toast("Connected to live job updates");
    },
  });
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
      hint: summary ? `${summary.buildable} of ${summary.projects} buildable` : undefined,
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
            <p className="text-sm text-slate-500 dark:text-slate-400">{stat.label}</p>
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

      <div className="mt-6 flex items-center justify-between rounded-xl border border-dashed border-slate-300 p-4 text-sm dark:border-slate-700">
        <p className="text-slate-500 dark:text-slate-400">
          {lastMessage ? `Channel: ${String(lastMessage.type)}` : "Job channel"}
        </p>
        <span className="flex items-center gap-2 text-slate-400 dark:text-slate-500">
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
          {wsLabel(status)}
        </span>
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

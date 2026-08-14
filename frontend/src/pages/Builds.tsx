import { useEffect, useState } from "react";

import {
  getBuildHistory,
  getBuildStatus,
  triggerBuild,
  type BuildJob,
  type BuildLog,
} from "../api/builds";
import { useProjectList } from "../hooks/useProjects";
import { useUI } from "../contexts/UIContext";

const POLL_MS = 2000;
const POLL_CAP_MS = 6 * 60 * 1000;

function statusTone(job: BuildJob | BuildLog) {
  if (job.success === true) return "text-emerald-600 dark:text-emerald-400";
  if (job.success === false) return "text-red-600 dark:text-red-400";
  return "text-slate-400 dark:text-slate-500";
}

function statusLabel(job: BuildJob | BuildLog) {
  if (job.success === true) return "succeeded";
  if (job.success === false) return "failed";
  if (job.completed_at) return "skipped";
  return "running";
}

export default function Builds() {
  const { projects, loading: projectsLoading } = useProjectList();
  const { toast } = useUI();

  const [projectId, setProjectId] = useState("");
  const [history, setHistory] = useState<BuildLog[]>([]);
  const [running, setRunning] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);

  useEffect(() => {
    setPollingJobId(null);
    setRunning(false);
    if (!projectId) {
      setHistory([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoadingHistory(true);
      setError(null);
      try {
        const rows = await getBuildHistory(projectId);
        if (!cancelled) {
          setHistory(rows);
          // Resume live-polling a build that was already running when the
          // page loaded (e.g. triggered from another tab) — unless a fresh
          // trigger already owns the poll.
          const newest = rows[0];
          if (newest && newest.success === null && !newest.completed_at) {
            setRunning(true);
            setPollingJobId((current) => current ?? newest.id);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Cannot load builds.");
        }
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Poll the active job every 2 s until it reaches a terminal state
  // (queued → running → succeeded/failed/skipped), then refresh the list so
  // the result shows up without a manual refresh or tab switch.
  useEffect(() => {
    if (!pollingJobId) return;
    let cancelled = false;
    let elapsed = 0;
    const finish = async (message: string, tone: "success" | "error") => {
      setPollingJobId(null);
      setRunning(false);
      try {
        const rows = await getBuildHistory(projectId);
        if (!cancelled) setHistory(rows);
      } catch {
        // keep the toast; the next page load will show fresh history
      }
      if (!cancelled) toast(message, tone);
    };
    const tick = async () => {
      elapsed += POLL_MS;
      try {
        const job = await getBuildStatus(pollingJobId);
        if (cancelled) return;
        if (job.completed_at !== null) {
          const failed = job.success === false;
          await finish(`Build ${job.status}.`, failed ? "error" : "success");
        } else if (elapsed >= POLL_CAP_MS) {
          await finish(
            "Build still running — refresh to see the result.",
            "error",
          );
        }
      } catch {
        if (!cancelled) {
          await finish(
            "Build status lost — refresh to see the result.",
            "error",
          );
        }
      }
    };
    void tick();
    const interval = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [pollingJobId, projectId]);

  async function handleBuild() {
    if (!projectId || running) return;
    setRunning(true);
    try {
      const job = await triggerBuild(projectId);
      toast(`Build queued (job ${job.id.slice(0, 8)}…)`, "success");
      const rows = await getBuildHistory(projectId);
      setHistory(rows);
      setPollingJobId(job.id);
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to queue build.",
        "error",
      );
      setRunning(false);
    }
  }

  return (
    <section aria-label="Builds" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Builds
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Deterministic builds: the known commands for each project, run in a
          clean job (git history + CI logs, never AI).
        </p>
        {error && (
          <div className="mt-3 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          Project
          <select
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            disabled={projectsLoading}
            className="w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Select a project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => void handleBuild()}
          disabled={!projectId || running}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
        >
          {running ? "Building…" : "Run build"}
        </button>
      </div>

      {projectId && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Recent builds ({history.length})
          </h3>
          {loadingHistory && history.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              Loading…
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              No builds yet. Trigger one above.
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {history.map((job) => (
                <li
                  key={job.id}
                  className="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
                >
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedId(expandedId === job.id ? null : job.id)
                    }
                    className="flex w-full items-center gap-3 px-4 py-3 text-left"
                    aria-expanded={expandedId === job.id}
                  >
                    <span
                      className={`text-xs font-semibold ${statusTone(job)}`}
                    >
                      {statusLabel(job)}
                    </span>
                    <span className="flex-1 truncate text-xs text-slate-400 dark:text-slate-500">
                      {job.completed_at ?? "running…"} · exit{" "}
                      {job.exit_code ?? "—"}
                    </span>
                    <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                      {job.commands ? Object.keys(job.commands).length : 0}{" "}
                      command(s)
                    </span>
                  </button>
                  {expandedId === job.id && (
                    <div className="border-t border-slate-100 px-4 py-3 dark:border-slate-800">
                      {job.commands && Object.keys(job.commands).length > 0 && (
                        <div className="mb-3 flex flex-wrap gap-2">
                          {Object.entries(job.commands).map(
                            ([step, command]) => (
                              <span
                                key={step}
                                className="rounded bg-slate-100 px-2 py-1 font-mono text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                              >
                                {step}: {command}
                              </span>
                            ),
                          )}
                        </div>
                      )}
                      <pre className="max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600 dark:bg-slate-950 dark:text-slate-300">
                        {job.stdout || "(no stdout)"}
                        {job.stderr ? `\n\n[stderr]\n${job.stderr}` : ""}
                      </pre>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

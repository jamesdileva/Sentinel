import { useEffect, useState } from "react";

import {
  clearResolvedFindings,
  getFindings,
  triggerScan,
  triggerScanAll,
  type FindingSeverity,
  type SecurityFinding,
} from "../api/security";
import { getProject } from "../api/projects";
import { useProjectList } from "../hooks/useProjects";
import { useUI } from "../contexts/UIContext";

const POLL_MS = 2000;
const POLL_CAP_MS = 10 * 60 * 1000;

const severityTone: Record<FindingSeverity, string> = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/60 dark:text-orange-200",
  medium:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200",
  low: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  info: "bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-200",
};

export default function Security() {
  const { projects, loading: projectsLoading } = useProjectList();
  const { toast } = useUI();

  const [projectId, setProjectId] = useState("");
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanningAll, setScanningAll] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [showResolved, setShowResolved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Baseline `last_scanned` snapshot taken when a scan was queued; the poll
  // loop compares against it so the tab refreshes when the scan completes.
  const [scanBaseline, setScanBaseline] = useState<string | null>(null);

  useEffect(() => {
    setScanBaseline(null);
    setScanning(false);
    setScanningAll(false);
    if (!projectId) {
      setFindings([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const rows = await getFindings(projectId);
        if (!cancelled) setFindings(rows);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Cannot load findings.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // Poll the project's `last_scanned` (stamped by the scanner on completion)
  // until it moves past the pre-scan snapshot, then refresh the findings
  // list. A clean scan writes no finding row, so the list alone cannot
  // signal completion — the timestamp is the only deterministic signal.
  useEffect(() => {
    if (!projectId || scanBaseline === null) return;
    let cancelled = false;
    let elapsed = 0;
    const finish = async (message: string, tone: "success" | "error") => {
      try {
        const rows = await getFindings(projectId);
        if (!cancelled) setFindings(rows);
      } catch {
        // keep the toast; the next page load will show fresh findings
      }
      if (!cancelled) toast(message, tone);
      // Clear the poll *after* the refresh so the effect cleanup (which sets
      // `cancelled`) can never drop the list update or the toast.
      setScanBaseline(null);
      setScanning(false);
      setScanningAll(false);
    };
    const tick = async () => {
      elapsed += POLL_MS;
      try {
        const project = await getProject(projectId);
        if (cancelled) return;
        if (project.last_scanned !== scanBaseline) {
          await finish("Security scan complete.", "success");
        } else if (elapsed >= POLL_CAP_MS) {
          await finish(
            "Scan still running — refresh to see the results.",
            "error",
          );
        }
      } catch {
        if (!cancelled) {
          await finish("Scan status lost — refresh to see findings.", "error");
        }
      }
    };
    void tick();
    const interval = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [projectId, scanBaseline, toast]);

  async function handleScan() {
    if (!projectId || scanning || scanBaseline !== null) return;
    setScanning(true);
    try {
      const baseline =
        projects.find((project) => project.id === projectId)?.last_scanned ??
        null;
      const job = await triggerScan(projectId);
      toast(`Security scan queued (job ${job.job_id.slice(0, 8)}…)`, "success");
      setScanBaseline(baseline);
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to queue scan.",
        "error",
      );
      setScanning(false);
    }
  }

  async function handleScanAll() {
    if (scanningAll || scanBaseline !== null) return;
    setScanningAll(true);
    try {
      const baseline = projectId
        ? (projects.find((project) => project.id === projectId)?.last_scanned ??
          null)
        : null;
      const job = await triggerScanAll();
      toast(
        `Security scan of all projects queued (job ${job.job_id.slice(0, 8)}…)`,
        "success",
      );
      if (baseline !== null) {
        setScanBaseline(baseline);
      } else {
        setScanningAll(false);
      }
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to queue scan.",
        "error",
      );
      setScanningAll(false);
    }
  }

  async function handleClearResolved() {
    if (!projectId || clearing) return;
    setClearing(true);
    try {
      const result = await clearResolvedFindings(projectId);
      toast(
        result.deleted > 0
          ? `Cleared ${result.deleted} resolved finding(s).`
          : "No resolved findings to clear.",
        "success",
      );
      const rows = await getFindings(projectId);
      setFindings(rows);
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to clear findings.",
        "error",
      );
    } finally {
      setClearing(false);
    }
  }

  const visibleFindings = showResolved
    ? findings
    : findings.filter((finding) => !finding.resolved);
  const resolvedCount = findings.filter((finding) => finding.resolved).length;

  return (
    <section aria-label="Security" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Security
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Deterministic scans against known repositories: dependency and
          token/secret checks, plus static analysis.
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
          onClick={() => void handleScan()}
          disabled={!projectId || scanning || scanBaseline !== null}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
        >
          {scanning ? "Scanning…" : "Run scan"}
        </button>
        <button
          type="button"
          onClick={() => void handleScanAll()}
          disabled={scanningAll || scanBaseline !== null}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {scanningAll ? "Scanning…" : "Run all"}
        </button>
      </div>

      {projectId && (
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Findings ({visibleFindings.length})
            </h3>
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
              <input
                type="checkbox"
                checked={showResolved}
                onChange={(event) => setShowResolved(event.target.checked)}
                className="h-3.5 w-3.5 accent-indigo-600"
              />
              Show resolved
            </label>
            <button
              type="button"
              onClick={() => void handleClearResolved()}
              disabled={clearing || resolvedCount === 0}
              className="rounded-lg border border-red-300 px-3 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-50 disabled:opacity-40 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950"
            >
              {clearing ? "Clearing…" : `Clear resolved (${resolvedCount})`}
            </button>
          </div>
          {loading && findings.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              Loading…
            </div>
          ) : visibleFindings.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              {findings.length === 0
                ? "No findings yet. Run a scan above."
                : showResolved
                  ? "No findings for this project."
                  : "No open findings — resolved ones are hidden. Toggle 'Show resolved' to see them."}
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {visibleFindings.map((finding) => (
                <li
                  key={finding.id}
                  className={`rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 ${finding.resolved ? "opacity-60" : ""}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${severityTone[finding.severity]}`}
                        >
                          {finding.severity}
                        </span>
                        <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {finding.title}
                        </span>
                      </div>
                      {finding.cve_id && (
                        <span className="mt-1 inline-block rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                          {finding.cve_id}
                        </span>
                      )}
                    </div>
                    {finding.resolved && (
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-200">
                        resolved
                      </span>
                    )}
                  </div>
                  {finding.file_path && (
                    <p className="mt-1 font-mono text-[11px] text-slate-400 dark:text-slate-500">
                      {finding.file_path}
                      {finding.line_number ? `:${finding.line_number}` : ""}
                    </p>
                  )}
                  {finding.description && (
                    <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                      {finding.description}
                    </p>
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

import { useEffect, useState } from "react";

import {
  getFindings,
  triggerScan,
  type FindingSeverity,
  type SecurityFinding,
} from "../api/security";
import { useProjectList } from "../hooks/useProjects";
import { useUI } from "../contexts/UIContext";

const severityTone: Record<FindingSeverity, string> = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900/60 dark:text-red-200",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/60 dark:text-orange-200",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200",
  low: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  info: "bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-200",
};

export default function Security() {
  const { projects, loading: projectsLoading } = useProjectList();
  const { toast } = useUI();

  const [projectId, setProjectId] = useState("");
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
          setError(err instanceof Error ? err.message : "Cannot load findings.");
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

  async function handleScan() {
    if (!projectId || scanning) return;
    setScanning(true);
    try {
      const job = await triggerScan(projectId);
      toast(`Security scan queued (job ${job.job_id.slice(0, 8)}…)`, "success");
      const rows = await getFindings(projectId);
      setFindings(rows);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to queue scan.", "error");
    } finally {
      setScanning(false);
    }
  }

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
          disabled={!projectId || scanning}
          className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
        >
          {scanning ? "Queuing…" : "Run scan"}
        </button>
      </div>

      {projectId && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Findings ({findings.length})
          </h3>
          {loading && findings.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              Loading…
            </div>
          ) : findings.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
              No findings yet. Run a scan above.
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {findings.map((finding) => (
                <li
                  key={finding.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
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
import { useEffect, useRef, useState } from "react";

import { getProjectFiles, listProjects } from "../api/projects";
import type { Project, ProjectFile } from "../types";

function languageBadge(language: string) {
  const tones: Record<string, string> = {
    python: "bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-200",
    javascript: "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200",
    typescript: "bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-200",
    sql: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200",
  };
  const fallback = "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300";
  return tones[language.toLowerCase()] ?? fallback;
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  // v1.17.18.5 (audit2 F6): guards against a stale file-list response
  // landing after the user has already switched projects.
  const filesRequestRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await listProjects();
        if (cancelled) return;
        setProjects(response.projects);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Cannot load projects.");
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function selectProject(project: Project) {
    const nextSelected = project.id === selectedId ? null : project.id;
    setSelectedId(nextSelected);
    setFiles([]);
    if (nextSelected === null) return;
    const requestId = ++filesRequestRef.current;
    try {
      const rows = await getProjectFiles(nextSelected);
      if (filesRequestRef.current !== requestId) return; // stale switch
      setFiles(rows);
    } catch (err) {
      if (filesRequestRef.current !== requestId) return;
      setError(err instanceof Error ? err.message : "Cannot load files.");
    }
  }

  const selected = projects.find((p) => p.id === selectedId) ?? null;

  return (
    <section aria-label="Known projects" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Known repositories
        </h2>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Deterministic project index: unknown web apps are never watched —
          only these repositories.
        </p>
        {error && (
          <div className="mt-3 rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
          </div>
        )}
      </div>

      {projects.length === 0 && !error ? (
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
          No projects indexed. Add one via the CLI indexer.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {projects.map((project) => (
            <li
              key={project.id}
              className="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
            >
              <button
                type="button"
                onClick={() => void selectProject(project)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left"
                aria-expanded={project.id === selectedId}
              >
                <span
                  className={`text-xs font-semibold ${
                    project.status === "active"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-slate-400 dark:text-slate-500"
                  }`}
                >
                  {project.status === "active" ? "●" : "○"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
                    {project.name}
                  </span>
                  <span className="block truncate text-xs text-slate-400 dark:text-slate-500">
                    {project.path}
                  </span>
                </span>
                {project.language && (
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${languageBadge(
                      project.language,
                    )}`}
                  >
                    {project.language}
                  </span>
                )}
                {project.framework && (
                  <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300">
                    {project.framework}
                  </span>
                )}
                {project.health_score !== null && (
                  <span className="hidden text-xs font-semibold text-slate-500 sm:block dark:text-slate-400">
                    {project.health_score.toFixed(0)}
                  </span>
                )}
              </button>

              {project.id === selectedId && (
                <div className="border-t border-slate-100 px-4 py-3 dark:border-slate-800">
                  {selected && (
                    <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                      <span>
                        Files: <span className="font-semibold">{files.length}</span>
                      </span>
                      {project.last_indexed && (
                        <span>
                          Last indexed:{" "}
                          <span className="font-semibold">
                            {new Date(project.last_indexed).toLocaleString()}
                          </span>
                        </span>
                      )}
                    </div>
                  )}
                  {files.length === 0 ? (
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      No indexed files.
                    </p>
                  ) : (
                    <ul className="max-h-72 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-800">
                      {files.map((file) => (
                        <li
                          key={file.id}
                          className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-1.5 text-xs last:border-b-0 dark:border-slate-800"
                        >
                          <span className="truncate font-mono text-slate-600 dark:text-slate-300">
                            {file.path}
                          </span>
                          <span className="shrink-0 text-slate-400 dark:text-slate-500">
                            {file.size_bytes != null
                              ? `${(file.size_bytes / 1024).toFixed(1)} KiB`
                              : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
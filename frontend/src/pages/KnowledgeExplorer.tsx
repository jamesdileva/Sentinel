import { useEffect, useRef, useState } from "react";

import {
  getIndexStatus,
  ragIndex,
  ragSearch,
  resetKnowledgeIndex,
  type RagIndexStatus,
  type RagResult,
} from "../api/rag";
import RagChat from "../components/RagChat";
import { useUI } from "../contexts/UIContext";
import { useProjectList } from "../hooks/useProjects";
import { useActivity } from "../hooks/useActivity";

const REFRESH_THROTTLE_MS = 3_000;

export default function KnowledgeExplorer() {
  const { projects, loading: projectsLoading } = useProjectList();
  const { toast } = useUI();
  const { events: activity } = useActivity();

  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [indexing, setIndexing] = useState(false);

  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<RagResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [indexStatus, setIndexStatus] = useState<RagIndexStatus | null>(null);
  const [resetting, setResetting] = useState(false);
  const lastRefresh = useRef(0);

  useEffect(() => {
    let active = true;
    getIndexStatus()
      .then((data) => {
        if (active) setIndexStatus(data);
      })
      .catch(() => {
        if (active) setIndexStatus(null);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const latest = activity[0];
    if (!latest) return;
    if (!["knowledge", "index", "ollama"].includes(latest.kind)) return;
    const now = Date.now();
    if (now - lastRefresh.current < REFRESH_THROTTLE_MS) return;
    lastRefresh.current = now;
    getIndexStatus()
      .then(setIndexStatus)
      .catch(() => {
        /* keep the last known progress */
      });
  }, [activity]);

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  function indexStatusLine(): string | null {
    if (!indexStatus) return null;
    if (selectedProjectId) {
      const entry = indexStatus.projects[selectedProjectId];
      if (!entry) return null;
      return entry.embedded === entry.files
        ? `All ${entry.files} files embedded ✓`
        : `${entry.embedded} of ${entry.files} files embedded`;
    }
    return indexStatus.files_total > 0
      ? `${indexStatus.files_embedded} of ${indexStatus.files_total} files embedded across projects`
      : "No files indexed yet";
  }

  function indexStatusComplete(): boolean {
    if (!indexStatus) return false;
    if (selectedProjectId) {
      const entry = indexStatus.projects[selectedProjectId];
      return entry != null && entry.embedded === entry.files;
    }
    return (
      indexStatus.files_total > 0 &&
      indexStatus.files_embedded === indexStatus.files_total
    );
  }

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    const query = searchQuery.trim();
    if (!query || searching) return;
    setSearching(true);
    setSearchError(null);
    try {
      const response = await ragSearch(query, selectedProjectId || undefined);
      setResults(response.results);
    } catch (err) {
      setSearchError(
        err instanceof Error
          ? err.message
          : "Search failed. Is the knowledge indexed?",
      );
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function handleIndex() {
    if (!selectedProjectId || indexing) return;
    setIndexing(true);
    try {
      // with_summary=true (v1.17.6.2): indexing always includes the AI
      // architecture summary (deduped server-side to once per project).
      const job = await ragIndex(selectedProjectId, true);
      toast(
        `Knowledge indexing queued (job ${job.job_id.slice(0, 8)}…)`,
        "success",
      );
    } catch (err) {
      toast(
        err instanceof Error
          ? err.message
          : "Failed to queue knowledge indexing.",
        "error",
      );
    } finally {
      setIndexing(false);
    }
  }

  async function handleReset() {
    if (resetting) return;
    const brokenList = indexStatus?.health?.broken ?? [];
    const broken =
      brokenList.length > 0 ? brokenList.join(", ") : "the index";
    if (
      !window.confirm(
        `Rebuild knowledge index?\n\nThe ${broken} data on disk can't be read. ` +
          "Rebuilding drops the derived vectors (project data is untouched) " +
          "and re-indexes everything from the local files.",
      )
    ) {
      return;
    }
    setResetting(true);
    try {
      const job = await resetKnowledgeIndex();
      toast(
        `Rebuild queued (job ${job.job_id.slice(0, 8)}…) — re-indexing follows.`,
        "success",
      );
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to queue the rebuild.",
        "error",
      );
    } finally {
      setResetting(false);
    }
  }

  function damagedCollections(): string[] {
    return indexStatus?.health?.broken ?? [];
  }

  return (
    <section aria-label="Knowledge explorer">
      {damagedCollections().length > 0 && (
        <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-amber-900 dark:text-amber-200">
              <p className="font-semibold">Knowledge index damaged on disk</p>
              <p className="mt-1 text-xs">
                {damagedCollections().join(", ")} can no longer be read (a
                write was probably interrupted). Rebuild to drop the broken
                vectors and re-embed everything — source files and rows are
                untouched.
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleReset()}
              disabled={resetting}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700 disabled:opacity-50"
            >
              {resetting ? "Rebuilding…" : "Rebuild knowledge index"}
            </button>
          </div>
        </div>
      )}
      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
            Project
            <select
              value={selectedProjectId}
              onChange={(event) => setSelectedProjectId(event.target.value)}
              disabled={projectsLoading}
              className="w-64 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() => void handleIndex()}
            disabled={!selectedProjectId || indexing}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
          >
            {indexing ? "Indexing…" : "Index knowledge"}
          </button>
        </div>
        {indexStatusLine() ? (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {indexStatusLine()}
            {!indexStatusComplete() && (
              <> — run "Index knowledge" to refresh or complete it.</>
            )}
          </p>
        ) : (
          selectedProject && (
            <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
              Scoped to{" "}
              <span className="font-medium">{selectedProject.name}</span> — run
              "Index knowledge" first so search and chat have data.
            </p>
          )
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="flex flex-col gap-4">
          <form
            onSubmit={(event) => void handleSearch(event)}
            className="flex gap-2 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
          >
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Semantic search, e.g. how does authentication work"
              className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
            <button
              type="submit"
              disabled={searching || !searchQuery.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
            >
              {searching ? "…" : "Search"}
            </button>
          </form>

          {searchError && (
            <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
              {searchError}
            </div>
          )}

          {results.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Results ({results.length})
              </h3>
              {results.map((result, index) => (
                <div
                  key={`${result.source}-${index}`}
                  className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-medium text-slate-600 dark:text-slate-300">
                      {result.file_path || result.source}
                    </span>
                    <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                      {result.distance.toFixed(3)}
                    </span>
                  </div>
                  <p className="line-clamp-3 text-xs text-slate-500 dark:text-slate-400">
                    {result.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        <RagChat projectId={selectedProjectId || undefined} />
      </div>
    </section>
  );
}

import { useEffect, useMemo, useState } from "react";

import {
  addCheckpoint,
  captureScreenshot,
  deleteSession,
  endSession,
  exportScreenshot,
  getSession,
  listSessions,
  screenshotUrl,
  startSession,
  summarizeSession,
  triageSession,
  type SessionExport,
  type SessionRecord,
  type SessionStatus,
  type TriageRecord,
} from "../api/sessions";
import { useProjectList } from "../hooks/useProjects";
import { useUI } from "../contexts/UIContext";

const STATUS_TONE: Record<SessionStatus, string> = {
  running: "text-amber-600 dark:text-amber-400",
  passed: "text-emerald-600 dark:text-emerald-400",
  failed: "text-red-600 dark:text-red-400",
  investigate: "text-indigo-600 dark:text-indigo-400",
};

const STATUS_LABEL: Record<SessionStatus, string> = {
  running: "running",
  passed: "passed",
  failed: "failed",
  investigate: "investigate",
};

const STATUS_ORDER: SessionStatus[] = [
  "running",
  "passed",
  "failed",
  "investigate",
];

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  const when = new Date(iso);
  return when.toLocaleString();
}

export default function Sessions() {
  const { projects, loading: projectsLoading } = useProjectList();
  const { toast } = useUI();

  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectFilter, setProjectFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<SessionStatus | "">("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [zoomImage, setZoomImage] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<SessionExport | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setSessions(
        await listSessions(
          projectFilter || undefined,
          statusFilter || undefined,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cannot load sessions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [projectFilter, statusFilter]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {
      running: 0,
      passed: 0,
      failed: 0,
      investigate: 0,
    };
    for (const session of sessions) counts[session.status] += 1;
    return counts;
  }, [sessions]);

  async function refreshOne(sessionId: string) {
    try {
      const fresh = await getSession(sessionId);
      setSessions((current) =>
        current.map((session) => (session.id === sessionId ? fresh : session)),
      );
    } catch {
      void load();
    }
  }

  function handleCreate() {
    setShowCreate(true);
  }

  async function handleDelete(session: SessionRecord) {
    try {
      await deleteSession(session.id);
      toast("Session deleted.", "success");
      if (expandedId === session.id) setExpandedId(null);
      await load();
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to delete session.",
        "error",
      );
    }
  }

  return (
    <section aria-label="Sessions" className="flex flex-col gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Sessions
            </h2>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Manual app-testing runs. Sentinel records start / checkpoint / end
              markers into the app's own log (provenance, never guessed) and
              grabs full-screen screenshots — you drive the app, Sentinel only
              watches (Rule 2). Export copies shots into your portfolio repo;
              pushing the site stays manual.
            </p>
          </div>
          <button
            type="button"
            onClick={handleCreate}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
          >
            New session
          </button>
        </div>
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
            value={projectFilter}
            onChange={(event) => setProjectFilter(event.target.value)}
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
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Status
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setStatusFilter("")}
              className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                statusFilter === ""
                  ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                  : "text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
              }`}
            >
              All ({sessions.length})
            </button>
            {STATUS_ORDER.map((status) => (
              <button
                key={status}
                type="button"
                onClick={() =>
                  setStatusFilter(statusFilter === status ? "" : status)
                }
                className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  statusFilter === status
                    ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300"
                    : "text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                }`}
              >
                {STATUS_LABEL[status]} ({statusCounts[status]})
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && sessions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
          Loading…
        </div>
      ) : sessions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
          No sessions yet. Start one to record an app-testing run.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {sessions.map((session) => (
            <li
              key={session.id}
              className="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
            >
              <button
                type="button"
                onClick={() =>
                  setExpandedId(expandedId === session.id ? null : session.id)
                }
                className="flex w-full items-center gap-3 px-4 py-3 text-left"
                aria-expanded={expandedId === session.id}
              >
                <span
                  className={`text-xs font-semibold ${STATUS_TONE[session.status]}`}
                >
                  {STATUS_LABEL[session.status]}
                </span>
                <span className="flex-1 truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                  {session.title}
                </span>
                <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                  {session.project_name ?? "unknown project"}
                </span>
                <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                  {session.checkpoints.length} checkpoint(s) ·{" "}
                  {session.screenshots.length} shot(s)
                </span>
                <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                  {formatWhen(session.started_at)}
                </span>
              </button>
              {expandedId === session.id && (
                <SessionDetail
                  session={session}
                  onChanged={() => void refreshOne(session.id)}
                  onDeleted={() => void handleDelete(session)}
                  onZoom={(url) => setZoomImage(url)}
                  onExport={(result) => setExportResult(result)}
                />
              )}
            </li>
          ))}
        </ul>
      )}

      {showCreate && (
        <CreateDialog
          projects={projects}
          onClose={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await load();
          }}
        />
      )}

      {zoomImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
          onClick={() => setZoomImage(null)}
          role="dialog"
          aria-label="Screenshot preview"
        >
          <img
            src={zoomImage}
            alt="Screenshot preview"
            className="max-h-full max-w-full rounded-lg shadow-2xl"
          />
        </div>
      )}

      {exportResult && (
        <ExportDialog
          result={exportResult}
          onClose={() => setExportResult(null)}
        />
      )}
    </section>
  );
}

function SessionDetail({
  session,
  onChanged,
  onDeleted,
  onZoom,
  onExport,
}: {
  session: SessionRecord;
  onChanged: () => void;
  onDeleted: () => void;
  onZoom: (url: string) => void;
  onExport: (result: SessionExport) => void;
}) {
  const { toast } = useUI();
  const [capturing, setCapturing] = useState(false);
  const [ending, setEnding] = useState(false);
  const [outcome, setOutcome] = useState("");
  const [endStatus, setEndStatus] = useState<
    "passed" | "failed" | "investigate"
  >("passed");
  const [checkpointLabel, setCheckpointLabel] = useState("");
  const [addingCheckpoint, setAddingCheckpoint] = useState(false);
  const [triage, setTriage] = useState<TriageRecord | null>(null);
  const [triaging, setTriaging] = useState(false);
  const [summarizing, setSummarizing] = useState(false);

  const ended = session.status !== "running";
  const triageable =
    ended && (session.status === "failed" || session.status === "investigate");

  async function handleCapture(checkpointId?: string) {
    setCapturing(true);
    try {
      await captureScreenshot(session.id, checkpointId);
      toast("Screenshot captured.", "success");
      onChanged();
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to capture screenshot.",
        "error",
      );
    } finally {
      setCapturing(false);
    }
  }

  async function handleCheckpoint() {
    if (!checkpointLabel.trim()) return;
    setAddingCheckpoint(true);
    try {
      await addCheckpoint(session.id, checkpointLabel.trim());
      setCheckpointLabel("");
      toast("Checkpoint recorded.", "success");
      onChanged();
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to record checkpoint.",
        "error",
      );
    } finally {
      setAddingCheckpoint(false);
    }
  }

  async function handleEnd() {
    setEnding(true);
    try {
      await endSession(session.id, outcome.trim() || null, endStatus);
      toast("Session ended — log slice + auto screenshot saved.", "success");
      onChanged();
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to end session.",
        "error",
      );
    } finally {
      setEnding(false);
    }
  }

  async function handleExport(screenshotId: string) {
    try {
      const result = await exportScreenshot(session.id, screenshotId);
      onExport(result);
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to export screenshot.",
        "error",
      );
    }
  }

  async function handleTriage() {
    setTriaging(true);
    try {
      setTriage(await triageSession(session.id));
      toast("Triage captured — evidence is deterministic.", "success");
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to triage session.",
        "error",
      );
    } finally {
      setTriaging(false);
    }
  }

  async function handleSummarize() {
    setSummarizing(true);
    try {
      setTriage(await summarizeSession(session.id));
      toast("AI summary written (interpretation only).", "success");
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to summarize session.",
        "error",
      );
    } finally {
      setSummarizing(false);
    }
  }

  const sliceLines = (session.log_slice ?? "").split("\n").filter(Boolean);

  return (
    <div className="border-t border-slate-100 px-4 py-4 dark:border-slate-800">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          {session.expected_output && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Expected output
              </h4>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {session.expected_output}
              </p>
            </div>
          )}
          {session.actual_outcome && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Actual outcome
              </h4>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {session.actual_outcome}
              </p>
            </div>
          )}
          {session.checkpoints.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Checkpoints
              </h4>
              <ul className="mt-1 flex flex-col gap-1">
                {session.checkpoints.map((checkpoint) => (
                  <li
                    key={checkpoint.id}
                    className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300"
                  >
                    <span className="text-indigo-500">◆</span>
                    <span className="flex-1">{checkpoint.label}</span>
                    <span className="text-xs text-slate-400">
                      {formatWhen(checkpoint.at)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void handleCapture()}
              disabled={capturing}
              className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
            >
              {capturing ? "Capturing…" : "Capture screenshot"}
            </button>
            <button
              type="button"
              onClick={() => void onDeleted()}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
            >
              Delete
            </button>
          </div>
          {triageable && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Error triage (deterministic — no AI)
                </h4>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => void handleTriage()}
                    disabled={triaging}
                    className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
                  >
                    {triaging
                      ? "Triaging…"
                      : triage
                        ? "Re-triage"
                        : "Triage failure"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleSummarize()}
                    disabled={summarizing}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    {summarizing ? "Summarizing…" : "AI summary"}
                  </button>
                </div>
              </div>
              {triage && <TriageCard triage={triage} />}
            </div>
          )}
          {!ended && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-950">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                End session
              </h4>
              <textarea
                value={outcome}
                onChange={(event) => setOutcome(event.target.value)}
                placeholder="What actually happened? (markers + screenshot are saved regardless)"
                rows={2}
                className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {(["passed", "failed", "investigate"] as const).map(
                  (status) => (
                    <label
                      key={status}
                      className="flex cursor-pointer items-center gap-1 text-xs font-medium text-slate-600 dark:text-slate-300"
                    >
                      <input
                        type="radio"
                        name="end-status"
                        checked={endStatus === status}
                        onChange={() => setEndStatus(status)}
                        className="accent-indigo-500"
                      />
                      {status}
                    </label>
                  ),
                )}
                <button
                  type="button"
                  onClick={() => void handleEnd()}
                  disabled={ending}
                  className="ml-auto rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
                >
                  {ending ? "Ending…" : "End session"}
                </button>
              </div>
            </div>
          )}
          {!ended && (
            <div className="flex gap-2">
              <input
                value={checkpointLabel}
                onChange={(event) => setCheckpointLabel(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleCheckpoint();
                }}
                placeholder="Checkpoint label…"
                className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
              <button
                type="button"
                onClick={() => void handleCheckpoint()}
                disabled={addingCheckpoint || !checkpointLabel.trim()}
                className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {addingCheckpoint ? "Saving…" : "Add checkpoint"}
              </button>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          {sliceLines.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                App log slice (deterministic, from markers)
              </h4>
              <pre className="mt-1 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                {sliceLines.map((line, index) => (
                  <div
                    key={index}
                    className={
                      line.startsWith("[sentinel]")
                        ? "font-semibold text-indigo-600 dark:text-indigo-400"
                        : ""
                    }
                  >
                    {line}
                  </div>
                ))}
              </pre>
            </div>
          )}
          {session.screenshots.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Screenshots ({session.screenshots.length})
              </h4>
              <ul className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
                {session.screenshots.map((shot) => (
                  <li key={shot.id} className="flex flex-col gap-1">
                    <button
                      type="button"
                      onClick={() =>
                        onZoom(screenshotUrl(session.id, shot.path))
                      }
                      className="overflow-hidden rounded-lg border border-slate-200 transition-transform hover:scale-105 dark:border-slate-800"
                      aria-label="View screenshot"
                    >
                      <img
                        src={screenshotUrl(session.id, shot.path)}
                        alt={`Screenshot ${new Date(shot.captured_at).toLocaleString()}`}
                        className="h-24 w-full object-cover"
                        loading="lazy"
                      />
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleExport(shot.id)}
                      className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      Export to portfolio
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TriageCard({ triage }: { triage: TriageRecord }) {
  const evidence = triage.evidence;
  const hasContent =
    evidence.error_lines.length > 0 ||
    evidence.frames.length > 0 ||
    evidence.patterns.length > 0;

  if (!hasContent && !evidence.note) {
    return (
      <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
        No error lines or traceback frames found in the log slice.
      </p>
    );
  }

  return (
    <div className="mt-3 flex flex-col gap-3">
      {evidence.error_lines.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            Error lines (verbatim from the app log)
          </h5>
          <pre className="mt-1 max-h-40 overflow-auto rounded-lg border border-red-200 bg-red-50 p-3 text-[11px] leading-relaxed text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
            {evidence.error_lines.map((line, index) => (
              <div key={index}>{line}</div>
            ))}
          </pre>
        </div>
      )}
      {evidence.patterns.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {evidence.patterns.map((pattern) => (
            <span
              key={pattern}
              className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 dark:border-indigo-900 dark:bg-indigo-500/10 dark:text-indigo-300"
            >
              {pattern}
            </span>
          ))}
        </div>
      )}
      {evidence.frames.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            Traceback frames → project files
          </h5>
          <ul className="mt-1 flex flex-col gap-2">
            {evidence.frames.map((frame, index) => (
              <li
                key={index}
                className="rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-900"
              >
                <div className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                  {frame.relative_path}:{frame.line}
                  {frame.function ? ` in ${frame.function}` : ""}
                </div>
                {frame.source.length > 0 && (
                  <pre className="mt-1 overflow-auto rounded border border-slate-100 bg-slate-50 p-2 text-[10px] leading-relaxed text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-400">
                    {frame.source.map((line) => (
                      <div
                        key={line.line_number}
                        className={
                          line.line_number === frame.line
                            ? "bg-red-100 font-semibold text-red-700 dark:bg-red-950 dark:text-red-300"
                            : ""
                        }
                      >
                        <span className="mr-2 inline-block w-6 text-right text-slate-400">
                          {line.line_number}
                        </span>
                        {line.text}
                      </div>
                    ))}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {evidence.note && (
        <p className="text-[11px] italic text-slate-400 dark:text-slate-500">
          {evidence.note}
        </p>
      )}
      {triage.summary && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
          <h5 className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            AI summary (interpretation only — no fixes, no decisions)
          </h5>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {triage.summary}
          </p>
          <p className="mt-2 text-[11px] text-slate-400 dark:text-slate-500">
            {triage.model} · {formatWhen(triage.created_at)}
          </p>
        </div>
      )}
    </div>
  );
}

function CreateDialog({
  projects,
  onClose,
  onCreated,
}: {
  projects: { id: string; name: string }[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const { toast } = useUI();
  const [projectId, setProjectId] = useState("");
  const [title, setTitle] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [creating, setCreating] = useState(false);

  async function handleCreate() {
    if (!projectId || !title.trim()) return;
    setCreating(true);
    try {
      await startSession({
        project_id: projectId,
        title: title.trim(),
        expected_output: expectedOutput.trim() || null,
      });
      toast(
        "Session started — a marker was written into the app log.",
        "success",
      );
      onCreated();
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Failed to start session.",
        "error",
      );
      setCreating(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
      onClick={onClose}
      role="dialog"
      aria-label="New session"
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          New session
        </h3>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          The session writes a `[sentinel] Session started` marker into the
          app's own log — the slice is captured when you end it.
        </p>
        <label className="mt-4 flex flex-col gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          Project
          <select
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Select a project</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <label className="mt-3 flex flex-col gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          Title
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Play through first level"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <label className="mt-3 flex flex-col gap-1 text-xs font-medium text-slate-500 dark:text-slate-400">
          Expected output
          <textarea
            value={expectedOutput}
            onChange={(event) => setExpectedOutput(event.target.value)}
            placeholder="What should the app do? (optional)"
            rows={2}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleCreate()}
            disabled={creating || !projectId || !title.trim()}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white"
          >
            {creating ? "Starting…" : "Start session"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ExportDialog({
  result,
  onClose,
}: {
  result: SessionExport;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // clipboard unavailable — the text stays selectable in the pre blocks
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6"
      onClick={onClose}
      role="dialog"
      aria-label="Export result"
    >
      <div
        className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Export to portfolio
        </h3>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Screenshots copied into your portfolio repo. Paste the card HTML into
          index.html, then push the site manually — Sentinel never pushes.
        </p>
        <ul className="mt-3 flex flex-col gap-1">
          {result.copied.map((path) => (
            <li
              key={path}
              className="text-xs text-slate-500 dark:text-slate-400"
            >
              ✓ {path}
            </li>
          ))}
        </ul>
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Card HTML
            </h4>
            <button
              type="button"
              onClick={() => void copyText(result.snippet)}
              className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <pre className="mt-1 max-h-56 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
            {result.snippet}
          </pre>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

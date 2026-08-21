import { useEffect, useMemo, useState } from "react";
import type { Project, TimelineEvent } from "../types";
import { getTimeline } from "../api/observatory";
import { listProjects } from "../api/projects";

const KIND_STYLE: Record<TimelineEvent["kind"], string> = {
  "project-created": "bg-sky-500",
  commit: "bg-violet-500",
  build: "bg-emerald-500",
  test: "bg-amber-500",
  finding: "bg-rose-500",
};

const KIND_CHIPS: { kind: TimelineEvent["kind"] | "all"; label: string }[] = [
  { kind: "all", label: "All" },
  { kind: "commit", label: "Commits" },
  { kind: "build", label: "Builds" },
  { kind: "test", label: "Tests" },
  { kind: "finding", label: "Findings" },
  { kind: "project-created", label: "Created" },
];

const PAGE_SIZE = 100;

function eventDate(event: TimelineEvent): Date {
  return new Date(event.at + (event.at.endsWith("Z") ? "" : "Z"));
}

export default function ProjectTimeline() {
  const [days, setDays] = useState(365);
  const [kind, setKind] = useState<TimelineEvent["kind"] | "all">("all");
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then((response) => setProjects(response.projects))
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    setEvents([]);
    setHasMore(false);
    setLoading(true);
    getTimeline({
      days,
      kinds: kind === "all" ? [] : [kind],
      projectId: projectId || undefined,
      offset: 0,
      limit: PAGE_SIZE,
    })
      .then((timeline) => {
        setEvents(timeline.events);
        setHasMore(timeline.has_more);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [days, kind, projectId]);

  const loadMore = () => {
    getTimeline({
      days,
      kinds: kind === "all" ? [] : [kind],
      projectId: projectId || undefined,
      offset: events.length,
      limit: PAGE_SIZE,
    })
      .then((timeline) => {
        setEvents((prev) => [...prev, ...timeline.events]);
        setHasMore(timeline.has_more);
      })
      .catch((e) => setError(String(e)));
  };

  // v1.17.9: group by local day so a long window is scannable instead of
  // one endless list (backend still returns newest-first).
  const groups = useMemo(() => {
    const byDay = new Map<string, { date: Date; events: TimelineEvent[] }>();
    for (const event of events) {
      const date = eventDate(event);
      const key = date.toDateString();
      const entry = byDay.get(key) ?? { date, events: [] };
      entry.events.push(event);
      byDay.set(key, entry);
    }
    return [...byDay.values()].map(({ date, events: dayEvents }) => ({
      label: date.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      }),
      events: dayEvents,
    }));
  }, [events]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-neutral-400">
          <span>Window</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded bg-neutral-800 px-2 py-1 text-sm text-neutral-100"
          >
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={90}>90 days</option>
            <option value={365}>Year</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-neutral-400">
          <span>Project</span>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded bg-neutral-800 px-2 py-1 text-sm text-neutral-100"
          >
            <option value="">All projects</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-1.5">
          {KIND_CHIPS.map((chip) => (
            <button
              key={chip.kind}
              type="button"
              onClick={() => setKind(chip.kind)}
              className={`rounded-full px-3 py-0.5 text-xs transition-colors ${
                kind === chip.kind
                  ? "bg-neutral-700 text-neutral-100"
                  : "bg-neutral-900 text-neutral-400 hover:bg-neutral-800"
              }`}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-red-500 text-sm">Timeline failed to load: {error}</p>}
      {!error && loading && <p className="text-sm text-neutral-500">Loading timeline…</p>}
      {!error && !loading && events.length === 0 && (
        <p className="text-sm text-neutral-500">No activity in this window.</p>
      )}
      {!error && !loading && events.length > 0 && (
        <ol className="space-y-5">
          {groups.map((group) => (
            <li key={group.label}>
              <h3 className="mb-2 border-b border-neutral-800 pb-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                {group.label} — {group.events.length}{" "}
                {group.events.length === 1 ? "event" : "events"}
              </h3>
              <ol className="relative space-y-3 border-l border-neutral-800 pl-5">
                {group.events.map((event, index) => (
                  <li
                    key={`${event.kind}-${event.at}-${index}`}
                    className="relative"
                  >
                    <span
                      className={`absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full ${KIND_STYLE[event.kind]}`}
                    />
                    <div className="flex items-baseline justify-between gap-2 text-sm">
                      <span className="text-neutral-100">
                        {event.project_name}
                      </span>
                      <time className="shrink-0 text-xs text-neutral-500">
                        {eventDate(event).toLocaleTimeString(undefined, {
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                      </time>
                    </div>
                    <p className="truncate text-xs text-neutral-400" title={event.message}>
                      {event.message}
                    </p>
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      )}
      {hasMore && (
        <button
          type="button"
          onClick={loadMore}
          className="rounded bg-neutral-800 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700"
        >
          Load more
        </button>
      )}
    </div>
  );
}
import { useEffect, useState } from "react"
import type { TimelineEvent } from "../types"
import { getTimeline } from "../api/observatory"

const KIND_STYLE: Record<TimelineEvent["kind"], string> = {
  "project-created": "bg-sky-500",
  commit: "bg-violet-500",
  build: "bg-emerald-500",
  test: "bg-amber-500",
  finding: "bg-rose-500",
}

export default function ProjectTimeline() {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null)
  const [days, setDays] = useState(365)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setEvents(null)
    getTimeline(days)
      .then((timeline) => setEvents(timeline.events))
      .catch((e) => setError(String(e)))
  }, [days])

  return (
    <div className="space-y-4">
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
      {error && <p className="text-red-500 text-sm">Timeline failed to load: {error}</p>}
      {!error && !events && <p className="text-sm text-neutral-500">Loading timeline…</p>}
      {!error && events && events.length === 0 && (
        <p className="text-sm text-neutral-500">No activity in this window.</p>
      )}
      <ol className="relative space-y-3 border-l border-neutral-800 pl-5">
        {events?.map((event, index) => (
          <li key={`${event.kind}-${event.at}-${index}`} className="relative">
            <span
              className={`absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full ${KIND_STYLE[event.kind]}`}
            />
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="text-neutral-100">{event.project_name}</span>
              <time className="shrink-0 text-xs text-neutral-500">
                {new Date(event.at + (event.at.endsWith("Z") ? "" : "Z")).toLocaleString()}
              </time>
            </div>
            <p className="truncate text-xs text-neutral-400">{event.message}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}
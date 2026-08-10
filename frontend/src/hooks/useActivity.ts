import { useEffect, useRef, useState } from "react";

import { getActivity } from "../api/system";
import type { ActivityEvent } from "../api/system";
import { useWebSocket } from "./useWebSocket";
import type { WsStatus } from "./useWebSocket";

const MAX_EVENTS = 200;
const FALLBACK_POLL_MS = 15_000;

/**
 * Live activity feed (v1.17): prefers the /api/v1/ws/jobs channel and falls
 * back to polling /system/activity every 15s while the socket is not open
 * (server down, tests, restricted environments).
 */
export function useActivity() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const { status, lastMessage } = useWebSocket("/api/v1/ws/jobs");
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    if (lastMessage?.type !== "activity") return;
    const event = (lastMessage as { event?: ActivityEvent }).event;
    if (!event) return;
    setEvents((current) => mergeEvents(current, [event]));
  }, [lastMessage]);

  useEffect(() => {
    if (status === "open") {
      if (pollTimer.current !== null) window.clearInterval(pollTimer.current);
      return;
    }
    const poll = async () => {
      try {
        const data = await getActivity(100);
        setEvents((current) =>
          mergeEvents(current, Array.isArray(data) ? data : []),
        );
      } catch {
        // Socket closed and history unavailable — retry on the next tick.
      }
    };
    void poll();
    pollTimer.current = window.setInterval(() => void poll(), FALLBACK_POLL_MS);
    return () => {
      if (pollTimer.current !== null) window.clearInterval(pollTimer.current);
    };
  }, [status]);

  return { events, status };
}

function mergeEvents(
  current: ActivityEvent[],
  incoming: ActivityEvent[],
): ActivityEvent[] {
  const seen = new Set<string>();
  const key = (event: ActivityEvent) =>
    event.id ?? `${event.kind}|${event.message}|${event.created_at}`;
  const merged = [...incoming, ...current].filter((event) => {
    const k = key(event);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return merged
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .slice(0, MAX_EVENTS);
}

export type { WsStatus as ActivityStatus };

import { useCallback, useEffect, useRef, useState } from "react";

import { getActivity } from "../api/system";
import type { ActivityEvent } from "../api/system";
import { useWebSocket } from "./useWebSocket";
import type { WsStatus } from "./useWebSocket";

const MAX_EVENTS = 200;
const FALLBACK_POLL_MS = 15_000;
const RETRY_AFTER_EMPTY_MS = 1_500;

/**
 * Live activity feed (v1.17+): persists across page switches.
 *
 * v1.17.1: on mount the persisted history (`GET /system/activity`) is loaded
 * once, so the feed is never empty when you navigate here — then live events
 * merge in over `/api/v1/ws/jobs`. While the socket is closed (server down,
 * tests, restricted environments) a 15s poll of /system/activity stands in.
 *
 * v1.17.2: the seed is self-healing — it re-runs when the socket comes up
 * (a mount seed can race startup writes) and retries once shortly after
 * mount when it came back empty, so cached history shows even under load.
 */
export function useActivity() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const { status, lastMessage } = useWebSocket("/api/v1/ws/jobs");
  const pollTimer = useRef<number | null>(null);
  const retryTimer = useRef<number | null>(null);

  const mergeHistory = useCallback((history: ActivityEvent[]) => {
    setEvents((current) => mergeEvents(current, history));
  }, []);

  useEffect(() => {
    let active = true;
    const seed = () =>
      getActivity(MAX_EVENTS)
        .then((history) => {
          if (!active) return;
          mergeHistory(history);
          if (history.length === 0) {
            // v1.17.2: the seed may have run before the server finished
            // persisting startup events — give history one more chance.
            retryTimer.current = window.setTimeout(() => {
              getActivity(MAX_EVENTS)
                .then((again) => {
                  if (active) mergeHistory(again);
                })
                .catch(() => {
                  /* still nothing — live events will fill the feed */
                });
            }, RETRY_AFTER_EMPTY_MS);
          }
        })
        .catch(() => {
          /* history unavailable — live events will still flow in */
        });
    void seed();
    return () => {
      active = false;
      if (retryTimer.current !== null) window.clearTimeout(retryTimer.current);
    };
  }, [mergeHistory]);

  useEffect(() => {
    if (lastMessage?.type !== "activity") return;
    const event = (lastMessage as { event?: ActivityEvent }).event;
    if (!event) return;
    setEvents((current) => mergeEvents(current, [event]));
  }, [lastMessage]);

  useEffect(() => {
    if (status === "open") {
      if (pollTimer.current !== null) window.clearInterval(pollTimer.current);
      // v1.17.2: re-seed now that the channel is up — a mount seed that ran
      // mid-startup can have missed rows persisted moments later.
      getActivity(100)
        .then((history) => mergeHistory(history))
        .catch(() => {
          /* live frames will keep the feed moving */
        });
      return;
    }
    const poll = async () => {
      try {
        const data = await getActivity(100);
        mergeHistory(Array.isArray(data) ? data : []);
      } catch {
        // Socket closed and history unavailable — retry on the next tick.
      }
    };
    void poll();
    pollTimer.current = window.setInterval(() => void poll(), FALLBACK_POLL_MS);
    return () => {
      if (pollTimer.current !== null) window.clearInterval(pollTimer.current);
    };
  }, [status, mergeHistory]);

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

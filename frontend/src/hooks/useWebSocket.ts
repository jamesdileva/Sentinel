import { useCallback, useEffect, useRef, useState } from "react";

export type WsStatus = "connecting" | "open" | "closed";

export interface WsMessage {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  reconnect?: boolean;
  onMessage?: (message: WsMessage) => void;
}

const MAX_RECONNECT_DELAY_MS = 30_000;
// v1.17.18.4 (audit2 F1): the server sends a heartbeat every 30 s
// (api/v1/ws.py). If nothing — not even a heartbeat — arrives within this
// window while the socket claims to be open, the connection is dead without
// FIN (sleep/resume, NAT drop); force-close so onclose reconnects and the
// header stops showing a false "live".
const LIVENESS_TIMEOUT_MS = 75_000;

function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}

/**
 * Subscribe to a Sentinel WebSocket channel with automatic reconnect and
 * exponential backoff. Uses the Vite dev proxy (`/api` → backend) so the
 * same path works in development and production.
 */
export function useWebSocket(
  path: string,
  { reconnect = true, onMessage }: UseWebSocketOptions = {},
) {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);
  const attemptRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  const reconnectRef = useRef(reconnect);
  const lastSeenRef = useRef<number>(Date.now());
  const livenessTimerRef = useRef<number | null>(null);

  onMessageRef.current = onMessage;

  useEffect(() => {
    reconnectRef.current = reconnect;
  }, [reconnect]);

  const connect = useCallback(() => {
    if (typeof WebSocket === "undefined") {
      // jsdom and other non-browser environments have no WebSocket; degrade
      // to "closed" so callers can fall back to HTTP polling.
      setStatus("closed");
      return;
    }
    setStatus("connecting");
    lastSeenRef.current = Date.now();
    const socket = new WebSocket(wsUrl(path));
    socketRef.current = socket;

    socket.onopen = () => {
      attemptRef.current = 0;
      setStatus("open");
    };
    socket.onmessage = (event) => {
      let message: WsMessage;
      try {
        message = JSON.parse(String(event.data));
      } catch {
        message = { type: "raw", data: String(event.data) };
      }
      lastSeenRef.current = Date.now();
      setLastMessage(message);
      onMessageRef.current?.(message);
    };
    socket.onclose = () => {
      setStatus("closed");
      if (!reconnectRef.current) return;
      const delay = Math.min(
        1000 * 2 ** attemptRef.current++,
        MAX_RECONNECT_DELAY_MS,
      );
      timerRef.current = window.setTimeout(connect, delay);
    };
    socket.onerror = () => {
      socket.close();
    };

    // Liveness watchdog (v1.17.18.4, audit2 F1): reconnect only fired from
    // onclose before, so a silently-dead socket stayed "live" forever.
    if (livenessTimerRef.current !== null) {
      window.clearInterval(livenessTimerRef.current);
    }
    livenessTimerRef.current = window.setInterval(() => {
      if (
        socketRef.current === socket &&
        socket.readyState === WebSocket.OPEN &&
        Date.now() - lastSeenRef.current > LIVENESS_TIMEOUT_MS
      ) {
        socket.close();
      }
    }, 15_000);
  }, [path]);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      if (livenessTimerRef.current !== null) {
        window.clearInterval(livenessTimerRef.current);
        livenessTimerRef.current = null;
      }
      socketRef.current?.close();
    };
  }, [connect]);

  return { status, lastMessage };
}

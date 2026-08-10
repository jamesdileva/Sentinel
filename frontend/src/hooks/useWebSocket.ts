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
  }, [path]);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  return { status, lastMessage };
}

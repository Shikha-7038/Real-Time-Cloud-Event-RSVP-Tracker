import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "../api";

/**
 * useEventSocket - opens a real WebSocket connection to the backend for
 * one event and keeps `counts` updated the instant the server pushes a
 * change (see backend/app/routers/rsvp.py: _broadcast_counts). This is
 * the genuine real-time mechanism - no setInterval/polling anywhere in
 * this hook.
 *
 * Auto-reconnects with backoff if the connection drops (handles the
 * server restarting, network blips, etc. - basic resilience for a
 * "real-time" feature so a dropped socket doesn't silently freeze the UI).
 */
export function useEventSocket(eventId, onAnnouncement) {
  const [counts, setCounts] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const retryDelay = useRef(1000);
  const closedByUs = useRef(false);

  useEffect(() => {
    if (!eventId) return;
    closedByUs.current = false;

    function connect() {
      const ws = new WebSocket(`${WS_BASE}/events/${eventId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryDelay.current = 1000; // reset backoff on success
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "counts_update") {
            setCounts(msg);
          } else if (msg.type === "announcement" && onAnnouncement) {
            onAnnouncement(msg);
          }
        } catch (e) {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs.current) {
          setTimeout(connect, retryDelay.current);
          retryDelay.current = Math.min(retryDelay.current * 2, 10000);
        }
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      closedByUs.current = true;
      wsRef.current?.close();
    };
  }, [eventId]);

  return { counts, connected };
}

import { useEffect, useRef } from "react";
import { apiBase } from "@/lib/api";
import type { SSEPayload } from "@/types";

/**
 * Subscribe to the backend SSE stream. Dispatches every message to the
 * provided handler. A single EventSource is shared across the component
 * tree — the handler updates on every render but the socket does not
 * reconnect unless the component remounts.
 *
 * See `docs/client_server.md` for the refetch lifecycle.
 */
export function useSSE(onEvent: (payload: SSEPayload) => void): void {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    const source = new EventSource(`${apiBase}/events`, {
      withCredentials: true,
    });

    source.onmessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as SSEPayload;
        handlerRef.current(payload);
      } catch (err) {
        console.error("SSE payload parse failed", err, event.data);
      }
    };

    source.onerror = (event) => {
      // EventSource auto-reconnects; surface transient errors for debugging.
      console.warn("SSE connection hiccup", event);
    };

    return () => source.close();
  }, []);
}

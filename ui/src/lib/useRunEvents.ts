"use client";

/**
 * `useRunEvents(runId)`: a run's event stream, reduced to a `RunView` (docs/07 §1, §9).
 *
 * - Frames are named SSE events (`event: <type>`), so `onmessage` never fires; there is
 *   one listener per type.
 * - The stream is closed on `run.finished`. Left open, the browser would reconnect to a
 *   finished run every few seconds.
 * - While the browser is retrying on its own, it sends `Last-Event-ID` and the server
 *   resumes. If the browser gives up (the connection is CLOSED), the hook replays
 *   `GET /runs/{id}/events` and opens a new stream; `seq` dedup drops what it already has.
 * - An SSE frame without an id keeps the previous `lastEventId`. A repeated id is treated
 *   as "no id", so the API's synthetic finish for an interrupted run is not dropped.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useState } from "react";

import { api, streamUrl } from "./api";
import { EVENT_TYPES, type EventType, type RunEvent } from "./events";
import { initialRun, reduceRun, toRunEvent, type RunView } from "./reducer";

export type Connection = "idle" | "open" | "reconnecting" | "closed" | "gave_up";

type Action =
  | { kind: "reset"; runId: string | null }
  | { kind: "event"; event: RunEvent }
  | { kind: "events"; events: RunEvent[] };

function viewReducer(view: RunView, action: Action): RunView {
  switch (action.kind) {
    case "reset":
      return initialRun(action.runId);
    case "event":
      return reduceRun(view, action.event);
    case "events":
      return action.events.reduce(reduceRun, view);
  }
}

const MAX_RETRIES = 5;

export function useRunEvents(runId: string | null): { view: RunView; connection: Connection } {
  const [view, dispatch] = useReducer(viewReducer, runId, initialRun);
  const [connection, setConnection] = useState<Connection>("idle");
  const queryClient = useQueryClient();

  useEffect(() => {
    dispatch({ kind: "reset", runId });
    if (!runId) {
      setConnection("idle");
      return;
    }

    let cancelled = false;
    let finished = false;
    let retries = 0;
    let lastId: string | null = null;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const finish = () => {
      finished = true;
      source?.close();
      setConnection("closed");
      void queryClient.invalidateQueries({ queryKey: ["run", runId] });
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    };

    const listener = (type: EventType) => (message: MessageEvent<string>) => {
      if (cancelled) return;
      let payload: unknown;
      try {
        payload = JSON.parse(message.data);
      } catch {
        return;
      }
      const repeated = message.lastEventId === "" || message.lastEventId === lastId;
      const seq = repeated ? null : Number(message.lastEventId);
      if (!repeated) lastId = message.lastEventId;
      const event = toRunEvent({ type, seq, payload });
      if (!event) return;
      dispatch({ kind: "event", event });
      if (type === "run.finished") finish();
    };

    const replayThenReopen = async () => {
      try {
        const records = await api.runEvents(runId);
        if (cancelled) return;
        const events = records.map(toRunEvent).filter((event): event is RunEvent => event !== null);
        dispatch({ kind: "events", events });
        if (events.some((event) => event.type === "run.finished")) {
          finish();
          return;
        }
      } catch {
        // Unknown yet (a run whose first event has not been written): just retry the stream.
      }
      if (!cancelled) open();
    };

    const open = () => {
      source = new EventSource(streamUrl(runId));
      for (const type of EVENT_TYPES) {
        source.addEventListener(type, listener(type) as EventListener);
      }
      source.onopen = () => {
        retries = 0;
        setConnection("open");
      };
      source.onerror = () => {
        if (cancelled || finished || !source) return;
        if (source.readyState !== EventSource.CLOSED) {
          setConnection("reconnecting"); // the browser retries and sends Last-Event-ID
          return;
        }
        source.close();
        if (retries >= MAX_RETRIES) {
          setConnection("gave_up");
          return;
        }
        const delay = 1000 * 2 ** Math.min(retries, 2);
        retries += 1;
        setConnection("reconnecting");
        timer = setTimeout(() => void replayThenReopen(), delay);
      };
    };

    open();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      source?.close();
    };
  }, [runId, queryClient]);

  return { view, connection };
}

"use client";

/**
 * A past run for `/runs/[id]` (docs/07 §4): the saved events from `GET /runs/{id}/events`
 * and the record from `GET /runs/{id}`. A run whose replay has no `run.finished` is still
 * going (or was interrupted), so the live stream is attached; it replays from the start,
 * and the page switches to it once it has caught up.
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { api } from "./api";
import type { RunEvent } from "./events";
import { initialRun, reduceEvents, toRunEvent } from "./reducer";
import { useRunEvents } from "./useRunEvents";

export function useRun(runId: string) {
  const replay = useQuery({
    queryKey: ["run-events", runId],
    queryFn: () => api.runEvents(runId),
    retry: false,
  });
  const record = useQuery({ queryKey: ["run", runId], queryFn: () => api.run(runId), retry: false });

  const replayView = useMemo(() => {
    const events = (replay.data ?? [])
      .map(toRunEvent)
      .filter((event): event is RunEvent => event !== null);
    return reduceEvents(events, initialRun(runId));
  }, [replay.data, runId]);

  const needsLive = replay.isSuccess && !replayView.finished;
  const live = useRunEvents(needsLive ? runId : null);
  const view = needsLive && live.view.lastSeq >= replayView.lastSeq ? live.view : replayView;

  return {
    view,
    record: record.data ?? null,
    connection: needsLive ? live.connection : "closed",
    loading: replay.isLoading,
    error: replay.error,
  };
}

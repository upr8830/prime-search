/**
 * Event stream payloads (docs/02 §4, as the backend actually emits them).
 *
 * The OpenAPI schema carries every model that appears in a RunRecord (Answer, Evidence,
 * Verdict, ...). The small payloads that exist only on the stream are typed here, with
 * the shapes the code emits rather than the ones the table idealizes:
 * - the baseline sends two `search` frames per tool call, the second with `query: ""`;
 * - a task that failed or started past the deadline sends a flat `task.done`;
 * - the API sends a synthetic `error` + `run.finished` without an id for an interrupted run.
 */

import type {
  Answer,
  CriticReport,
  Evidence,
  QueryUnderstanding,
  SearchPlan,
  TaskResult,
  Usage,
  Verdict,
} from "./types";

export const EVENT_TYPES = [
  "run.started",
  "understanding",
  "plan",
  "task.started",
  "search",
  "fetch",
  "evidence",
  "task.done",
  "verdict",
  "critique",
  "token",
  "answer",
  "usage",
  "run.finished",
  "error",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

export type Mode = "prime" | "baseline";
export type Depth = "fast" | "deep";
export type FinishStatus = "completed" | "budget_exhausted" | "failed";

export type RunStartedPayload = {
  run_id: string;
  question: string;
  mode: Mode;
  depth?: Depth;
  trace_url?: string | null;
};

/** The SearchPlan plus the root's plan cell; `code` is null from a fallback rung and
 * absent in runs recorded before it was emitted. */
export type PlanPayload = SearchPlan & { code?: string | null };

export type TaskStartedPayload = {
  task_id: string;
  branch_id: string;
  round: number;
  instruction: string;
};

export type SearchPayload = {
  task_id: string | null;
  query: string;
  n_results: number | null;
  cached: boolean;
  tool?: string;
};

export type FetchPayload = {
  task_id: string | null;
  doc_id: string;
  url: string;
  title: string;
  tier: string;
  effective_date: string | null;
};

export type TaskDoneResultPayload = { task_id: string; result: TaskResult };
export type TaskDoneFlatPayload = {
  task_id: string;
  branch_id: string;
  evidence: number;
  unresolved: string | null;
};
export type TaskDonePayload = TaskDoneResultPayload | TaskDoneFlatPayload;

export type TokenPayload = { text: string };

export type RunFinishedPayload = {
  status: FinishStatus;
  langsmith_run_url: string | null;
  usage?: Usage;
};

export type ErrorPayload = { message: string; node: string };

export type PayloadByType = {
  "run.started": RunStartedPayload;
  understanding: QueryUnderstanding;
  plan: PlanPayload;
  "task.started": TaskStartedPayload;
  search: SearchPayload;
  fetch: FetchPayload;
  evidence: Evidence;
  "task.done": TaskDonePayload;
  verdict: Verdict;
  critique: CriticReport;
  token: TokenPayload;
  answer: Answer;
  usage: Usage;
  "run.finished": RunFinishedPayload;
  error: ErrorPayload;
};

/** One event as the reducer sees it, from the stream (`seq` is the SSE id, null on a
 * synthetic frame) or from `GET /runs/{id}/events`. */
export type RunEvent = {
  [K in EventType]: { type: K; seq: number | null; payload: PayloadByType[K] };
}[EventType];

export function isEventType(value: string): value is EventType {
  return (EVENT_TYPES as readonly string[]).includes(value);
}

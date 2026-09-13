/**
 * The API (docs/07 §7). REST goes through the `/api` rewrite in next.config.ts; the event
 * stream connects to the API origin directly, because a dev rewrite can buffer it.
 */

import type {
  ApiEvent,
  BenchQuestion,
  BenchSummary,
  DocView,
  FeedbackIn,
  Ok,
  RunRecord,
  RunRequest,
  RunStarted,
  RunSummary,
  UiEventIn,
} from "./types";

export const API_ORIGIN = process.env.NEXT_PUBLIC_PRIME_API_ORIGIN ?? "http://127.0.0.1:8765";
const REST = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${REST}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...init?.headers },
    });
  } catch (error) {
    throw new ApiError(`The API is unreachable at ${API_ORIGIN}: ${String(error)}`, 0);
  }
  if (!response.ok) {
    // FastAPI puts a readable message in `detail` (a string for our 404/422s, a list for
    // request validation errors); show that rather than a bare status.
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      // not JSON (a proxy error page): keep the status line
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const enc = encodeURIComponent;

export const api = {
  startRun: (body: RunRequest) => request<RunStarted>("/run", post(body)),
  runs: () => request<RunSummary[]>("/runs"),
  run: (runId: string) => request<RunRecord>(`/runs/${enc(runId)}`),
  runEvents: (runId: string) => request<ApiEvent[]>(`/runs/${enc(runId)}/events`),
  document: (runId: string, docId: string, offset = 0, limit = 200) =>
    request<DocView>(`/docs/${enc(runId)}/${enc(docId)}?offset=${offset}&limit=${limit}`),
  feedback: (body: FeedbackIn) => request<Ok>("/feedback", post(body)),
  uiEvent: (body: UiEventIn) => request<Ok>("/ui-event", post(body)),
  benchQuestions: (split?: "train" | "dev" | "holdout") =>
    request<BenchQuestion[]>(`/bench/questions${split ? `?split=${split}` : ""}`),
  benchSummary: () => request<BenchSummary>("/bench/summary"),
};

/** `GET /run/{id}/events` (docs/02 §4), opened with `EventSource` against the API origin. */
export function streamUrl(runId: string): string {
  return `${API_ORIGIN}/run/${enc(runId)}/events`;
}

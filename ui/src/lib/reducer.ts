/**
 * One run, rebuilt from its events (docs/02 §4). The same pure reducer feeds the live
 * compare view (SSE) and the run detail page (`GET /runs/{id}/events`), so a replayed run
 * looks exactly like a watched one.
 *
 * It absorbs the stream as the backend really emits it:
 * - events are applied once: any `seq` at or below the last applied one is dropped, so
 *   replaying a file and then attaching the live stream is safe; a frame without an id
 *   (the API's synthetic finish for an interrupted run) is always applied;
 * - streamed `token` text is provisional: synthesis rewrites it, and `answer` replaces it;
 * - the baseline sends two `search` frames per tool call, the second with `query: ""`;
 * - a task that failed or started past the deadline sends a flat `task.done`;
 * - no event marks a round boundary, so the timeline keeps arrival order;
 * - an `error` is a red alert only at severity `error`; a `warning` is a muted note, on its
 *   task when it names one. Older runs carry no severity, so it is inferred from the node.
 */

import type {
  Depth,
  ErrorPayload,
  FetchPayload,
  Mode,
  PlanPayload,
  RunEvent,
  SearchPayload,
} from "./events";
import { isEventType } from "./events";
import type {
  Answer,
  ApiEvent,
  CriticReport,
  Evidence,
  QueryUnderstanding,
  TaskResult,
  Usage,
  Verdict,
} from "./types";

export type ViewStatus =
  | "connecting"
  | "running"
  | "completed"
  | "budget_exhausted"
  | "failed"
  | "interrupted";

export type TaskOrigin = "plan" | "judge" | "critic";
export type TaskStatus = "running" | "done" | "failed";
export type BranchStatus = "pending" | "running" | "done" | "failed";

export type TaskNode = {
  taskId: string;
  branchId: string;
  round: number;
  instruction: string;
  origin: TaskOrigin;
  status: TaskStatus;
  searches: SearchPayload[];
  fetchDocIds: string[];
  result: TaskResult | null;
  unresolved: string | null;
};

export type NoticeSeverity = "error" | "warning";

/** An `error` event as a reader sees it (docs/07 §3). */
export type Notice = {
  severity: NoticeSeverity;
  node: string;
  /** The task a warning belongs to; null when it belongs to the pane. */
  taskId: string | null;
  /** Plain words for the reader. */
  summary: string;
  /** The engineer's message, shown on hover. */
  detail: string;
};

export type BaselineSearch = { query: string; nResults: number | null; tool: string | null };

/** Arrival order of the things the search tree draws between rounds. */
export type LogEntry =
  | { kind: "task"; taskId: string }
  | { kind: "verdict"; index: number }
  | { kind: "critique"; index: number };

export type RunView = {
  runId: string | null;
  mode: Mode | null;
  depth: Depth | null;
  question: string | null;
  traceUrl: string | null;
  status: ViewStatus;
  understanding: QueryUnderstanding | null;
  plan: PlanPayload | null;
  planCode: string | null;
  /** False for runs recorded before the plan event carried `code`. */
  planCodeRecorded: boolean;
  tasks: Record<string, TaskNode>;
  taskOrder: string[];
  log: LogEntry[];
  verdicts: Verdict[];
  critiques: CriticReport[];
  evidence: Evidence[];
  evidenceById: Record<string, Evidence>;
  fetches: Record<string, FetchPayload>;
  baselineSearches: BaselineSearch[];
  streamText: string;
  answer: Answer | null;
  usage: Usage | null;
  /** Every `error` payload as received; the interrupted check reads these. */
  errors: ErrorPayload[];
  /** The same events for display: severity resolved, attached to a task, deduplicated. */
  notices: Notice[];
  /** From `run.finished`; null when the event did not name them (older runs, baseline). */
  limitsReached: string[] | null;
  finished: boolean;
  lastSeq: number;
};

export const INTERRUPTED_PREFIX = "run interrupted";

export function initialRun(runId: string | null = null): RunView {
  return {
    runId,
    mode: null,
    depth: null,
    question: null,
    traceUrl: null,
    status: "connecting",
    understanding: null,
    plan: null,
    planCode: null,
    planCodeRecorded: false,
    tasks: {},
    taskOrder: [],
    log: [],
    verdicts: [],
    critiques: [],
    evidence: [],
    evidenceById: {},
    fetches: {},
    baselineSearches: [],
    streamText: "",
    answer: null,
    usage: null,
    errors: [],
    notices: [],
    limitsReached: null,
    finished: false,
    lastSeq: -1,
  };
}

/** `b1-r0` -> plan; `b1-r1`, `b1-r1-2` -> judge; `b1-r1-critic1` -> critic (docs/02 §2.3). */
export function taskOrigin(taskId: string, round: number): TaskOrigin {
  if (/-critic\d*$/.test(taskId)) return "critic";
  return round > 0 ? "judge" : "plan";
}

function roundFromTaskId(taskId: string): number {
  const match = /-r(\d+)/.exec(taskId);
  return match ? Number(match[1]) : 0;
}

function newTask(taskId: string, branchId: string, round: number, instruction: string): TaskNode {
  return {
    taskId,
    branchId,
    round,
    instruction,
    origin: taskOrigin(taskId, round),
    status: "running",
    searches: [],
    fetchDocIds: [],
    result: null,
    unresolved: null,
  };
}

function withTask(view: RunView, node: TaskNode): RunView {
  const known = node.taskId in view.tasks;
  return {
    ...view,
    tasks: { ...view.tasks, [node.taskId]: node },
    taskOrder: known ? view.taskOrder : [...view.taskOrder, node.taskId],
    log: known ? view.log : [...view.log, { kind: "task", taskId: node.taskId }],
  };
}

export function reduceRun(view: RunView, event: RunEvent): RunView {
  if (event.seq !== null) {
    if (event.seq <= view.lastSeq) return view;
    view = { ...view, lastSeq: event.seq };
  }
  if (!view.finished && view.status === "connecting") view = { ...view, status: "running" };

  switch (event.type) {
    case "run.started": {
      const payload = event.payload;
      return {
        ...view,
        runId: payload.run_id,
        question: payload.question,
        mode: payload.mode,
        depth: payload.depth ?? view.depth,
        traceUrl: payload.trace_url ?? view.traceUrl,
      };
    }
    case "understanding":
      return { ...view, understanding: event.payload };
    case "plan":
      return {
        ...view,
        plan: event.payload,
        planCode: event.payload.code ?? null,
        planCodeRecorded: "code" in event.payload,
      };
    case "task.started": {
      const { task_id, branch_id, round, instruction } = event.payload;
      const existing = view.tasks[task_id];
      const node = existing
        ? { ...existing, status: "running" as const }
        : newTask(task_id, branch_id, round, instruction);
      return withTask(view, node);
    }
    case "search": {
      const payload = event.payload;
      if (payload.task_id === null) return reduceBaselineSearch(view, payload);
      const node = view.tasks[payload.task_id];
      if (!node) return view;
      return withTask(view, { ...node, searches: [...node.searches, payload] });
    }
    case "fetch": {
      const payload = event.payload;
      let next: RunView = { ...view, fetches: { ...view.fetches, [payload.doc_id]: payload } };
      const node = payload.task_id ? next.tasks[payload.task_id] : undefined;
      if (node && !node.fetchDocIds.includes(payload.doc_id)) {
        next = withTask(next, { ...node, fetchDocIds: [...node.fetchDocIds, payload.doc_id] });
      }
      return next;
    }
    case "evidence": {
      const item = event.payload;
      if (item.evidence_id in view.evidenceById) return view;
      return {
        ...view,
        evidence: [...view.evidence, item],
        evidenceById: { ...view.evidenceById, [item.evidence_id]: item },
      };
    }
    case "task.done": {
      const payload = event.payload;
      if ("result" in payload) {
        const node =
          view.tasks[payload.task_id] ??
          newTask(payload.task_id, "", roundFromTaskId(payload.task_id), "");
        return withTask(view, {
          ...node,
          status: "done",
          result: payload.result,
          unresolved: payload.result.unresolved,
        });
      }
      const node =
        view.tasks[payload.task_id] ??
        newTask(payload.task_id, payload.branch_id, roundFromTaskId(payload.task_id), "");
      return withTask(view, { ...node, status: "failed", unresolved: payload.unresolved });
    }
    case "verdict":
      return {
        ...view,
        verdicts: [...view.verdicts, event.payload],
        log: [...view.log, { kind: "verdict", index: view.verdicts.length }],
      };
    case "critique":
      return {
        ...view,
        critiques: [...view.critiques, event.payload],
        log: [...view.log, { kind: "critique", index: view.critiques.length }],
      };
    case "token":
      // Once the final answer is in, a late token cannot overwrite it.
      return view.answer ? view : { ...view, streamText: view.streamText + event.payload.text };
    case "answer":
      return { ...view, answer: event.payload, streamText: "" };
    case "usage":
      return { ...view, usage: event.payload };
    case "error": {
      const notice = noticeFor(view, event.payload);
      const repeated = view.notices.some(
        (seen) => seen.severity === notice.severity && seen.taskId === notice.taskId && seen.summary === notice.summary,
      );
      return {
        ...view,
        errors: [...view.errors, event.payload],
        notices: repeated ? view.notices : [...view.notices, notice],
      };
    }
    case "run.finished": {
      const payload = event.payload;
      const interrupted =
        payload.status === "failed" &&
        view.errors.some((error) => error.message.startsWith(INTERRUPTED_PREFIX));
      return {
        ...view,
        status: interrupted ? "interrupted" : payload.status,
        traceUrl: payload.langsmith_run_url ?? view.traceUrl,
        usage: payload.usage ?? view.usage,
        limitsReached: payload.limits_reached ?? null,
        finished: true,
      };
    }
  }
}

// Nodes whose failures the run survives (02 §4). Runs recorded before `severity` existed
// carry none, so their events are read by node.
const WARNING_NODES = new Set(["search_agent", "judge", "critic", "plan", "synthesize"]);

const NODE_SUMMARY: Record<string, string> = {
  search_agent: "This line of research stopped because of a technical problem",
  judge: "The check of whether the research was complete could not run this round",
  critic: "The final review of the answer was skipped",
  plan: "The research followed a standard plan for this kind of question",
  synthesize: "Some citation markers matched no source and were removed from the answer",
};

/** The site of the first URL in a message, without `www.`. */
export function hostOf(text: string): string | null {
  const match = /https?:\/\/[^\s"'<>)]+/.exec(text);
  if (!match) return null;
  try {
    return new URL(match[0]).hostname.replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}

function noticeFor(view: RunView, payload: ErrorPayload): Notice {
  const base = payload.node.split(":")[0];
  const severity = payload.severity ?? (WARNING_NODES.has(base) ? "warning" : "error");
  return {
    severity,
    node: payload.node,
    taskId: payload.task_id ?? (severity === "warning" ? inferTaskId(view, payload) : null),
    summary: payload.summary ?? inferSummary(payload),
    detail: payload.message,
  };
}

/** Older runs: a branch's miss (`search_agent:b5`) belongs to that branch's running task,
 * or its latest; a crashed sub-agent's message starts with its task id. */
function inferTaskId(view: RunView, payload: ErrorPayload): string | null {
  const [base, branchId] = payload.node.split(":");
  if (base !== "search_agent") return null;
  if (!branchId) {
    const taskId = payload.message.split(":")[0];
    return Object.prototype.hasOwnProperty.call(view.tasks, taskId) ? taskId : null;
  }
  const tasks = tasksForBranch(view, branchId);
  const running = tasks.filter((task) => task.status === "running");
  return (running[running.length - 1] ?? tasks[tasks.length - 1])?.taskId ?? null;
}

function inferSummary(payload: ErrorPayload): string {
  const base = payload.node.split(":")[0];
  if (base === "search_agent" && payload.node.includes(":")) {
    if (payload.message.startsWith("fetch:")) {
      const host = hostOf(payload.message);
      return host ? `Couldn't read a page from ${host}` : "Couldn't read a page";
    }
    return "A web search failed";
  }
  return NODE_SUMMARY[base] ?? payload.message;
}

function reduceBaselineSearch(view: RunView, payload: SearchPayload): RunView {
  const tool = payload.tool ?? null;
  if (payload.query === "") {
    // The tool's result: fill the oldest call of this tool still waiting for a count.
    const index = view.baselineSearches.findIndex(
      (search) => search.nResults === null && search.tool === tool,
    );
    if (index === -1 || payload.n_results === null) return view;
    const baselineSearches = view.baselineSearches.map((search, i) =>
      i === index ? { ...search, nResults: payload.n_results } : search,
    );
    return { ...view, baselineSearches };
  }
  return {
    ...view,
    baselineSearches: [
      ...view.baselineSearches,
      { query: payload.query, nResults: payload.n_results, tool },
    ],
  };
}

export function reduceEvents(events: RunEvent[], start: RunView = initialRun()): RunView {
  return events.reduce(reduceRun, start);
}

/** A record from `GET /runs/{id}/events` (or a JSONL line) as a reducer event. */
export function toRunEvent(
  record: Pick<ApiEvent, "type" | "payload"> & { seq: number | null },
): RunEvent | null {
  if (!isEventType(record.type)) return null;
  return { type: record.type, seq: record.seq ?? null, payload: record.payload } as RunEvent;
}

// --- selectors ---------------------------------------------------------------------------

/** Branch ids in plan order, then any a task names that the plan does not. */
export function branchIds(view: RunView): string[] {
  const ids = view.plan?.branches.map((branch) => branch.branch_id) ?? [];
  for (const taskId of view.taskOrder) {
    const branchId = view.tasks[taskId].branchId;
    if (branchId && !ids.includes(branchId)) ids.push(branchId);
  }
  return ids;
}

export function tasksForBranch(view: RunView, branchId: string): TaskNode[] {
  return view.taskOrder.map((id) => view.tasks[id]).filter((task) => task.branchId === branchId);
}

export function branchStatus(view: RunView, branchId: string): BranchStatus {
  const tasks = tasksForBranch(view, branchId);
  if (tasks.length === 0) return "pending";
  if (tasks.some((task) => task.status === "running")) return view.finished ? "failed" : "running";
  if (tasks.every((task) => task.status === "failed")) return "failed";
  return "done";
}

/** Red alerts: the run failed or was interrupted. */
export function paneErrors(view: RunView): Notice[] {
  return view.notices.filter((notice) => notice.severity === "error");
}

/** Muted notes for the pane: warnings that belong to no task. */
export function paneWarnings(view: RunView): Notice[] {
  return view.notices.filter((notice) => notice.severity === "warning" && notice.taskId === null);
}

/** Muted notes shown under one task in the search tree. */
export function taskNotices(view: RunView, taskId: string): Notice[] {
  return view.notices.filter((notice) => notice.severity === "warning" && notice.taskId === taskId);
}

export function evidenceForBranch(view: RunView, branchId: string): Evidence[] {
  return view.evidence.filter((item) => item.branch_id === branchId);
}

export type TimelineItem =
  | { kind: "round"; round: number; tasks: TaskNode[] }
  | { kind: "verdict"; verdict: Verdict }
  | { kind: "critique"; report: CriticReport };

/**
 * The search tree top to bottom: each run of tasks between separators is one round block,
 * followed by the judge's verdict and, when it ran, the critic's report (docs/07 §3).
 */
export function timeline(view: RunView): TimelineItem[] {
  const items: TimelineItem[] = [];
  for (const entry of view.log) {
    if (entry.kind === "verdict") {
      items.push({ kind: "verdict", verdict: view.verdicts[entry.index] });
    } else if (entry.kind === "critique") {
      items.push({ kind: "critique", report: view.critiques[entry.index] });
    } else {
      const task = view.tasks[entry.taskId];
      const last = items[items.length - 1];
      if (last && last.kind === "round") {
        last.tasks.push(task);
        last.round = Math.max(last.round, task.round);
      } else {
        items.push({ kind: "round", round: task.round, tasks: [task] });
      }
    }
  }
  return items;
}

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import type { EventType, RunEvent } from "./events";
import {
  branchStatus,
  initialRun,
  reduceEvents,
  reduceRun,
  taskOrigin,
  timeline,
  toRunEvent,
} from "./reducer";

let seq = 0;
function ev(type: EventType, payload: unknown, id: number | null = seq++): RunEvent {
  return { type, seq: id, payload } as RunEvent;
}

const usage = (rounds: number, input: number) => ({
  searches: 3,
  fetches: 2,
  deep_reads: 1,
  agents: 2,
  rounds,
  input_tokens: input,
  output_tokens: 100,
  wall_seconds: 12.5,
});

const evidence = (id: string, branch: string) => ({
  evidence_id: id,
  doc_id: "doc_lcd",
  branch_id: branch,
  claim_text: "Insulin-treated beneficiaries qualify",
  evidence_text: "The beneficiary is insulin-treated",
  location: { section: "Coverage", paragraph_index: 4, char_start: 0, char_end: 34 },
  effective_date: "2024-10-01",
  relevance: 0.9,
  source_quality: 1,
  confidence: 0.8,
  stance: "supports",
});

const taskResult = (evidenceIds: string[]) => ({
  queries_issued: ["L33822 coverage"],
  documents_fetched: ["doc_lcd"],
  evidence_ids: evidenceIds,
  summary: "Found the LCD criteria.",
  unresolved: null,
  usage: usage(1, 1000),
});

const plan = {
  understanding: {
    normalized_question: "q",
    domain: "cgm",
    question_type: "eligibility",
    entities: [],
    time_sensitivity: "high",
    needs_primary_sources: true,
  },
  branches: [
    { branch_id: "b1", question: "Criteria?", rationale: "r", source_hint: "primary_policy", priority: 1, depends_on: [] },
    { branch_id: "b2", question: "Codes?", rationale: "r", source_hint: "coding_article", priority: 2, depends_on: [] },
  ],
  stop_criteria: "cited",
  budget: {},
  code: "ws.plan = SearchPlan(...)",
};

function primeRun(): RunEvent[] {
  seq = 0;
  return [
    ev("run.started", { run_id: "r1", question: "q", mode: "prime", depth: "deep", trace_url: "https://smith/x" }),
    ev("understanding", plan.understanding),
    ev("plan", plan),
    ev("task.started", { task_id: "b1-r0", branch_id: "b1", round: 0, instruction: "find criteria" }),
    ev("task.started", { task_id: "b2-r0", branch_id: "b2", round: 0, instruction: "find codes" }),
    ev("search", { task_id: "b1-r0", query: "L33822 coverage", n_results: 8, cached: false }),
    ev("fetch", { task_id: "b1-r0", doc_id: "doc_lcd", url: "https://cms.gov/lcd", title: "LCD L33822", tier: "primary_policy", effective_date: "2024-10-01" }),
    ev("evidence", evidence("ev1", "b1")),
    ev("task.done", { task_id: "b1-r0", result: taskResult(["ev1"]) }),
    ev("task.done", { task_id: "b2-r0", branch_id: "b2", evidence: 0, unresolved: "deadline passed" }),
    ev("usage", usage(1, 5000)),
    ev("verdict", { round: 1, sufficient: false, coverage: { b1: "resolved", b2: "unresolved" }, missing: ["codes"], new_tasks: [{}], reasoning: "codes missing" }),
    ev("task.started", { task_id: "b2-r1", branch_id: "b2", round: 1, instruction: "find codes again" }),
    ev("task.done", { task_id: "b2-r1", result: taskResult([]) }),
    ev("critique", { weak_claims: [], missing_interpretations: [], source_independence_issues: [], secondary_when_primary_exists: [], outdated_sources: [], contradictions: [], recommended_searches: [{}], completion_probability: 0.6, reasoning: "ok" }),
    ev("task.started", { task_id: "b1-r2-critic1", branch_id: "b1", round: 2, instruction: "check recency" }),
    ev("task.done", { task_id: "b1-r2-critic1", result: taskResult([]) }),
    ev("token", { text: "Covered 【1】" }),
    ev("token", { text: " when insulin-treated." }),
    ev("answer", { summary: "Covered.", body_markdown: "## Answer\nCovered [1].", claims: [], citations: [{ n: 1, evidence_id: "ev1", doc_id: "doc_lcd", url: "https://cms.gov/lcd", label: "LCD" }], effective_dates: [], contradictions: [], unknowns: [], confidence: 0.7 }),
    ev("usage", usage(3, 9000)),
    ev("run.finished", { status: "completed", langsmith_run_url: "https://smith/x", usage: usage(3, 9100) }),
  ];
}

describe("reduceRun", () => {
  it("rebuilds a prime run: plan code, task origins, statuses, answer and final totals", () => {
    const view = reduceEvents(primeRun());

    expect(view.status).toBe("completed");
    expect(view.finished).toBe(true);
    expect(view.planCode).toBe("ws.plan = SearchPlan(...)");
    expect(view.planCodeRecorded).toBe(true);
    expect(Object.values(view.tasks).map((task) => [task.taskId, task.origin, task.status])).toEqual([
      ["b1-r0", "plan", "done"],
      ["b2-r0", "plan", "failed"],
      ["b2-r1", "judge", "done"],
      ["b1-r2-critic1", "critic", "done"],
    ]);
    expect(view.tasks["b1-r0"].searches).toHaveLength(1);
    expect(view.tasks["b1-r0"].fetchDocIds).toEqual(["doc_lcd"]);
    expect(view.tasks["b2-r0"].unresolved).toBe("deadline passed");
    expect(view.evidence).toHaveLength(1);
    expect(view.answer?.body_markdown).toBe("## Answer\nCovered [1].");
    expect(view.streamText).toBe("");
    expect(view.usage?.input_tokens).toBe(9100); // run.finished carries the totals
    expect(branchStatus(view, "b1")).toBe("done");
  });

  it("keeps arrival order in the timeline: round, verdict, round, critique, round", () => {
    const kinds = timeline(reduceEvents(primeRun())).map((item) => item.kind);
    expect(kinds).toEqual(["round", "verdict", "round", "critique", "round"]);
  });

  it("applies each seq once, so replay followed by the live stream is idempotent", () => {
    const events = primeRun();
    const once = reduceEvents(events);
    const twice = reduceEvents(events, once);
    expect(twice).toEqual(once);
  });

  it("shows streamed tokens until the answer, and ignores tokens after it", () => {
    seq = 0;
    let view = reduceEvents([ev("token", { text: "Cov" }), ev("token", { text: "ered" })]);
    expect(view.streamText).toBe("Covered");
    view = reduceRun(view, ev("answer", { summary: "", body_markdown: "final", claims: [], citations: [], effective_dates: [], contradictions: [], unknowns: [], confidence: 0 }));
    view = reduceRun(view, ev("token", { text: " late" }));
    expect(view.answer?.body_markdown).toBe("final");
    expect(view.streamText).toBe("");
  });

  it("pairs the baseline's two search frames into one search with a result count", () => {
    seq = 0;
    const view = reduceEvents([
      ev("search", { task_id: null, query: "medicare cgm coverage", n_results: null, cached: false, tool: "tavily_search" }),
      ev("search", { task_id: null, query: "", n_results: 5, cached: false, tool: "tavily_search" }),
    ]);
    expect(view.baselineSearches).toEqual([{ query: "medicare cgm coverage", nResults: 5, tool: "tavily_search" }]);
  });

  it("marks the API's synthetic finish as interrupted, and a real failure as failed", () => {
    seq = 0;
    const interrupted = reduceEvents([
      ev("run.started", { run_id: "r", question: "q", mode: "prime", depth: "deep" }),
      ev("error", { message: "run interrupted: the process running it stopped before it finished", node: "api" }, null),
      ev("run.finished", { status: "failed", langsmith_run_url: null }, null),
    ]);
    expect(interrupted.status).toBe("interrupted");

    seq = 0;
    const failed = reduceEvents([
      ev("error", { message: "RuntimeError: boom", node: "run_prime" }),
      ev("run.finished", { status: "failed", langsmith_run_url: null }),
    ]);
    expect(failed.status).toBe("failed");
  });

  it("tells a run recorded before plan code apart from a fallback plan", () => {
    seq = 0;
    const withoutCode: Record<string, unknown> = { ...plan };
    delete withoutCode.code;
    expect(reduceRun(initialRun(), ev("plan", withoutCode)).planCodeRecorded).toBe(false);
    const fallback = reduceRun(initialRun(), ev("plan", { ...plan, code: null }));
    expect([fallback.planCodeRecorded, fallback.planCode]).toEqual([true, null]);
  });

  it("names task origins from the task id convention (docs/02 §2.3)", () => {
    expect(taskOrigin("b1-r0", 0)).toBe("plan");
    expect(taskOrigin("b1-r1-2", 1)).toBe("judge");
    expect(taskOrigin("b3-r2-critic1", 2)).toBe("critic");
  });
});

// A real recorded run, when this checkout has it (runs/ is not committed).
const REAL_RUN = resolve(__dirname, "../../../runs/01a09bb6-7412-7203-8fe8-1b44eb7a8497/events.jsonl");

describe.skipIf(!existsSync(REAL_RUN))("a recorded prime deep run", () => {
  it("replays to a finished run with its verdicts, critique, evidence and answer", () => {
    const lines = readFileSync(REAL_RUN, "utf-8").split("\n").filter((line) => line.trim());
    const events = lines
      .map((line, index) => {
        const record = JSON.parse(line);
        return toRunEvent({ type: record.type, seq: record.seq ?? index, payload: record.payload });
      })
      .filter((event): event is RunEvent => event !== null);
    const view = reduceEvents(events);

    expect(view.finished).toBe(true);
    expect(view.answer).not.toBeNull();
    expect(view.verdicts).toHaveLength(2);
    expect(view.critiques).toHaveLength(1);
    expect(view.evidence).toHaveLength(17);
    expect(timeline(view).filter((item) => item.kind === "verdict")).toHaveLength(2);
  });
});

"use client";

import { formatDate, formatPercent, plural, tierBadgeClass, tierLabel } from "@/lib/format";
import {
  branchIds,
  evidenceForBranch,
  tasksForBranch,
  timeline,
  type BranchStatus,
  type RunView,
  type TaskNode,
} from "@/lib/reducer";
import type { CriticReport, Verdict } from "@/lib/types";

const BRANCH_MARK: Record<BranchStatus, string> = {
  pending: "○ pending",
  running: "◐ running",
  done: "● done",
  failed: "✕ failed",
};

/**
 * The search tree (docs/07 §3): a nested list, not a graph. Round blocks in arrival order,
 * separated by the judge's verdict and, when it ran, the critic's report.
 */
export function SearchTree({ view }: { view: RunView }) {
  const items = timeline(view);
  const pending = branchIds(view).filter((id) => tasksForBranch(view, id).length === 0);

  if (!view.plan && items.length === 0) {
    return <p className="text-sm text-muted">{view.finished ? "No search plan." : "Planning…"}</p>;
  }

  return (
    <div className="rounded-md border border-line">
      <div className="border-b border-line px-3 py-1.5 text-xs font-medium text-muted uppercase">Search tree</div>
      <div className="divide-y divide-line">
        {items.map((item, index) =>
          item.kind === "round" ? (
            <RoundBlock key={`round-${index}`} view={view} tasks={item.tasks} />
          ) : item.kind === "verdict" ? (
            <VerdictSeparator key={`verdict-${index}`} verdict={item.verdict} />
          ) : (
            <CriticSeparator key={`critique-${index}`} report={item.report} />
          ),
        )}
        {pending.length > 0 && (
          <ul className="px-3 py-2 text-sm">
            {pending.map((id) => (
              <li key={id} className="flex gap-2 text-muted">
                <span className="font-mono">{id}</span>
                <span className="truncate">{branchQuestion(view, id)}</span>
                <span className="ml-auto whitespace-nowrap">{BRANCH_MARK.pending}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function branchQuestion(view: RunView, branchId: string): string {
  return view.plan?.branches.find((branch) => branch.branch_id === branchId)?.question ?? "";
}

function RoundBlock({ view, tasks }: { view: RunView; tasks: TaskNode[] }) {
  const order = branchIds(view);
  const byBranch = new Map<string, TaskNode[]>();
  for (const task of tasks) byBranch.set(task.branchId, [...(byBranch.get(task.branchId) ?? []), task]);
  const branches = [...byBranch.keys()].sort((a, b) => order.indexOf(a) - order.indexOf(b));

  return (
    <div className="space-y-1 px-3 py-2">
      {branches.map((branchId) => (
        <BranchNode key={branchId} view={view} branchId={branchId} tasks={byBranch.get(branchId) ?? []} />
      ))}
    </div>
  );
}

function statusOf(tasks: TaskNode[], finished: boolean): BranchStatus {
  if (tasks.some((task) => task.status === "running")) return finished ? "failed" : "running";
  if (tasks.every((task) => task.status === "failed")) return "failed";
  return "done";
}

function BranchNode({ view, branchId, tasks }: { view: RunView; branchId: string; tasks: TaskNode[] }) {
  const status = statusOf(tasks, view.finished);
  const evidenceCount = evidenceForBranch(view, branchId).length;
  const summary = tasks.map((task) => task.result?.summary).filter(Boolean).join(" ");
  return (
    <details className="group text-sm" open={status === "running"}>
      <summary className="flex cursor-pointer list-none items-center gap-2">
        <span className="text-muted group-open:rotate-90">▸</span>
        <span className="font-mono text-xs text-muted">{branchId}</span>
        <span className="min-w-0 flex-1 truncate">{branchQuestion(view, branchId) || tasks[0]?.instruction}</span>
        <span className="text-xs whitespace-nowrap text-muted">{plural(evidenceCount, "ev", "ev")}</span>
        <span
          className={`text-xs whitespace-nowrap ${
            status === "failed" ? "text-bad" : status === "running" ? "text-accent" : "text-muted"
          }`}
        >
          {BRANCH_MARK[status]}
        </span>
      </summary>
      <div className="mt-1 ml-5 space-y-1.5 border-l border-line pl-3">
        {summary && <p className="text-xs text-muted">{summary}</p>}
        {tasks.map((task) => (
          <TaskRow key={task.taskId} view={view} task={task} />
        ))}
      </div>
    </details>
  );
}

function TaskRow({ view, task }: { view: RunView; task: TaskNode }) {
  const evidence = task.result?.evidence_ids.length ?? 0;
  return (
    <div className="text-xs">
      <div className="flex items-center gap-2">
        <span className="font-mono text-muted">{task.taskId}</span>
        {task.origin !== "plan" && (
          <span
            className={`rounded border px-1 ${task.origin === "critic" ? "border-warn text-warn" : "border-line text-muted"}`}
          >
            {task.origin}
          </span>
        )}
        {task.status === "running" && !view.finished && <span className="text-accent">running</span>}
        {task.status === "failed" && <span className="text-bad">failed</span>}
      </div>
      <ul className="mt-0.5 space-y-0.5 text-muted">
        {task.searches.map((search, index) => (
          <li key={`s-${index}`}>
            ├ search <span className="text-foreground">&ldquo;{search.query}&rdquo;</span> {search.n_results ?? "?"}
            {search.cached && " · cached"}
          </li>
        ))}
        {task.fetchDocIds.map((docId) => {
          const fetch = view.fetches[docId];
          return (
            <li key={`f-${docId}`} className="flex flex-wrap items-center gap-1">
              ├ fetch <span className="text-foreground">{fetch?.title ?? docId}</span>
              {fetch && (
                <span className={`rounded px-1 text-[10px] ${tierBadgeClass(fetch.tier)}`}>{tierLabel(fetch.tier)}</span>
              )}
              {fetch?.effective_date && <span>effective {formatDate(fetch.effective_date)}</span>}
            </li>
          );
        })}
        {task.status !== "running" && <li>└ evidence ×{evidence}</li>}
        {task.unresolved && <li className="italic">unresolved: {task.unresolved}</li>}
      </ul>
    </div>
  );
}

function VerdictSeparator({ verdict }: { verdict: Verdict }) {
  return (
    <div className="bg-panel px-3 py-1.5 text-xs text-muted" title={verdict.reasoning}>
      ── round {verdict.round}: judge →{" "}
      <span className={verdict.sufficient ? "text-ok" : "text-warn"}>
        {verdict.sufficient ? "sufficient" : "insufficient"}
      </span>
      , {plural(verdict.new_tasks.length, "new task")}
      {verdict.missing.length > 0 && <span> · missing: {verdict.missing.join("; ")}</span>}
    </div>
  );
}

function CriticSeparator({ report }: { report: CriticReport }) {
  return (
    <div className="bg-panel px-3 py-1.5 text-xs text-muted" title={report.reasoning}>
      ── critic: completion {formatPercent(report.completion_probability)},{" "}
      {plural(report.recommended_searches.length, "recommended search", "recommended searches")}
    </div>
  );
}

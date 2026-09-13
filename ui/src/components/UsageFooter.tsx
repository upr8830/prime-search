import { formatSeconds, formatTokens, plural, totalTokens } from "@/lib/format";
import type { RunView } from "@/lib/reducer";
import type { RunRecord, Usage } from "@/lib/types";

/**
 * Cost and latency for one pane (docs/07 §3, §9). Once the run has ended, the saved
 * record's totals win over the stream's; runs recorded before the final `usage` event
 * existed only have them there.
 */
export function UsageFooter({
  mode,
  view,
  record,
}: {
  mode: "baseline" | "prime";
  view: RunView;
  record: RunRecord | null;
}) {
  const usage: Usage | null = (record && record.status !== "running" ? record.usage : view.usage) ?? null;
  const traceUrl = view.traceUrl ?? record?.langsmith_run_url ?? null;

  const parts = usage
    ? mode === "prime"
      ? [
          plural(usage.searches, "search", "searches"),
          plural(usage.fetches, "fetch", "fetches"),
          plural(usage.agents, "agent"),
          plural(usage.rounds, "round"),
          formatSeconds(usage.wall_seconds),
          `${formatTokens(totalTokens(usage))} tok`,
        ]
      : [plural(usage.searches, "search", "searches"), formatSeconds(usage.wall_seconds), `${formatTokens(totalTokens(usage))} tok`]
    : [];

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
      <span>{parts.length > 0 ? parts.join(" · ") : view.finished ? "no usage recorded" : "…"}</span>
      {view.status === "budget_exhausted" && (
        <span className="rounded-full border border-warn bg-warn-soft px-2 py-0.5 text-warn">budget hit</span>
      )}
      {traceUrl ? (
        <a href={traceUrl} target="_blank" rel="noreferrer" className="text-accent underline">
          LangSmith ↗
        </a>
      ) : (
        view.runId && view.status !== "connecting" && <span>tracing off</span>
      )}
    </div>
  );
}

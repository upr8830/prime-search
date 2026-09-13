import type { RunView } from "@/lib/reducer";

import { StatusBadge } from "./StatusBadge";

/** Pane title, what the agent is, and what PRIME understood the question as (docs/07 §3). */
export function PaneHeader({ view, mode }: { view: RunView; mode: "baseline" | "prime" }) {
  const prime = mode === "prime";
  const budget = view.plan?.budget;
  return (
    <div className="border-b border-line pb-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className={`text-sm font-semibold tracking-wide uppercase ${prime ? "text-accent" : "text-plain"}`}>
          {prime ? "PRIME Search" : "Simple search (starter)"}
        </h2>
        <StatusBadge status={view.status} />
      </div>
      <p className="mt-1 text-xs text-muted">
        {prime
          ? `root · sub-agents · ${view.depth ?? "deep"}${
              budget ? ` · budget ${budget.max_searches} searches, ${Math.round(budget.max_tokens / 1000)}k tokens` : ""
            }`
          : "starter model · 1 tool (TavilySearch)"}
      </p>
      {prime && view.understanding && (
        <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
          {[
            view.understanding.domain,
            view.understanding.question_type.replaceAll("_", " "),
            `${view.understanding.time_sensitivity} time sensitivity`,
          ].map((chip) => (
            <span key={chip} className="rounded bg-accent-soft px-1.5 py-0.5 text-accent">
              {chip}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

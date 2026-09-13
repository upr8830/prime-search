"use client";

import type { Connection } from "@/lib/useRunEvents";
import type { RunView } from "@/lib/reducer";

import { PaneHeader } from "./PaneHeader";

/**
 * One side of the compare view (docs/07 §3). The baseline pane uses the same pieces as
 * the prime pane, minus the search tree.
 */
export function RunPane({
  mode,
  view,
  connection,
}: {
  mode: "baseline" | "prime";
  view: RunView;
  connection: Connection;
}) {
  return (
    <section className="flex min-w-0 flex-col gap-3 rounded-lg border border-line p-4">
      <PaneHeader view={view} mode={mode} />

      {connection === "reconnecting" && (
        <p className="text-xs text-muted">Stream dropped, reconnecting and replaying…</p>
      )}
      {connection === "gave_up" && (
        <p className="text-xs text-bad">Lost the event stream. Reload the page to replay this run.</p>
      )}
      {view.errors.map((error, index) => (
        <p key={index} role="alert" className="rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
          <span className="font-medium">{error.node}:</span> {error.message}
        </p>
      ))}

      {mode === "baseline" && view.baselineSearches.length > 0 && (
        <ul className="space-y-1 text-sm">
          {view.baselineSearches.map((search, index) => (
            <li key={index} className="text-muted">
              ▸ search: <span className="text-foreground">&ldquo;{search.query}&rdquo;</span>
              {search.nResults !== null && <span> · {search.nResults} results</span>}
            </li>
          ))}
        </ul>
      )}

      <div className="text-sm leading-relaxed">
        {view.answer ? (
          <pre className="font-sans whitespace-pre-wrap">{view.answer.body_markdown}</pre>
        ) : view.streamText ? (
          <pre className="font-sans whitespace-pre-wrap text-muted">{view.streamText}</pre>
        ) : (
          <p className="text-muted">{view.finished ? "No answer." : "Waiting for the answer…"}</p>
        )}
      </div>
    </section>
  );
}

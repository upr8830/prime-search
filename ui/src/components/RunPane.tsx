"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api";
import type { RunView } from "@/lib/reducer";
import type { RunRecord } from "@/lib/types";
import type { Connection } from "@/lib/useRunEvents";

import { AnswerView } from "./AnswerView";
import { ClaimList } from "./ClaimList";
import { CriticPanel } from "./CriticPanel";
import { EvidenceTable } from "./EvidenceTable";
import { FeedbackControls } from "./FeedbackControls";
import { PaneHeader } from "./PaneHeader";
import { RunTabs, type Tab } from "./RunTabs";
import { SearchTree } from "./SearchTree";
import { UsageFooter } from "./UsageFooter";

/**
 * One side of the compare view (docs/07 §3), also the body of the run detail page (§4).
 * The baseline pane uses the same pieces as the prime pane, minus the tree and tabs.
 * Key it by run id, so flagged claims and sent feedback do not carry over to a new run.
 */
export function RunPane({
  mode,
  view,
  connection,
  record,
  extraTabs = [],
}: {
  mode: "baseline" | "prime";
  view: RunView;
  connection: Connection;
  /** Supplied by the run detail page; the compare view fetches it once the run ends. */
  record?: RunRecord | null;
  extraTabs?: Tab[];
}) {
  const runId = view.runId;
  const fetched = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.run(runId as string),
    enabled: record === undefined && runId !== null && view.finished,
    retry: false,
  });
  const saved = record === undefined ? (fetched.data ?? null) : record;
  const [flagged, setFlagged] = useState<string[]>([]);

  const claims = view.answer?.claims ?? saved?.answer?.claims ?? [];
  const toggleFlag = (claimId: string) =>
    setFlagged((current) => (current.includes(claimId) ? current.filter((id) => id !== claimId) : [...current, claimId]));

  const primeTabs: Tab[] = [
    { id: "answer", label: "Answer", content: <AnswerView view={view} mode={mode} /> },
    { id: "evidence", label: `Evidence ${view.evidence.length}`, content: <EvidenceTable view={view} /> },
    {
      id: "claims",
      label: `Claims ${claims.length}`,
      content: <ClaimList view={view} claims={claims} flagged={flagged} onToggleFlag={toggleFlag} />,
    },
    {
      id: "critic",
      label: `Critic${view.critiques.length ? ` ${view.critiques.length}` : ""}`,
      content: <CriticPanel critiques={view.critiques} finished={view.finished} />,
    },
    ...extraTabs,
  ];

  return (
    <section className={`flex min-w-0 flex-col gap-3 rounded-lg border p-4 ${mode === "prime" ? "border-accent/40" : "border-line"}`}>
      <PaneHeader view={view} mode={mode} />

      {connection === "reconnecting" && <p className="text-xs text-muted">Stream dropped: reconnecting and replaying…</p>}
      {connection === "gave_up" && <p className="text-xs text-bad">Lost the event stream. Reload the page to replay this run.</p>}
      {view.errors.map((error, index) => (
        <p key={index} role="alert" className="rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
          <span className="font-medium">{error.node}:</span> {error.message}
        </p>
      ))}

      {mode === "prime" ? (
        <>
          <SearchTree view={view} />
          <RunTabs tabs={primeTabs} />
        </>
      ) : (
        <>
          {view.baselineSearches.length > 0 && (
            <ul className="space-y-1 text-sm">
              {view.baselineSearches.map((search, index) => (
                <li key={index} className="text-muted">
                  ▸ search: <span className="text-foreground">&ldquo;{search.query}&rdquo;</span>
                  {search.nResults !== null && <span> · {search.nResults} results</span>}
                </li>
              ))}
            </ul>
          )}
          {extraTabs.length > 0 ? (
            <RunTabs tabs={[{ id: "answer", label: "Answer", content: <AnswerView view={view} mode={mode} /> }, ...extraTabs]} />
          ) : (
            <AnswerView view={view} mode={mode} />
          )}
        </>
      )}

      <div className="mt-auto flex flex-col gap-2 border-t border-line pt-3">
        <UsageFooter mode={mode} view={view} record={saved} />
        <FeedbackControls runId={runId} enabled={view.finished} flaggedClaims={mode === "prime" ? flagged : []} />
      </div>
    </section>
  );
}

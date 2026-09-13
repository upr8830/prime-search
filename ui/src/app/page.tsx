"use client";

import { useState } from "react";

import { QuestionBar, type AskRequest } from "@/components/QuestionBar";
import { RunPane } from "@/components/RunPane";
import { ApiError, api } from "@/lib/api";
import { postUiEvent } from "@/lib/uiEvents";
import { useRunEvents } from "@/lib/useRunEvents";

type RunIds = { baseline: string | null; prime: string | null };

/** Compare view (docs/07 §3): one question, the starter and PRIME side by side. */
export default function ComparePage() {
  const [runIds, setRunIds] = useState<RunIds>({ baseline: null, prime: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hideBaseline, setHideBaseline] = useState(false);

  const baseline = useRunEvents(runIds.baseline);
  const prime = useRunEvents(runIds.prime);

  const ask = async ({ question, depth, questionId }: AskRequest) => {
    setBusy(true);
    setError(null);
    if (runIds.prime) postUiEvent("ui.rerun", { question, previous: runIds }, runIds.prime);
    const body = { question, depth, question_id: questionId, prompt_set: "base" as const };
    try {
      // Both runs start at once and run concurrently (docs/07 §3).
      const [baselineRun, primeRun] = await Promise.all([
        api.startRun({ ...body, mode: "baseline" }),
        api.startRun({ ...body, mode: "prime" }),
      ]);
      setRunIds({ baseline: baselineRun.run_id, prime: primeRun.run_id });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  };

  const toggleBaseline = () => {
    const next = !hideBaseline;
    setHideBaseline(next);
    postUiEvent("ui.compare_toggled", { baseline_hidden: next }, runIds.prime);
  };

  const started = runIds.baseline !== null || runIds.prime !== null;

  return (
    <div className="flex flex-col gap-4">
      <QuestionBar onAsk={ask} busy={busy} error={error} />

      {started ? (
        <>
          <div className="flex justify-end">
            <button type="button" onClick={toggleBaseline} className="text-xs text-muted underline">
              {hideBaseline ? "Show the starter pane" : "Hide the starter pane"}
            </button>
          </div>
          <div className={`grid gap-4 ${hideBaseline ? "grid-cols-1" : "lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"}`}>
            {/* Hidden, not unmounted: unmounting would unlock feedback already sent (docs/07 §3). */}
            <div className={hideBaseline ? "hidden" : "contents"}>
              <RunPane key={runIds.baseline ?? "baseline"} mode="baseline" view={baseline.view} connection={baseline.connection} />
            </div>
            <RunPane key={runIds.prime ?? "prime"} mode="prime" view={prime.view} connection={prime.connection} />
          </div>
        </>
      ) : (
        <p className="text-sm text-muted">
          Pick a SearchBench preset or type a policy question, then Ask: the starter agent and PRIME Search
          run the same question side by side.
        </p>
      )}
    </div>
  );
}

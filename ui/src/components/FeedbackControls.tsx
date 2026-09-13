"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, api } from "@/lib/api";

type Thumbs = "up" | "down";

/**
 * Thumbs and comment (docs/07 §3, docs/06 §3). Enabled once the run has finished, because
 * `POST /feedback` needs the saved record. After sending, the buttons lock with a check
 * and say whether LangSmith has it or it was only saved locally.
 */
export function FeedbackControls({
  runId,
  enabled,
  flaggedClaims = [],
}: {
  runId: string | null;
  enabled: boolean;
  flaggedClaims?: string[];
}) {
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState<{ thumbs: Thumbs; langsmith: boolean } | null>(null);

  const mutation = useMutation({
    mutationFn: (thumbs: Thumbs) =>
      api.feedback({
        run_id: runId as string,
        thumbs,
        comment: comment.trim() || null,
        claim_ids_flagged: flaggedClaims,
      }),
    onSuccess: (ok, thumbs) => setSent({ thumbs, langsmith: ok.langsmith === true }),
  });

  const locked = !enabled || !runId || sent !== null || mutation.isPending;
  const button = (thumbs: Thumbs, label: string, glyph: string) => (
    <button
      type="button"
      aria-label={label}
      disabled={locked}
      onClick={() => mutation.mutate(thumbs)}
      className={`rounded-md border px-2 py-1 text-sm disabled:cursor-not-allowed ${
        sent?.thumbs === thumbs ? "border-accent bg-accent-soft" : "border-line disabled:opacity-40"
      }`}
    >
      {glyph}
      {sent?.thumbs === thumbs && " ✓"}
    </button>
  );

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {button("up", "Thumbs up", "👍")}
      {button("down", "Thumbs down", "👎")}
      <input
        value={comment}
        onChange={(event) => setComment(event.target.value)}
        disabled={locked}
        placeholder={enabled ? "comment (optional)" : "feedback opens when the run finishes"}
        className="min-w-0 flex-1 rounded-md border border-line bg-background px-2 py-1 disabled:opacity-60"
      />
      {flaggedClaims.length > 0 && !sent && <span className="text-muted">flagging {flaggedClaims.length} claim(s)</span>}
      {sent && <span className="text-muted">{sent.langsmith ? "sent · LangSmith ✓" : "saved locally (not in LangSmith)"}</span>}
      {mutation.isError && (
        <span role="alert" className="text-bad">
          {mutation.error instanceof ApiError ? mutation.error.message : String(mutation.error)}
        </span>
      )}
    </div>
  );
}

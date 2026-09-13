"use client";

import { CLAIM_STATUS_CLASS, formatDate, formatPercent } from "@/lib/format";
import type { RunView } from "@/lib/reducer";
import type { Claim } from "@/lib/types";
import { postUiEvent } from "@/lib/uiEvents";

/**
 * Claims tab (docs/07 §3): status badges with their word, both sides of a contested claim,
 * and a flag that joins the pane's feedback as `claim_ids_flagged`.
 */
export function ClaimList({
  view,
  claims,
  flagged,
  onToggleFlag,
}: {
  view: RunView;
  claims: Claim[];
  flagged: string[];
  onToggleFlag: (claimId: string) => void;
}) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted">{view.finished ? "No claims in this answer." : "Claims arrive with the answer."}</p>;
  }

  const passages = (ids: string[]) =>
    ids
      .map((id) => view.evidenceById[id])
      .filter(Boolean)
      .map((item) => (
        <li key={item.evidence_id} className="border-l-2 border-line pl-2 italic">
          &ldquo;{item.evidence_text}&rdquo;
        </li>
      ));

  return (
    <ul className="flex flex-col gap-3">
      {claims.map((claim) => {
        const isFlagged = flagged.includes(claim.claim_id);
        return (
          <li key={claim.claim_id} className="rounded-md border border-line p-3 text-sm">
            <div className="flex items-start gap-2">
              <span className={`rounded border px-1.5 text-xs whitespace-nowrap ${CLAIM_STATUS_CLASS[claim.status]}`}>{claim.status}</span>
              <p className="min-w-0 flex-1">{claim.text}</p>
              <label className="flex items-center gap-1 text-xs whitespace-nowrap text-muted">
                <input
                  type="checkbox"
                  checked={isFlagged}
                  onChange={() => {
                    onToggleFlag(claim.claim_id);
                    postUiEvent("ui.claim_flagged", { claim_id: claim.claim_id, flagged: !isFlagged }, view.runId);
                  }}
                />
                flag
              </label>
            </div>
            <p className="mt-1 text-xs text-muted">
              {claim.branch_id} · confidence {formatPercent(claim.confidence)}
              {claim.governing_date && ` · governing ${formatDate(claim.governing_date)}`} · {claim.supported_by.length} supporting,{" "}
              {claim.contradicted_by.length} contradicting
            </p>
            {claim.status === "contested" && (
              <div className="mt-2 grid gap-3 text-xs md:grid-cols-2">
                <div>
                  <p className="font-medium text-ok">Supports</p>
                  <ul className="mt-1 space-y-1">{passages(claim.supported_by)}</ul>
                </div>
                <div>
                  <p className="font-medium text-bad">Contradicts</p>
                  <ul className="mt-1 space-y-1">{passages(claim.contradicted_by)}</ul>
                </div>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

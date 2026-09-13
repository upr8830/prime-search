"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { formatDate, formatPercent, tierBadgeClass, tierLabel } from "@/lib/format";
import { branchIds, type RunView } from "@/lib/reducer";
import { postUiEvent } from "@/lib/uiEvents";

import { documentHref } from "./CitationRef";

/** Evidence tab (docs/07 §3): one row per verbatim passage; a row opens its paragraph. */
export function EvidenceTable({ view }: { view: RunView }) {
  const router = useRouter();
  const [branch, setBranch] = useState("all");
  const rows = view.evidence.filter((item) => branch === "all" || item.branch_id === branch);

  if (view.evidence.length === 0) {
    return <p className="text-sm text-muted">{view.finished ? "No evidence was extracted." : "No evidence yet."}</p>;
  }

  const open = (evidenceId: string, docId: string, paragraph: number) => {
    if (!view.runId) return;
    postUiEvent("ui.evidence_opened", { from: "evidence_table", evidence_id: evidenceId, doc_id: docId }, view.runId);
    router.push(documentHref(view.runId, docId, paragraph));
  };

  return (
    <div className="flex flex-col gap-2">
      <label className="flex items-center gap-2 text-xs text-muted">
        Branch
        <select value={branch} onChange={(event) => setBranch(event.target.value)} className="rounded border border-line bg-background px-1 py-0.5">
          <option value="all">all ({view.evidence.length})</option>
          {branchIds(view).map((id) => (
            <option key={id} value={id}>
              {id} ({view.evidence.filter((item) => item.branch_id === id).length})
            </option>
          ))}
        </select>
      </label>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="py-1 pr-2 font-medium">Claim</th>
              <th className="py-1 pr-2 font-medium">Stance</th>
              <th className="py-1 pr-2 font-medium">Tier</th>
              <th className="py-1 pr-2 font-medium">Date</th>
              <th className="py-1 pr-2 font-medium">Document</th>
              <th className="py-1 font-medium">Conf.</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => {
              const fetch = view.fetches[item.doc_id];
              return (
                <tr
                  key={item.evidence_id}
                  onClick={() => open(item.evidence_id, item.doc_id, item.location.paragraph_index)}
                  className="cursor-pointer border-b border-line align-top hover:bg-panel"
                  title={item.evidence_text}
                >
                  <td className="py-1.5 pr-2">
                    <span className="font-mono text-muted">{item.branch_id}</span> {item.claim_text}
                  </td>
                  <td className={`py-1.5 pr-2 ${item.stance === "contradicts" ? "text-bad" : item.stance === "supports" ? "text-ok" : "text-muted"}`}>
                    {item.stance}
                  </td>
                  <td className="py-1.5 pr-2">
                    <span className={`rounded px-1 whitespace-nowrap ${tierBadgeClass(fetch?.tier)}`}>{tierLabel(fetch?.tier)}</span>
                  </td>
                  <td className="py-1.5 pr-2 whitespace-nowrap">{formatDate(item.effective_date ?? fetch?.effective_date)}</td>
                  <td className="py-1.5 pr-2">
                    {view.runId ? (
                      <Link
                        href={documentHref(view.runId, item.doc_id, item.location.paragraph_index)}
                        onClick={(event) => event.stopPropagation()}
                        className="text-accent underline"
                      >
                        {fetch?.title ?? item.doc_id}
                      </Link>
                    ) : (
                      (fetch?.title ?? item.doc_id)
                    )}
                  </td>
                  <td className="py-1.5">{formatPercent(item.confidence)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

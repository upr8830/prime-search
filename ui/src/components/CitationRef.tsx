"use client";

import Link from "next/link";

import type { FetchPayload } from "@/lib/events";
import { formatDate, formatPercent, tierBadgeClass, tierLabel } from "@/lib/format";
import type { Citation, Evidence } from "@/lib/types";
import { postUiEvent } from "@/lib/uiEvents";

export function documentHref(runId: string, docId: string, paragraph?: number | null): string {
  const base = `/docs/${encodeURIComponent(runId)}/${encodeURIComponent(docId)}`;
  return paragraph === null || paragraph === undefined ? base : `${base}?p=${paragraph}`;
}

/**
 * `[n]` in a PRIME answer: a hover (or focus) card with the evidence behind it, and a link
 * to the paragraph in the document view (docs/07 §3). A number with no citation stays text.
 */
export function CitationRef({
  n,
  runId,
  citation,
  evidence,
  fetch,
}: {
  n: number;
  runId: string | null;
  citation: Citation | undefined;
  evidence: Evidence | undefined;
  fetch: FetchPayload | undefined;
}) {
  if (!citation || !runId) return <span>[{n}]</span>;

  const paragraph = evidence?.location.paragraph_index;
  const href = documentHref(runId, citation.doc_id, paragraph);

  return (
    <span className="group relative inline-block align-baseline">
      <Link
        href={href}
        onClick={() =>
          postUiEvent("ui.evidence_opened", { from: "citation", n, evidence_id: citation.evidence_id, doc_id: citation.doc_id }, runId)
        }
        className="rounded px-0.5 text-xs font-medium text-accent hover:bg-accent-soft focus:bg-accent-soft focus:outline-none"
        aria-describedby={`cite-${runId}-${n}`}
      >
        [{n}]
      </Link>
      <span
        id={`cite-${runId}-${n}`}
        role="tooltip"
        className="invisible absolute bottom-full left-1/2 z-20 mb-1 w-80 -translate-x-1/2 rounded-md border border-line bg-background p-3 text-left text-xs leading-snug font-normal text-foreground shadow-lg group-focus-within:visible group-hover:visible"
      >
        <span className="mb-1 flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{fetch?.title ?? citation.label}</span>
          {fetch && <span className={`rounded px-1 text-[10px] ${tierBadgeClass(fetch.tier)}`}>{tierLabel(fetch.tier)}</span>}
        </span>
        {evidence ? (
          <>
            <span className="block text-muted">
              {evidence.stance} · confidence {formatPercent(evidence.confidence)} · effective{" "}
              {formatDate(evidence.effective_date ?? fetch?.effective_date)}
            </span>
            <span className="mt-1.5 block border-l-2 border-accent pl-2 italic">&ldquo;{evidence.evidence_text}&rdquo;</span>
          </>
        ) : (
          <span className="block text-muted">{citation.label}</span>
        )}
        <span className="mt-1.5 block text-accent">Open in document →</span>
      </span>
    </span>
  );
}

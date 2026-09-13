"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { formatDate, formatPercent, tierBadgeClass, tierLabel } from "@/lib/format";

import { documentHref } from "./CitationRef";

const PAGE = 200; // docs/07 §9: "document view paginates paragraphs at 200"

/**
 * `/docs/[runId]/[docId]` (docs/07 §6): the fetched text as indexed paragraphs, `?p=`
 * scrolled to and highlighted, and the evidence drawn from this document alongside.
 */
export function DocumentView({ runId, docId, focus }: { runId: string; docId: string; focus: number | null }) {
  const router = useRouter();
  const [offset, setOffset] = useState(focus !== null ? Math.floor(focus / PAGE) * PAGE : 0);

  useEffect(() => {
    if (focus !== null) setOffset(Math.floor(focus / PAGE) * PAGE);
  }, [focus]);

  const query = useQuery({
    queryKey: ["doc", runId, docId, offset],
    queryFn: () => api.document(runId, docId, offset, PAGE),
    retry: false,
  });

  useEffect(() => {
    if (focus === null || !query.data) return;
    document.getElementById(`p-${focus}`)?.scrollIntoView({ block: "center" });
  }, [focus, query.data]);

  if (query.isLoading) return <p className="text-sm text-muted">Loading document…</p>;
  if (query.isError) {
    const message = query.error instanceof ApiError ? query.error.message : String(query.error);
    return (
      <p role="alert" className="rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm text-bad">
        {message}
      </p>
    );
  }
  const view = query.data;
  if (!view) return null;
  const { document: doc } = view;
  const last = Math.min(view.offset + view.paragraphs.length, view.total);

  return (
    <div className="flex flex-col gap-4">
      <Link href={`/runs/${encodeURIComponent(runId)}`} className="text-xs text-muted underline">
        ← back to the run
      </Link>

      <header className="flex flex-col gap-1 border-b border-line pb-3">
        <h1 className="text-lg font-semibold">{doc.title}</h1>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className={`rounded px-1.5 ${tierBadgeClass(doc.source_tier)}`}>{tierLabel(doc.source_tier)}</span>
          {doc.publisher && <span>{doc.publisher}</span>}
          {doc.doc_type && <span>{doc.doc_type}</span>}
          {doc.document_id_external && <span className="font-mono">{doc.document_id_external}</span>}
          <span>effective {formatDate(doc.effective_date)}</span>
          <span>revised {formatDate(doc.revision_date)}</span>
          <span>fetched via {doc.fetch_method}</span>
        </div>
        <a href={doc.url} target="_blank" rel="noreferrer" className="truncate text-xs text-accent underline">
          {doc.url}
        </a>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-2">
          {view.text_error ? (
            <p className="rounded-md border border-warn bg-warn-soft px-3 py-2 text-sm text-warn">{view.text_error}</p>
          ) : (
            <>
              <ol className="flex flex-col gap-2 text-sm leading-relaxed">
                {view.paragraphs.map((paragraph) => (
                  <li
                    key={paragraph.index}
                    id={`p-${paragraph.index}`}
                    className={`flex gap-3 rounded px-2 py-1 ${
                      paragraph.index === focus ? "border border-warn bg-warn-soft" : ""
                    } ${paragraph.boilerplate ? "text-muted" : ""}`}
                  >
                    <span className="w-10 shrink-0 text-right font-mono text-xs text-muted">{paragraph.index}</span>
                    <span className="min-w-0">
                      {paragraph.section && <span className="mb-0.5 block text-xs text-muted">§ {paragraph.section}</span>}
                      {paragraph.text}
                    </span>
                  </li>
                ))}
              </ol>
              {view.total > PAGE && (
                <div className="flex items-center gap-3 text-xs text-muted">
                  <button
                    type="button"
                    disabled={view.offset === 0}
                    onClick={() => setOffset(Math.max(0, view.offset - PAGE))}
                    className="rounded border border-line px-2 py-1 disabled:opacity-40"
                  >
                    ← previous
                  </button>
                  <span>
                    paragraphs {view.offset}–{last - 1} of {view.total}
                  </span>
                  <button
                    type="button"
                    disabled={last >= view.total}
                    onClick={() => setOffset(view.offset + PAGE)}
                    className="rounded border border-line px-2 py-1 disabled:opacity-40"
                  >
                    next →
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <aside className="flex flex-col gap-2">
          <h2 className="text-xs font-medium text-muted uppercase">Evidence from this document ({view.evidence.length})</h2>
          {view.evidence.length === 0 && <p className="text-xs text-muted">None.</p>}
          {view.evidence.map((item) => (
            <button
              key={item.evidence_id}
              type="button"
              onClick={() => router.replace(documentHref(runId, docId, item.location.paragraph_index))}
              className={`rounded-md border p-2 text-left text-xs ${
                item.location.paragraph_index === focus ? "border-warn bg-warn-soft" : "border-line hover:bg-panel"
              }`}
            >
              <span className="block font-medium">{item.claim_text}</span>
              <span className="mt-0.5 block text-muted">
                ¶ {item.location.paragraph_index} · {item.stance} · {formatPercent(item.confidence)} · {item.branch_id}
              </span>
            </button>
          ))}
        </aside>
      </div>
    </div>
  );
}

"use client";

import type { ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { normalizeSources, remarkCitations } from "@/lib/citations";
import type { RunView } from "@/lib/reducer";

import { CitationRef } from "./CitationRef";

type SupProps = ComponentProps<"sup"> & { "data-cite"?: string | number };

/**
 * The answer panel (docs/07 §3). Streamed tokens are shown as provisional text until the
 * `answer` event arrives: synthesis rewrites citations and injects sections, so the final
 * `body_markdown` replaces what streamed rather than extending it.
 */
export function AnswerView({ view, mode }: { view: RunView; mode: "baseline" | "prime" }) {
  const answer = view.answer;

  if (!answer) {
    if (view.streamText) {
      return (
        <div>
          <p className="mb-1 text-xs text-muted">streaming…</p>
          <pre className="font-sans text-sm leading-relaxed whitespace-pre-wrap text-muted">{view.streamText}</pre>
        </div>
      );
    }
    return <p className="text-sm text-muted">{view.finished ? "No answer." : "Waiting for the answer…"}</p>;
  }

  const citationsByN = new Map(answer.citations.map((citation) => [citation.n, citation]));

  const components = {
    sup: ({ children, ...props }: SupProps) => {
      const raw = props["data-cite"];
      if (raw === undefined) return <sup {...props}>{children}</sup>;
      const n = Number(raw);
      const citation = citationsByN.get(n);
      return (
        <CitationRef
          n={n}
          runId={view.runId}
          citation={citation}
          evidence={citation ? view.evidenceById[citation.evidence_id] : undefined}
          fetch={citation ? view.fetches[citation.doc_id] : undefined}
        />
      );
    },
    a: (props: ComponentProps<"a">) => <a {...props} target="_blank" rel="noreferrer" className="text-accent underline" />,
  };

  return (
    <div className="flex flex-col gap-3">
      {answer.scope_warning && (
        <p role="note" className="rounded-md border border-warn bg-warn-soft px-3 py-2 text-sm text-warn">
          <span className="font-medium">Scope:</span> {answer.scope_warning}
        </p>
      )}
      <div className="answer-markdown text-sm leading-relaxed">
        <ReactMarkdown
          remarkPlugins={mode === "prime" ? [remarkGfm, remarkCitations] : [remarkGfm]}
          components={components}
        >
          {mode === "prime" ? normalizeSources(answer.body_markdown) : answer.body_markdown}
        </ReactMarkdown>
      </div>
      {mode === "baseline" && answer.citations.length > 0 && (
        <div className="text-xs text-muted">
          <p className="font-medium">Links in the answer</p>
          <ul className="mt-1 space-y-0.5">
            {answer.citations.map((citation) => (
              <li key={citation.n} className="truncate">
                <a href={citation.url} target="_blank" rel="noreferrer" className="underline">
                  {citation.url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

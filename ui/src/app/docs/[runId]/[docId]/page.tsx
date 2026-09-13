"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { DocumentView } from "@/components/DocumentView";

function DocumentPage() {
  const params = useParams<{ runId: string; docId: string }>();
  const search = useSearchParams();
  const raw = search.get("p");
  const focus = raw !== null && /^\d+$/.test(raw) ? Number(raw) : null;
  return <DocumentView runId={params.runId} docId={params.docId} focus={focus} />;
}

export default function Page() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading document…</p>}>
      <DocumentPage />
    </Suspense>
  );
}

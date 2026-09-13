"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { PlanTab } from "@/components/PlanTab";
import { RunPane } from "@/components/RunPane";
import { ApiError } from "@/lib/api";
import { useRun } from "@/lib/useRun";

/** Run detail (docs/07 §4): a past run replayed from its events, plus the Plan tab. */
export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { view, record, connection, loading, error } = useRun(id);

  if (loading) return <p className="text-sm text-muted">Loading run…</p>;
  if (error) {
    const message = error instanceof ApiError && error.status === 404 ? `No run ${id}.` : String(error);
    return (
      <div className="flex flex-col gap-2">
        <p role="alert" className="text-sm text-bad">
          {message}
        </p>
        <Link href="/runs" className="text-xs text-muted underline">
          ← all runs
        </Link>
      </div>
    );
  }

  const mode = view.mode ?? record?.request.mode ?? "prime";
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <Link href="/runs" className="text-xs text-muted underline">
          ← all runs
        </Link>
        <h1 className="text-lg font-semibold">{view.question ?? record?.request.question ?? id}</h1>
        <p className="font-mono text-xs text-muted">{id}</p>
      </div>
      <RunPane
        key={id}
        mode={mode}
        view={view}
        connection={connection}
        record={record}
        extraTabs={mode === "prime" ? [{ id: "plan", label: "Plan", content: <PlanTab view={view} /> }] : []}
      />
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";

import { BenchTable } from "@/components/BenchTable";
import { api } from "@/lib/api";
import { isMissingReport } from "@/lib/types";

/** Latest bench summary (docs/07 §5), from `GET /bench/summary`. */
export default function BenchPage() {
  const summary = useQuery({ queryKey: ["bench-summary"], queryFn: api.benchSummary });

  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-lg font-semibold">Bench</h1>
      {summary.isLoading && <p className="text-sm text-muted">Loading the latest report…</p>}
      {summary.isError && (
        <p role="alert" className="text-sm text-bad">
          Could not load the report: {String(summary.error)}
        </p>
      )}
      {summary.data && isMissingReport(summary.data) && (
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-muted">No bench report yet{summary.data.error ? ` (${summary.data.error})` : ""}. Run the bench, then build the report:</p>
          <pre className="rounded-md border border-line bg-panel p-3 font-mono text-xs">
            {`make bench ARGS="--mode baseline --split dev"
make bench ARGS="--mode prime --split dev --prompt-set base"
uv run python -m eval.report --split dev`}
          </pre>
        </div>
      )}
      {summary.data && !isMissingReport(summary.data) && <BenchTable report={summary.data} />}
    </div>
  );
}

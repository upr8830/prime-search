"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { LIMIT_NOTE_GENERIC, formatSeconds, formatTokens, totalTokens } from "@/lib/format";

/** Run history (docs/07 §2), newest first, from `GET /runs`. */
export default function RunsPage() {
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: api.runs,
    refetchInterval: (query) => (query.state.data?.some((run) => run.status === "running") ? 5000 : false),
  });

  if (runs.isLoading) return <p className="text-sm text-muted">Loading runs…</p>;
  if (runs.isError) {
    return (
      <p role="alert" className="text-sm text-bad">
        Could not list runs: {String(runs.error)}
      </p>
    );
  }
  const rows = runs.data ?? [];

  return (
    <div className="flex flex-col gap-3">
      <h1 className="text-lg font-semibold">Runs</h1>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">No runs yet. Ask a question on the compare view.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="py-1.5 pr-3 font-medium">Started</th>
                <th className="py-1.5 pr-3 font-medium">Question</th>
                <th className="py-1.5 pr-3 font-medium">Mode</th>
                <th className="py-1.5 pr-3 font-medium">Status</th>
                <th className="py-1.5 font-medium">Usage</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((run) => (
                <tr key={run.run_id} className="border-b border-line align-top">
                  <td className="py-2 pr-3 text-xs whitespace-nowrap text-muted">{new Date(run.started_at).toLocaleString()}</td>
                  <td className="py-2 pr-3">
                    <Link href={`/runs/${encodeURIComponent(run.run_id)}`} className="hover:text-accent hover:underline">
                      {run.question || <span className="text-muted">(no question)</span>}
                    </Link>
                    {run.example && <span className="ml-2 rounded border border-line px-1 text-xs text-muted">example</span>}
                  </td>
                  <td className={`py-2 pr-3 text-xs whitespace-nowrap ${run.mode === "prime" ? "text-accent" : "text-plain"}`}>
                    {run.mode} · {run.depth}
                  </td>
                  <td className="py-2 pr-3">
                    <StatusBadge status={run.status} />
                    {run.status === "budget_exhausted" && (
                      <span className="ml-2 text-xs whitespace-nowrap text-muted" title={LIMIT_NOTE_GENERIC}>
                        ⓘ limit reached
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-xs whitespace-nowrap text-muted">
                    {run.usage
                      ? `${run.usage.searches} searches · ${formatSeconds(run.usage.wall_seconds)} · ${formatTokens(totalTokens(run.usage))} tok`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

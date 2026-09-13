import { formatPercent } from "@/lib/format";
import type { CriticReport } from "@/lib/types";

const SECTIONS: { key: keyof CriticReport; label: string }[] = [
  { key: "weak_claims", label: "Weak claims" },
  { key: "missing_interpretations", label: "Missing interpretations" },
  { key: "contradictions", label: "Contradictions" },
  { key: "outdated_sources", label: "Outdated sources" },
  { key: "secondary_when_primary_exists", label: "Secondary where a primary source exists" },
  { key: "source_independence_issues", label: "Source independence" },
];

/** Critic tab (docs/07 §3): what the critic found and what it asked to search for. */
export function CriticPanel({ critiques, finished }: { critiques: CriticReport[]; finished: boolean }) {
  if (critiques.length === 0) {
    return (
      <p className="text-sm text-muted">
        {finished ? "The critic did not run (fast depth, or it was skipped)." : "The critic runs after the judge is satisfied."}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {critiques.map((report, index) => (
        <div key={index} className="rounded-md border border-line p-3 text-sm">
          <p className="font-medium">
            Critic report {critiques.length > 1 ? index + 1 : ""} · completion probability {formatPercent(report.completion_probability)}
          </p>
          {report.reasoning && <p className="mt-1 text-xs text-muted">{report.reasoning}</p>}
          {SECTIONS.map(({ key, label }) => {
            const items = report[key] as string[];
            return items.length > 0 ? (
              <div key={key} className="mt-2">
                <p className="text-xs font-medium text-muted">{label}</p>
                <ul className="mt-0.5 list-disc pl-5 text-xs">
                  {items.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null;
          })}
          {report.recommended_searches.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-muted">Recommended searches</p>
              <ul className="mt-0.5 list-disc pl-5 text-xs">
                {report.recommended_searches.map((task) => (
                  <li key={task.task_id}>
                    <span className="font-mono text-muted">{task.task_id}</span> {task.instruction}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

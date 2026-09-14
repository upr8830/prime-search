import { formatScore, formatTokens } from "@/lib/format";
import type { BenchConfig, BenchReport, BreakdownRow, MetricSummary } from "@/lib/types";

// docs/05 §2's twelve keys, in the report's order.
const METRICS = [
  "answer_correctness",
  "evidence_recall",
  "citation_correctness",
  "citation_completeness",
  "currency",
  "contradiction_handling",
  "scope_handling",
  "primary_source_ratio",
  "search_cost",
  "latency_s",
  "tokens",
  "search_efficiency",
] as const;

function formatMetric(key: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (key === "tokens") return formatTokens(Math.round(value));
  if (key === "latency_s" || key === "search_cost" || key === "search_efficiency") return value.toFixed(1);
  return formatScore(value);
}

function Cell({ metric, summary }: { metric: string; summary: MetricSummary | undefined }) {
  if (!summary) return <td className="px-2 py-1.5 text-muted">—</td>;
  return (
    <td className="px-2 py-1.5 whitespace-nowrap" title={`n = ${summary.n}`}>
      {formatMetric(metric, summary.mean)}
      {summary.spread !== null && <span className="text-muted"> ± {formatMetric(metric, summary.spread)}</span>}
    </td>
  );
}

function label(key: string): string {
  return key.replaceAll("_", " ");
}

/** `/bench` (docs/07 §5): `reports/latest.json` as a configs × metrics table. */
export function BenchTable({ report }: { report: BenchReport }) {
  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted">
        Split <span className="font-medium text-foreground">{report.split}</span> · generated {report.generated_at} ·{" "}
        {report.passes} pass{report.passes === 1 ? "" : "es"} per config
        {report.split !== "holdout" && " · a build-time check on a small split, not a result to quote"}
      </p>

      <div className="overflow-x-auto">
        <table className="text-left text-xs">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="px-2 py-1.5 font-medium">Config</th>
              {METRICS.map((metric) => (
                <th key={metric} className="px-2 py-1.5 font-medium">
                  {label(metric)}
                </th>
              ))}
              <th className="px-2 py-1.5 font-medium">composite</th>
              <th className="px-2 py-1.5 font-medium">judge errors{report.passes > 1 ? " (all passes)" : ""}</th>
              <th className="px-2 py-1.5 font-medium">failed runs{report.passes > 1 ? " (all passes)" : ""}</th>
            </tr>
          </thead>
          <tbody>
            {report.configs.map((config) => (
              <tr key={config.config} className="border-b border-line align-top">
                <td className="px-2 py-1.5">
                  <span className={`font-medium ${config.mode === "prime" ? "text-accent" : "text-plain"}`}>{config.config}</span>
                  <span className="block text-muted">n = {config.n}</span>
                  {config.experiments.map((experiment) =>
                    experiment.url ? (
                      <a key={experiment.name} href={experiment.url} target="_blank" rel="noreferrer" className="block text-accent underline">
                        LangSmith ↗
                      </a>
                    ) : null,
                  )}
                </td>
                {METRICS.map((metric) => (
                  <Cell key={metric} metric={metric} summary={config.metrics[metric]} />
                ))}
                <Cell metric="composite" summary={config.composite} />
                <td className="px-2 py-1.5">{config.judge_errors}</td>
                <td className="px-2 py-1.5">{config.failed_runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* per_tier and per_domain come from the latest pass only (eval/report.py). */}
      <Breakdown title={`Per tier${report.passes > 1 ? " (latest pass)" : ""}`} configs={report.configs} pick={(config) => config.per_tier} />
      <Breakdown title={`Per domain${report.passes > 1 ? " (latest pass)" : ""}`} configs={report.configs} pick={(config) => config.per_domain} />

      <section>
        <h2 className="mb-2 text-sm font-medium">PRD targets (docs/00 §9)</h2>
        <div className="overflow-x-auto">
          <table className="text-left text-xs">
            <thead className="text-muted">
              <tr className="border-b border-line">
                {["Config", "Metric", "Subset", "Value", "n", "Target", "Met"].map((heading) => (
                  <th key={heading} className="px-2 py-1.5 font-medium">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.prd_targets.map((target, index) => (
                <tr key={index} className="border-b border-line">
                  <td className="px-2 py-1.5">{target.config}</td>
                  <td className="px-2 py-1.5">{label(target.metric)}</td>
                  <td className="px-2 py-1.5 text-muted">{target.subset}</td>
                  <td className="px-2 py-1.5">{formatScore(target.value)}</td>
                  <td className="px-2 py-1.5">{target.n}</td>
                  <td className="px-2 py-1.5">{formatScore(target.target)}</td>
                  <td className={`px-2 py-1.5 ${target.met === true ? "text-ok" : target.met === false ? "text-bad" : "text-muted"}`}>
                    {target.met === null ? "—" : target.met ? "met" : "not met"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Breakdown({
  title,
  configs,
  pick,
}: {
  title: string;
  configs: BenchConfig[];
  pick: (config: BenchConfig) => Record<string, BreakdownRow>;
}) {
  const rows = configs.flatMap((config) => Object.entries(pick(config)).map(([group, row]) => ({ config, group, row })));
  const keys = [...new Set(rows.flatMap(({ row }) => Object.keys(row).filter((key) => key !== "n")))];
  if (rows.length === 0) return null;
  return (
    <details>
      <summary className="cursor-pointer text-sm font-medium">{title}</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="text-left text-xs">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="px-2 py-1.5 font-medium">{title.replace("Per ", "")}</th>
              <th className="px-2 py-1.5 font-medium">Config</th>
              <th className="px-2 py-1.5 font-medium">n</th>
              {keys.map((key) => (
                <th key={key} className="px-2 py-1.5 font-medium">
                  {label(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ config, group, row }) => (
              <tr key={`${config.config}-${group}`} className="border-b border-line">
                <td className="px-2 py-1.5">{group}</td>
                <td className="px-2 py-1.5">{config.config}</td>
                <td className="px-2 py-1.5">{row.n}</td>
                {keys.map((key) => (
                  <td key={key} className="px-2 py-1.5">
                    {formatMetric(key, row[key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

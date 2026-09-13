/**
 * Names for the API's schemas (generated into `@/types/api` by `pnpm gen:types`, docs/07 §8),
 * plus the one response OpenAPI cannot type: `GET /bench/summary`, which serves
 * `reports/latest.json` as `eval.report` wrote it (docs/05 §3).
 */

import type { components } from "@/types/api";

type Schemas = components["schemas"];

export type Answer = Schemas["Answer"];
export type ApiEvent = Schemas["Event"];
export type BenchQuestion = Schemas["BenchQuestion"];
export type Branch = Schemas["Branch"];
export type Budget = Schemas["Budget"];
export type Citation = Schemas["Citation"];
export type Claim = Schemas["Claim"];
export type CriticReport = Schemas["CriticReport"];
export type DocView = Schemas["DocView"];
export type Document = Schemas["Document"];
export type Evidence = Schemas["Evidence"];
export type FeedbackIn = Schemas["FeedbackIn"];
export type Ok = Schemas["Ok"];
export type ParagraphOut = Schemas["ParagraphOut"];
export type QueryUnderstanding = Schemas["QueryUnderstanding"];
export type RunRecord = Schemas["RunRecord"];
export type RunRequest = Schemas["RunRequest"];
export type RunStarted = Schemas["RunStarted"];
export type RunSummary = Schemas["RunSummary"];
export type SearchPlan = Schemas["SearchPlan"];
export type SearchTask = Schemas["SearchTask"];
export type TaskResult = Schemas["TaskResult"];
export type UiEventIn = Schemas["UiEventIn"];
export type Usage = Schemas["Usage"];
export type Verdict = Schemas["Verdict"];

export type Tier = Document["source_tier"];
export type ClaimStatus = Claim["status"];
export type RunStatus = RunSummary["status"];
export type UiEventType = UiEventIn["type"];

// --- GET /bench/summary (reports/latest.json, docs/05 §3 as built) -------------------------

export type MetricSummary = { mean: number | null; spread: number | null; n: number };

export type BenchExperiment = {
  name: string;
  url: string | null;
  tavily_cache: boolean | null;
  git_sha?: string | null;
  evaluator_model?: string | null;
  dataset_sha?: string | null;
  started_at?: string | null;
  rescored_at?: string | null;
  file?: string;
};

/** Per-tier and per-domain rows hold flat numbers (or null), not MetricSummary objects. */
export type BreakdownRow = { n: number } & Record<string, number | null>;

export type BenchConfig = {
  config: string;
  mode: string;
  prompt_set: string | null;
  depth: string | null;
  split: string;
  n: number;
  experiments: BenchExperiment[];
  metrics: Record<string, MetricSummary>;
  composite: MetricSummary;
  per_tier: Record<string, BreakdownRow>;
  per_domain: Record<string, BreakdownRow>;
  judge_errors: number;
  failed_runs: number;
  judge_tokens: number;
  missing_keys: string[];
};

export type PrdTarget = {
  config: string;
  metric: string;
  subset: string;
  value: number | null;
  n: number;
  target: number;
  met: boolean | null;
};

export type BenchReport = {
  generated_at: string;
  split: string;
  passes: number;
  sources: string[];
  configs: BenchConfig[];
  prd_targets: PrdTarget[];
};

export type BenchSummary = BenchReport | { missing: true; error?: string };

export function isMissingReport(summary: BenchSummary): summary is { missing: true; error?: string } {
  return "missing" in summary && summary.missing === true;
}

import type { ViewStatus } from "./reducer";
import type { ClaimStatus, RunStatus, Tier, Usage } from "./types";

export const TIER_LABEL: Record<Tier, string> = {
  primary_policy: "primary",
  official_secondary: "official secondary",
  professional: "professional",
  trade: "trade",
  web: "web",
  unknown: "unknown",
};

export function tierLabel(tier: string | null | undefined): string {
  return (tier && TIER_LABEL[tier as Tier]) || tier || "unknown";
}

/** docs/07 §10: primary solid, official secondary outline, the rest muted. */
export function tierBadgeClass(tier: string | null | undefined): string {
  if (tier === "primary_policy") return "bg-foreground text-background border border-foreground";
  if (tier === "official_secondary") return "border border-foreground text-foreground";
  return "border border-line text-muted";
}

export const STATUS_LABEL: Record<ViewStatus | RunStatus, string> = {
  connecting: "connecting",
  running: "running",
  completed: "completed",
  budget_exhausted: "budget hit",
  failed: "failed",
  interrupted: "interrupted",
};

export const CLAIM_STATUS_CLASS: Record<ClaimStatus, string> = {
  supported: "text-ok bg-ok-soft border-ok",
  contested: "text-warn bg-warn-soft border-warn",
  weak: "text-weak bg-plain-soft border-line",
  unresolved: "text-bad bg-bad-soft border-bad",
};

export function formatTokens(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 10_000) return `${Math.round(count / 1000)}k`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return String(count);
}

export function totalTokens(usage: Usage): number {
  return usage.input_tokens + usage.output_tokens;
}

export function formatSeconds(seconds: number): string {
  return seconds < 10 ? `${seconds.toFixed(1)} s` : `${Math.round(seconds)} s`;
}

export function formatDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "—";
}

export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

export function formatScore(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : value.toFixed(digits);
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

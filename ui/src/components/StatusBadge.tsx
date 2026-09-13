import { STATUS_LABEL } from "@/lib/format";
import type { ViewStatus } from "@/lib/reducer";
import type { RunStatus } from "@/lib/types";

const TONE: Record<ViewStatus | RunStatus, string> = {
  connecting: "border-line text-muted",
  running: "border-accent text-accent",
  completed: "border-ok text-ok",
  budget_exhausted: "border-warn text-warn bg-warn-soft",
  failed: "border-bad text-bad bg-bad-soft",
  interrupted: "border-bad text-bad bg-bad-soft",
};

/** A run status, always as a word (docs/07 §10: never colour alone). */
export function StatusBadge({ status }: { status: ViewStatus | RunStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${TONE[status]}`}>
      {status === "running" && <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
      {STATUS_LABEL[status]}
    </span>
  );
}

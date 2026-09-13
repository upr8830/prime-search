import type { RunView } from "@/lib/reducer";

/**
 * Plan tab (docs/07 §4): the SearchPlan and the root's plan code, which is where the RLM
 * code-as-action is visible to a reviewer.
 */
export function PlanTab({ view }: { view: RunView }) {
  const plan = view.plan;
  if (!plan) return <p className="text-sm text-muted">{view.finished ? "No plan was recorded." : "Planning…"}</p>;

  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="py-1 pr-2 font-medium">Branch</th>
              <th className="py-1 pr-2 font-medium">Question</th>
              <th className="py-1 pr-2 font-medium">Why</th>
              <th className="py-1 pr-2 font-medium">Source</th>
              <th className="py-1 pr-2 font-medium">Priority</th>
              <th className="py-1 font-medium">Depends on</th>
            </tr>
          </thead>
          <tbody>
            {plan.branches.map((branch) => (
              <tr key={branch.branch_id} className="border-b border-line align-top">
                <td className="py-1.5 pr-2 font-mono">{branch.branch_id}</td>
                <td className="py-1.5 pr-2">
                  {branch.question}
                  {branch.hypothesis && <span className="block text-muted">hypothesis: {branch.hypothesis}</span>}
                </td>
                <td className="py-1.5 pr-2 text-muted">{branch.rationale}</td>
                <td className="py-1.5 pr-2">{branch.source_hint.replaceAll("_", " ")}</td>
                <td className="py-1.5 pr-2">{branch.priority}</td>
                <td className="py-1.5 font-mono">{branch.depends_on.join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <p className="text-xs font-medium text-muted">Stop criteria</p>
        <p>{plan.stop_criteria}</p>
      </div>

      <div>
        <p className="text-xs font-medium text-muted">Budget</p>
        <p className="font-mono text-xs">
          {Object.entries(plan.budget)
            .map(([key, value]) => `${key}=${value}`)
            .join("  ")}
        </p>
      </div>

      <div>
        <p className="text-xs font-medium text-muted">Plan code (the root&rsquo;s code-as-action)</p>
        {!view.planCodeRecorded ? (
          <p className="text-xs text-muted">Plan code was not recorded for this run: it predates the plan event carrying it.</p>
        ) : view.planCode ? (
          <pre className="mt-1 overflow-x-auto rounded-md border border-line bg-panel p-3 font-mono text-xs leading-relaxed">
            {view.planCode}
          </pre>
        ) : (
          <p className="text-xs text-muted">This plan came from a fallback rung (structured output or the default plan), so there is no code.</p>
        )}
      </div>
    </div>
  );
}

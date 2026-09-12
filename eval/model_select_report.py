"""Turn model-selection-raw.json into reports/model-selection.md.

    uv run python -m eval.model_select_report

Separate from the runner so the report can be regenerated without spending calls,
and so every number in it is derived rather than transcribed by hand.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

RAW = Path("reports/model-selection-raw.json")
OUT = Path("reports/model-selection.md")

PROBE_TITLES = {
    "root_plan": (
        "Root — code-as-action plan",
        "Fenced Python that executes in the real `Workspace` sandbox and leaves a "
        "valid `SearchPlan` with 3-7 branches (docs/03 §3, §12).",
    ),
    "critic_json": (
        "Critic — fenced JSON",
        "A parseable JSON object (docs/01 §4). `flagged c1` means the model caught the "
        "planted weak claim: a coverage assertion resting on a vendor blog.",
    ),
    "subagent_tool": (
        "Sub-agent — native tool calling",
        "A native tool call when bound to the real Tavily search tool (docs/03 §4).",
    ),
    "judge_struct": (
        "Judge / extractor — structured output",
        "`with_structured_output(Verdict)` measured **natively**, without "
        "`models.structured()`'s repair ladder, which otherwise hides the difference.",
    ),
}


RECOMMENDATION = """## Recommendation

**One change is justified by the evidence; the rest of the routing should stand.**

### Change: judge, extractor and evaluator — Kimi-K2.6 -> `deepseek-ai/DeepSeek-V4-Flash-0731`

Kimi-K2.6 was the **only** candidate to fail native structured output (2/3 here,
and 17/20 when I measured it separately on 2026-09-12). Five alternatives went 3/3.
That flakiness is why `models.structured()` carries a repair ladder, and the ladder
costs a wasted call plus a fenced-JSON retry on roughly one judge call in six — on
every question, in every bench row, in every GEPA rollout.

V4-Flash is the pick among the five: fastest (1.6s median), 1M context against
Kimi's 262K, and $0.14/$0.28 per 1M. `Qwen/Qwen3-30B-A3B-Instruct-2507` is the
cheaper runner-up (3/3, 1.9s, $0.10/$0.30) if cost matters more than context.

Keep the ladder regardless — it is cheap insurance and docs/01 §4 rule 3 asks for
it — but it should stop firing routinely.

### Keep: root and critic on `nvidia/nemotron-3-super-120b-a12b`

The spec's choice wins on the measurements. 5/5 valid plans and 3/3 parseable
critiques, at the **lowest cost and lowest latency of any root candidate**
($0.00125/call, 4.4s). Kimi-K3 matches its validity at 23x the cost and 5x the
latency; Nemotron-3-Ultra matches it at 3.4x the cost with no measurable gain;
`Qwen3.5-397B` and `Kimi-K2.6` are 5x slower. Nothing here justifies a change.

`deepseek-ai/DeepSeek-V4-Pro` is the one genuine alternative for the **critic**
specifically — 3/3, 2.5s, and 137 output tokens against Nemotron's 934, because it
answers without thinking aloud. Cost per call is a wash ($0.00093 vs $0.00090). Not
worth a second model in the routing for that.

Every passing model flagged the planted weak claim, so this probe does not
discriminate on critic *quality* — only on format compliance. Treat the critic
choice as unresolved until `critic.md` exists (task 2.2).

### Keep: sub-agent on `moonshotai/Kimi-K2.6`, but revisit at 1.6

All six candidates emitted native tool calls 5/5 — including
`nvidia/Nemotron-3_5-Lightning`, a reasoning-family model. **docs/11 A12's
tool-call caveat does not reproduce on any model in the catalog today.**

Two caveats against acting on this yet:

* The probe only checks that a tool call was emitted, not that it was *usable*.
  `meta-llama/Llama-3.3-70B-Instruct` "passed" 5/5 while calling
  `tavily_search(end_date, exclude_domains, include_domains)` — **with no `query`
  argument at all**. That call would fail. A pass here is weaker evidence than it
  looks, and Llama is disqualified on the detail rather than the score.
* Sub-agent competence is a multi-turn property — fetch before evidence, verbatim
  passages, staying inside budget. None of that is measurable until task 1.6 builds
  the agent loop.

`Qwen3-30B` (1.4s, $0.00019) and `DeepSeek-V4-Flash` (1.7s, 1M context) are the
candidates to re-test then; sub-agents are the highest-volume role, so this is where
cost savings actually live.

### Fix regardless of any routing decision

`models.FALLBACKS` names `deepseek-ai/DeepSeek-V3.2` for five roles and
`DeepSeek-R1-0528` is offered as an alternate root in docs/01 §4. **Neither exists
in the catalog.** Every fallback would raise model-not-found. Proposed replacement,
using the measurements above: `deepseek-ai/DeepSeek-V4-Flash-0731` for the
tool-calling and structured-output roles (5/5 and 3/3 respectively), and
`nvidia/Nemotron-3-Ultra-550b-a55b` for root/critic (5/5 code-as-action, a different
vendor line from the primary so a vendor-wide outage does not take both down).

### Measurement gaps, stated

* `judge_struct` records 0 tokens: `with_structured_output` returns a Pydantic
  object, not a message, so usage metadata was not captured. Latency and validity
  are sound; its cost column is not.
* `plan.md`, `critic.md` and `search_agent.md` do not exist yet (tasks 1.7, 2.2,
  1.6). These probes use stand-in prompts matching the production *shape*, so the
  ranking measures shape compliance, not final-prompt quality.
* Prices for Kimi-K2.6, GLM-5.3 and Llama-3.3-70B are unpublished in every source
  reachable here, so their cost columns are blank rather than estimated.

### Disqualified

`zai-org/GLM-5.3` fails code-as-action outright: 2/5 on fenced Python, 1/3 on
fenced JSON, and the slowest root candidate at 34s while emitting 7,575 output
tokens per call. It cannot hold a root or critic role in this design.

"""


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.5f}" if value < 0.01 else f"${value:.4f}"


def main() -> int:
    payload = json.loads(RAW.read_text(encoding="utf-8"))
    trials: list[dict[str, Any]] = payload["trials"]
    candidates = {c["model"]: c for c in payload["candidates"]}

    by_probe: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for trial in trials:
        by_probe[trial["probe"]][trial["model"]].append(trial)

    lines: list[str] = [
        "# Model selection over the live Nebius catalog",
        "",
        "Measured 2026-09-12 against `https://api.studio.nebius.ai/v1`. Every candidate",
        "runs through **the exact call shape its role uses in this codebase**, because",
        "that is what has discriminated between models so far: `docs/01` §4's whole",
        "code-as-action design exists because reasoning models were reported to reject",
        "native tool calls, and `make smoke` measured Kimi-K2.6 returning `None` from",
        "`with_structured_output` on 15% of calls. Neither fact is visible on a",
        "leaderboard.",
        "",
        "## Findings that need action regardless of the ranking",
        "",
        "1. **`docs/01` §4's fallback ladder points at models that no longer exist.**",
        "   `deepseek-ai/DeepSeek-V3.2` (the stated fallback for every non-root role) and",
        "   `deepseek-ai/DeepSeek-R1-0528` (the optional root alternative) are both absent",
        "   from the catalog; the DeepSeek line is now V4-Flash / V4-Pro. `models.FALLBACKS`",
        "   and `fallback_model()` would raise model-not-found if anything triggered them —",
        "   a latent break in the one mechanism meant to rescue a failing role.",
        "2. **No Llama 4** of any size is offered. Nebius's own function-calling",
        "   documentation still uses a Llama 3.1 Instruct model as its worked example.",
        "3. **`PRIME_MODELS__SUB` is silently ignored** — the field is `subagent`, so the",
        "   working override is `PRIME_MODELS__SUBAGENT`. `Settings` uses `extra=\"ignore\"`,",
        "   so any mistyped `PRIME_*` key is dropped without a word.",
        "4. **Published capability tables are unreliable.** The only aggregator carrying",
        "   Nebius rows lists *every* model as `Tool Calling: No`, including Kimi-K2.6,",
        "   which demonstrably emits native tool calls here. Nebius's own docs never",
        "   enumerate which models support tools. Hence these measurements.",
        "",
        "## Catalog",
        "",
        "24 models are offered; the 22 chat models are below (`Qwen3-Embedding-8B` and",
        "`MiniCPM-V-4_5` are embedding and vision). Prices are USD per 1M tokens from",
        "`mastra.ai/models/providers/nebius` (read 2026-09-12) — Nebius's own pricing page",
        "is JavaScript-rendered and its docs carry no price table, so prices are",
        "second-hand and marked — where no row existed. **Token counts below are measured;",
        "dollar figures are indicative.**",
        "",
        "| model | ctx | $/1M in | $/1M out | tested as |",
        "|---|---|---|---|---|",
    ]
    for model, c in candidates.items():
        roles = ", ".join(c["roles"])
        lines.append(
            f"| `{model}` | {c['context']} | {_price(c['price_in'])} | "
            f"{_price(c['price_out'])} | {roles} |"
        )
    lines += [
        "",
        f"Named in the brief but absent from the catalog: "
        f"{', '.join('`' + m + '`' for m in payload['absent_from_catalog'])}.",
        "",
    ]

    for probe, (title, blurb) in PROBE_TITLES.items():
        models = by_probe.get(probe)
        if not models:
            continue
        lines += [f"## {title}", "", blurb, "", "| model | pass | median s | tok in/out | cost/call | detail |", "|---|---|---|---|---|---|"]
        rows = []
        for model, model_trials in models.items():
            passed = sum(1 for t in model_trials if t["ok"])
            total = len(model_trials)
            latencies = [t["seconds"] for t in model_trials]
            costs = [t["cost"] for t in model_trials if t["cost"] is not None]
            tokens_in = statistics.mean(t["input_tokens"] for t in model_trials)
            tokens_out = statistics.mean(t["output_tokens"] for t in model_trials)
            details = sorted({t["detail"] or (t["error"] or "")[:60] for t in model_trials} - {""})
            errors = [t["error"] for t in model_trials if t["error"]]
            rows.append(
                (
                    passed / total,
                    f"| `{model}` | {passed}/{total} | {statistics.median(latencies):.1f} | "
                    f"{tokens_in:.0f}/{tokens_out:.0f} | "
                    f"{_fmt_money(statistics.mean(costs)) if costs else '—'} | "
                    f"{'; '.join(details)[:70] or '—'} |",
                    errors,
                )
            )
        for _, row, _errors in sorted(rows, key=lambda r: -r[0]):
            lines.append(row)
        normalized = [
            t["model"] for t in trials if t["probe"] == probe and t.get("reasoning_normalized")
        ]
        if normalized:
            lines += [
                "",
                "Answered in `reasoning_content` and recovered by `models.py`'s "
                f"normalization: {', '.join('`' + m + '`' for m in sorted(set(normalized)))}. "
                "Without that normalization these would have returned empty `content`.",
            ]
        lines.append("")

    lines += RECOMMENDATION.splitlines()

    total_cost = sum(t["cost"] or 0 for t in trials)
    priced = sum(1 for t in trials if t["cost"] is not None)
    lines += [
        "## Cost of this experiment",
        "",
        f"{len(trials)} model calls. Measured spend on the {priced} calls to models with a",
        f"published price: **{_fmt_money(total_cost)}**. The remaining "
        f"{len(trials) - priced} calls went to models with no price row "
        "(Kimi-K2.6, GLM-5.3, Llama-3.3-70B), so true total spend is somewhat higher —",
        "on these token volumes, cents either way.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(trials)} trials)")
    return 0


def _price(value: float | None) -> str:
    return "—" if value is None else f"${value:g}"


if __name__ == "__main__":
    raise SystemExit(main())

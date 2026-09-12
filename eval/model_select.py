"""Role-shaped model selection over the live Nebius catalog.

    uv run --env-file .env python -m eval.model_select

Every candidate is exercised through *the exact call shape its role uses in this
codebase*, because that is what has actually discriminated between models so far:
docs/01 §4's whole design exists because reasoning models were reported to reject
native tool calls, and `make smoke` already measured Kimi-K2.6 returning None from
`with_structured_output` on 15% of calls. A leaderboard cannot tell you either of
those things.

Four probes:

* `root_plan`     — emit fenced Python that executes in the real Workspace sandbox
                    and leaves a valid SearchPlan with 3-7 branches (docs/03 §3, §12)
* `critic_json`   — emit a fenced JSON object the harness can parse (docs/01 §4)
* `subagent_tool` — emit a native tool call when bound to the real Tavily search
                    tool (docs/03 §4)
* `judge_struct`  — return a valid object from `with_structured_output(Verdict)`,
                    measured *natively*, without models.py's repair ladder, since
                    the ladder is what hides the difference between models

Scope, stated plainly: `prompts/plan.md`, `critic.md` and `search_agent.md` do not
exist yet — they are tasks 1.7, 2.2 and 1.6. The prompts here are stand-ins that
match the production *shape*, so these results rank models on shape compliance, not
on the final prompts. Re-run after 1.7 before treating the ranking as settled.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from prime_search.models import model_for, parse_fenced_json
from prime_search.primitives.sources import PRIMARY_DOMAINS
from prime_search.primitives.tavily import search_tool
from prime_search.schemas import SearchPlan, Verdict
from prime_search.workspace import Workspace

FENCED_PYTHON = re.compile(r"```(?:python)?\s*\n(.+?)```", re.DOTALL)

# --- catalog ---------------------------------------------------------------------

# Prices are USD per 1M tokens. Nebius's own pricing page is JavaScript-rendered and
# its docs do not carry a price table, so these come from an aggregator
# (mastra.ai/models/providers/nebius, read 2026-09-12) and are marked None where it
# had no row. Cost figures below are therefore indicative; token counts are measured.
@dataclass(frozen=True)
class Candidate:
    model: str
    context: str
    price_in: float | None  # USD / 1M input tokens
    price_out: float | None
    roles: tuple[str, ...]
    note: str = ""


CANDIDATES: tuple[Candidate, ...] = (
    # --- root / critic: code-as-action, no native tool calling required ----------
    Candidate("nvidia/nemotron-3-super-120b-a12b", "262K", 0.30, 0.90, ("root", "critic"),
              "current default"),
    Candidate("nvidia/Nemotron-3-Ultra-550b-a55b", "1.0M", 1.00, 3.00, ("root", "critic"),
              "frontier reasoning/orchestration"),
    Candidate("moonshotai/Kimi-K3", "1.0M", 3.00, 15.00, ("root", "critic"),
              "newest Kimi; most expensive"),
    Candidate("moonshotai/Kimi-K2.6", "262K", None, None, ("root", "critic", "subagent", "judge"),
              "current sub-agent/judge default"),
    Candidate("Qwen/Qwen3.5-397B-A17B", "262K", 0.60, 4.00, ("root", "critic")),
    Candidate("zai-org/GLM-5.3", "1.0M", None, None, ("root", "critic"),
              "newest GLM; no price row found"),
    Candidate("deepseek-ai/DeepSeek-V4-Pro", "1.0M", 2.00, 4.00, ("root", "critic"),
              "replaces the absent V3.2/R1"),
    # --- sub-agent / judge: native tool calling and structured output ------------
    Candidate("deepseek-ai/DeepSeek-V4-Flash-0731", "1.0M", 0.14, 0.28, ("subagent", "judge")),
    Candidate("Qwen/Qwen3-30B-A3B-Instruct-2507", "262K", 0.10, 0.30, ("subagent", "judge")),
    Candidate("meta-llama/Llama-3.3-70B-Instruct", "128K", None, None, ("subagent", "judge"),
              "no price row found"),
    Candidate("nvidia/Nemotron-3_5-Lightning", "1.0M", 0.06, 0.24, ("subagent", "judge"),
              "cheapest in catalog"),
    Candidate("zai-org/GLM-5.3-Flash", "1.0M", 0.15, 0.50, ("subagent", "judge")),
)

# Named in the brief but absent from the live catalog on 2026-09-12.
ABSENT = (
    "deepseek-ai/DeepSeek-V3.2",  # docs/01 §4's stated fallback for non-root roles
    "deepseek-ai/DeepSeek-R1-0528",  # docs/01 §4's optional root alternative
    "meta-llama/Llama-4-*",  # no Llama 4 of any size is offered
)

# --- probes ----------------------------------------------------------------------

QUESTIONS = [
    "Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?",
    "Which HCPCS codes apply to a therapeutic CGM supply allowance under Medicare?",
    "Has Medicare coverage for GLP-1 receptor agonists changed in the last year?",
]

PLAN_PROMPT = """You are the planning component of a Medicare coverage-determination
research agent. Break the question into independent research branches.

Emit a single fenced Python code block and nothing else — no prose before or after.
The block runs in a sandbox where `ws`, `SearchPlan`, `Branch` and `QueryUnderstanding`
are already defined. Assign `ws.plan`.

Use between 3 and 7 branches. Each Branch needs branch_id ("b1", "b2", ...), question,
hypothesis (or None), rationale, source_hint (one of "primary_policy",
"coding_article", "fda_label", "guidance", "news", "any"), and priority (1 = highest).

```python
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(branch_id="b1", question="...", hypothesis=None, rationale="...",
               source_hint="primary_policy", priority=1),
    ],
    stop_criteria="...",
    budget=ws.budget,
)
```

Question: {question}
"""

CRITIC_PROMPT = """You are the critic of a Medicare coverage-determination research
agent. Review the draft below and report what is weak about it.

Emit a single fenced JSON object and nothing else. Keys: weak_claims (list of claim
ids), outdated_sources (list of doc ids), contradictions (list of claim ids),
recommended_searches (list of short instructions), completion_probability (0-1),
reasoning (one or two sentences).

Draft answer under review:
  [c1] Therapeutic CGMs are always covered under Medicare for anyone with diabetes.
       Supported by: a 2019 vendor blog post (tier: web).
  [c2] The beneficiary must be treated with insulin.
       Supported by: LCD L33822, revision effective 2024-10-01 (tier: primary_policy).

One of these claims rests on a non-primary source and overstates coverage.
"""

TOOL_QUESTION = (
    "What are the current Medicare LCD coverage criteria for therapeutic continuous "
    "glucose monitors? Search the primary sources."
)

JUDGE_PROMPT = (
    "You are judging whether a research round is sufficient. Nothing has been searched "
    "yet, so it is not. Branch b1 is unresolved. Return a Verdict for round 1 with "
    "sufficient=false."
)


@dataclass
class Trial:
    model: str
    probe: str
    ok: bool
    seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    detail: str = ""
    error: str | None = None
    reasoning_normalized: bool = False

    @property
    def cost(self) -> float | None:
        prices = PRICE_BY_MODEL.get(self.model)
        if not prices or prices[0] is None or prices[1] is None:
            return None
        return (self.input_tokens * prices[0] + self.output_tokens * prices[1]) / 1_000_000


PRICE_BY_MODEL = {c.model: (c.price_in, c.price_out) for c in CANDIDATES}


def _usage(message: Any) -> tuple[int, int]:
    meta = getattr(message, "usage_metadata", None) or {}
    if meta:
        return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))
    token_usage = (getattr(message, "response_metadata", {}) or {}).get("token_usage", {})
    return int(token_usage.get("prompt_tokens", 0)), int(token_usage.get("completion_tokens", 0))


def _build(model: str, role: str = "root", **kwargs: Any) -> Any:
    """Every ChatNebius still comes from models.py (CLAUDE.md)."""
    return model_for(role, model=model, **kwargs)


def probe_root_plan(model: str, question: str) -> Trial:
    """Fenced Python that survives the real sandbox and yields a usable SearchPlan."""
    started = time.monotonic()
    try:
        message = _build(model).invoke(PLAN_PROMPT.format(question=question))
    except Exception as exc:
        return Trial(model, "root_plan", False, time.monotonic() - started,
                     error=f"{type(exc).__name__}: {str(exc)[:120]}")
    seconds = time.monotonic() - started
    tokens_in, tokens_out = _usage(message)
    normalized = bool(message.additional_kwargs.get("reasoning_normalized"))

    block = FENCED_PYTHON.search(message.text or "")
    if not block:
        return Trial(model, "root_plan", False, seconds, tokens_in, tokens_out,
                     detail="no fenced python block", reasoning_normalized=normalized)

    workspace = Workspace(objective=question)
    workspace.understanding = _understanding(question)
    result = workspace.exec(block.group(1))
    if not result.ok:
        return Trial(model, "root_plan", False, seconds, tokens_in, tokens_out,
                     detail=f"cell failed: {(result.error or '')[:80]}",
                     reasoning_normalized=normalized)
    if not isinstance(workspace.plan, SearchPlan):
        return Trial(model, "root_plan", False, seconds, tokens_in, tokens_out,
                     detail="cell ran but ws.plan is not a SearchPlan",
                     reasoning_normalized=normalized)
    branches = len(workspace.plan.branches)
    ok = 3 <= branches <= 7
    return Trial(model, "root_plan", ok, seconds, tokens_in, tokens_out,
                 detail=f"{branches} branches" + ("" if ok else " (outside 3-7)"),
                 reasoning_normalized=normalized)


def _understanding(question: str):
    from prime_search.schemas import QueryUnderstanding

    return QueryUnderstanding(
        normalized_question=question,
        domain="cgm" if "CGM" in question or "glucose" in question else "glp1",
        question_type="eligibility",
        time_sensitivity="medium",
    )


def probe_critic_json(model: str) -> Trial:
    started = time.monotonic()
    try:
        message = _build(model, "critic").invoke(CRITIC_PROMPT)
    except Exception as exc:
        return Trial(model, "critic_json", False, time.monotonic() - started,
                     error=f"{type(exc).__name__}: {str(exc)[:120]}")
    seconds = time.monotonic() - started
    tokens_in, tokens_out = _usage(message)
    normalized = bool(message.additional_kwargs.get("reasoning_normalized"))
    try:
        payload = parse_fenced_json(message.text)
    except Exception as exc:
        return Trial(model, "critic_json", False, seconds, tokens_in, tokens_out,
                     detail=f"unparseable: {type(exc).__name__}",
                     reasoning_normalized=normalized)
    if not isinstance(payload, dict):
        return Trial(model, "critic_json", False, seconds, tokens_in, tokens_out,
                     detail=f"got {type(payload).__name__}", reasoning_normalized=normalized)
    # Did it catch the planted weak claim? c1 rests on a vendor blog and overstates.
    flagged = "c1" in json.dumps(payload.get("weak_claims", []))
    return Trial(model, "critic_json", True, seconds, tokens_in, tokens_out,
                 detail=("flagged c1" if flagged else "missed c1"),
                 reasoning_normalized=normalized)


def probe_subagent_tool(model: str) -> Trial:
    started = time.monotonic()
    try:
        bound = _build(model, "subagent").bind_tools(
            [search_tool(include_domains=PRIMARY_DOMAINS)]
        )
        message = bound.invoke(TOOL_QUESTION)
    except Exception as exc:
        return Trial(model, "subagent_tool", False, time.monotonic() - started,
                     error=f"{type(exc).__name__}: {str(exc)[:120]}")
    seconds = time.monotonic() - started
    tokens_in, tokens_out = _usage(message)
    calls = getattr(message, "tool_calls", None) or []
    if not calls:
        return Trial(model, "subagent_tool", False, seconds, tokens_in, tokens_out,
                     detail="no tool_calls")
    args = calls[0].get("args", {})
    return Trial(model, "subagent_tool", True, seconds, tokens_in, tokens_out,
                 detail=f"{calls[0]['name']}({','.join(sorted(args))[:40]})")


def probe_judge_struct(model: str) -> Trial:
    """Native structured output only — models.py's ladder would mask the difference."""
    started = time.monotonic()
    try:
        result = _build(model, "judge").with_structured_output(Verdict).invoke(JUDGE_PROMPT)
    except Exception as exc:
        return Trial(model, "judge_struct", False, time.monotonic() - started,
                     error=f"{type(exc).__name__}: {str(exc)[:120]}")
    seconds = time.monotonic() - started
    ok = isinstance(result, Verdict)
    return Trial(model, "judge_struct", ok, seconds,
                 detail="Verdict" if ok else f"returned {type(result).__name__}")


PROBES = {
    "root_plan": ("root", 5),
    "critic_json": ("critic", 3),
    "subagent_tool": ("subagent", 5),
    "judge_struct": ("judge", 3),
}


def run(limit: int) -> list[Trial]:
    trials: list[Trial] = []
    calls = 0
    consecutive_errors: dict[str, int] = {}

    for probe, (role, repeats) in PROBES.items():
        for candidate in CANDIDATES:
            if role not in candidate.roles:
                continue
            if consecutive_errors.get(candidate.model, 0) >= 3:
                print(f"  SKIP {candidate.model} ({probe}) — dropped after 3 errors")
                continue
            for trial_index in range(repeats):
                if calls >= limit:
                    print(f"  budget of {limit} calls reached; stopping")
                    return trials
                if probe == "root_plan":
                    trial = probe_root_plan(candidate.model, QUESTIONS[trial_index % len(QUESTIONS)])
                elif probe == "critic_json":
                    trial = probe_critic_json(candidate.model)
                elif probe == "subagent_tool":
                    trial = probe_subagent_tool(candidate.model)
                else:
                    trial = probe_judge_struct(candidate.model)
                calls += 1
                trials.append(trial)
                if trial.error:
                    consecutive_errors[candidate.model] = (
                        consecutive_errors.get(candidate.model, 0) + 1
                    )
                    if consecutive_errors[candidate.model] >= 3:
                        print(f"  DROP {candidate.model} — 3 consecutive API errors")
                        break
                else:
                    consecutive_errors[candidate.model] = 0
                flag = "ok " if trial.ok else "FAIL"
                print(
                    f"  {flag} {probe:14} {candidate.model:38} "
                    f"{trial.seconds:5.1f}s {trial.detail or trial.error or ''}"[:150]
                )
    print(f"\ntotal model calls: {calls}")
    return trials


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=150, help="max model calls")
    parser.add_argument("--out", default="reports/model-selection-raw.json")
    args = parser.parse_args()

    print(f"{len(CANDIDATES)} candidates, probes: {', '.join(PROBES)}\n")
    trials = run(args.limit)

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "candidates": [asdict(c) for c in CANDIDATES],
                "absent_from_catalog": list(ABSENT),
                "trials": [asdict(t) | {"cost": t.cost} for t in trials],
            },
            indent=1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"\nraw results -> {path}")
    total = sum(t.cost or 0 for t in trials)
    print(f"measured cost (models with a published price): ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

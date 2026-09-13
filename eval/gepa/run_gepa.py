"""GEPA over PRIME's search-policy prompts (docs/05 §5).

    uv run --env-file .env python -m eval.gepa.run_gepa --dry-run
    uv run --env-file .env python -m eval.gepa.run_gepa
    uv run --env-file .env python -m eval.gepa.run_gepa --run-dir runs/gepa/<timestamp>   # resume

Trains on the `train` split and selects candidates on `dev`. Holdout is never touched:
the runner refuses any other split and the adapter refuses holdout records. Writes
`reports/gepa-run.json`, and `prime_search/prompts/optimized/<component>.md` only when the
best candidate beats the base prompts on dev. Acceptance on holdout is task 3.2's.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import gepa

from eval.gepa.adapter import COMPONENTS, GEPA_PROJECT, PrimeAdapter, prompt_set_name
from eval.searchbench.schema import load_records
from eval.searchbench.sync import check
from prime_search import prompts
from prime_search.agents.graph import _git_sha
from prime_search.config import Budget, get_settings
from prime_search.models import critic_model

# User decision (docs/11): option B, plan and judge only, 60 metric calls.
DEFAULT_COMPONENTS = ("plan", "judge")
DEFAULT_MAX_METRIC_CALLS = 60
# One scored deep run, from the Day 2 dev bench and current prices (docs/11).
COST_PER_EVALUATION = (0.60, 0.95)
MINUTES_PER_EVALUATION = 5.2
OPTIMIZED_DIR = Path("prime_search/prompts/optimized")
REPORT_PATH = Path("reports/gepa-run.json")
ACCEPTANCE = (
    "pending (task 3.2): docs/05 §5 accepts the optimized prompts only if holdout answer_correctness "
    "improves and citation_correctness does not drop by more than 0.03; otherwise base ships"
)


def gepa_budget(settings: Any) -> Budget:
    """docs/05 §5: the deep budget with `max_searches=20, max_agents=4`, to bound cost."""
    return settings.budget("deep").model_copy(update={"max_searches": 20, "max_agents": 4})


def estimate(max_metric_calls: int, concurrency: int, *, minibatch: int = 3, dev_size: int = 5) -> dict[str, float]:
    """Cost and wall time from the measured per-run figures. Reflection calls are extra
    and small (one critic-model call per GEPA iteration).

    GEPA checks the cap only between iterations, so the last one can finish past it: a new
    parent's minibatch, the child's minibatch and a dev evaluation (spec review)."""
    low, high = COST_PER_EVALUATION
    hours = max_metric_calls * MINUTES_PER_EVALUATION / 60
    overshoot = 2 * minibatch + dev_size
    return {
        "cost_low": round(max_metric_calls * low, 2),
        "cost_high": round(max_metric_calls * high, 2),
        "hours_sequential": round(hours, 1),
        # A minibatch is 3 records, so more than 3 at a time only speeds up dev evaluations.
        "hours_parallel": round(hours / max(1, min(concurrency, 3)), 1),
        "overshoot_runs": overshoot,
        "overshoot_cost_low": round(overshoot * low, 2),
        "overshoot_cost_high": round(overshoot * high, 2),
    }


def reflection_lm() -> Callable[[str | list[dict[str, Any]]], str]:
    """GEPA's reflection model: the critic model (docs/05 §5), built in models.py."""
    chat = critic_model()

    def call(prompt: str | list[dict[str, Any]]) -> str:
        return str(chat.invoke(prompt).text)

    return call


def prompt_diff(base: str, candidate: str, name: str) -> str:
    return "".join(
        difflib.unified_diff(
            base.splitlines(keepends=True),
            candidate.splitlines(keepends=True),
            fromfile=f"base/{name}.md",
            tofile=f"optimized/{name}.md",
        )
    )


def build_report(
    result: Any,
    *,
    seed: Mapping[str, str],
    components: Sequence[str],
    train_ids: Sequence[str],
    dev_ids: Sequence[str],
    rollouts: Sequence[Mapping[str, Any]],
    info: Mapping[str, Any],
    max_metric_calls: int,
    minibatch: int,
    run_dir: str,
    started_at: datetime,
    finished_at: datetime,
) -> dict[str, Any]:
    """`reports/gepa-run.json` (docs/05 §5): candidate scores, Pareto front, accepted edits."""

    def by_id(values: Mapping[Any, Any]) -> dict[str, Any]:
        return {
            (dev_ids[key] if isinstance(key, int) and 0 <= key < len(dev_ids) else str(key)): value
            for key, value in values.items()
        }

    candidates = []
    for idx, candidate in enumerate(result.candidates):
        changed = [name for name in components if candidate.get(name) != seed.get(name)]
        candidates.append(
            {
                "idx": idx,
                "parents": list(result.parents[idx]),
                "prompt_set": prompt_set_name(candidate),
                "dev_score": result.val_aggregate_scores[idx],
                "dev_scores": by_id(result.val_subscores[idx]),
                "discovered_at_metric_call": result.discovery_eval_counts[idx],
                "changed": changed,
                "diff": {name: prompt_diff(seed[name], candidate[name], name) for name in changed},
            }
        )
    best = result.best_idx
    scores = result.val_aggregate_scores
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        **info,
        "components": list(components),
        "max_metric_calls": max_metric_calls,
        "total_metric_calls": result.total_metric_calls,
        "num_full_val_evals": result.num_full_val_evals,
        "reflection_minibatch_size": minibatch,
        "train_ids": list(train_ids),
        "dev_ids": list(dev_ids),
        "run_dir": run_dir,
        "seed_dev_score": scores[0],
        "best_idx": best,
        "best_dev_score": scores[best],
        "improved_on_dev": best != 0 and scores[best] > scores[0],
        "pareto_front": {key: sorted(value) for key, value in by_id(result.per_val_instance_best_candidates).items()},
        "candidates": candidates,
        "rollouts": list(rollouts),
        "acceptance": ACCEPTANCE,
    }


def write_artifacts(
    result: Any,
    report: dict[str, Any],
    *,
    seed: Mapping[str, str],
    components: Sequence[str],
    optimized_dir: Path = OPTIMIZED_DIR,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    """The report always; optimized prompts only for a candidate that beat base on dev.
    The optimized set is exactly the best candidate, so an unchanged component's older
    file is removed and that prompt falls back to base."""
    written: list[str] = []
    removed: list[str] = []
    if report["improved_on_dev"]:
        best = result.candidates[report["best_idx"]]
        optimized_dir.mkdir(parents=True, exist_ok=True)
        for name in components:
            path = optimized_dir / f"{name}.md"
            if best[name] != seed[name]:
                path.write_text(best[name], encoding="utf-8", newline="\n")
                written.append(path.as_posix())
            elif path.is_file():
                path.unlink()
                removed.append(path.as_posix())
    report["optimized_prompts_written"] = written
    report["optimized_prompts_removed"] = removed
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n"
    )
    return report


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m eval.gepa.run_gepa", description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="train", help="training split; only 'train' (dev selects, holdout is never used)")
    parser.add_argument("--components", default=",".join(DEFAULT_COMPONENTS), help=f"comma-separated, from {', '.join(COMPONENTS)}")
    parser.add_argument("--max-metric-calls", type=int, default=DEFAULT_MAX_METRIC_CALLS)
    parser.add_argument("--minibatch", type=int, default=3, help="records per reflection step (GEPA's default 3)")
    parser.add_argument("--concurrency", type=int, default=3, help="runs at once")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--run-dir", help="GEPA checkpoint directory (default runs/gepa/<timestamp>); an existing one resumes")
    parser.add_argument("--dry-run", action="store_true", help="validate and print the plan and estimate; spend nothing")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.split != "train":
        reason = "holdout is never used for optimization (docs/05 §5)" if args.split == "holdout" else "GEPA trains on train and selects on dev"
        print(f"refusing to run: --split {args.split!r}; {reason}", file=sys.stderr)
        return 1
    components = [name.strip() for name in args.components.split(",") if name.strip()]
    unknown = [name for name in components if name not in COMPONENTS]
    if not components or unknown:
        print(f"refusing to run: components must come from {', '.join(COMPONENTS)} (got {args.components!r})", file=sys.stderr)
        return 1

    records = load_records()
    problems = check(records)
    if problems:
        for problem in problems:
            print(f"refusing to run: {problem}", file=sys.stderr)
        return 1
    train = [record for record in records if record.split == "train"]
    dev = [record for record in records if record.split == "dev"]
    unvalidated = [record.id for record in [*train, *dev] if not record.answer_key.is_validated]
    if unvalidated:
        print(f"refusing to run: unvalidated keys {unvalidated}", file=sys.stderr)
        return 1

    get_settings.cache_clear()
    settings = get_settings()
    budget = gepa_budget(settings)
    cost = estimate(args.max_metric_calls, args.concurrency, minibatch=args.minibatch, dev_size=len(dev))
    print(f"GEPA on {', '.join(components)}: train {len(train)} records, dev {len(dev)} (holdout never used)")
    print(f"max metric calls {args.max_metric_calls}, reflection minibatch {args.minibatch}, {args.concurrency} runs at a time")
    print(
        f"per run: deep, {budget.max_searches} searches, {budget.max_agents} agents per round, "
        f"{budget.max_tokens:,} tokens; Tavily cache {'on' if settings.tavily_cache else 'OFF'}"
    )
    print(
        f"estimated cost ${cost['cost_low']:.0f}-${cost['cost_high']:.0f}; about {cost['hours_parallel']} h "
        f"({cost['hours_sequential']} h one run at a time)"
    )
    print(
        f"the last iteration can run up to {cost['overshoot_runs']} more past the cap "
        f"(${cost['overshoot_cost_low']:.0f}-${cost['overshoot_cost_high']:.0f})"
    )
    if args.dry_run:
        return 0
    if not settings.tavily_cache:
        print("refusing to run: the Tavily cache is off (docs/05 §5 runs GEPA cached)", file=sys.stderr)
        return 1

    settings.export_sdk_env()
    started = datetime.now(UTC)
    run_dir = Path(args.run_dir or f"runs/gepa/{started:%Y%m%d-%H%M}")
    seed = {name: prompts.load(name, "base") for name in components}
    adapter = PrimeAdapter([*train, *dev], budget=budget, concurrency=args.concurrency)
    adapter.started_at = started.isoformat()  # a resume restores the first run's start
    result = gepa.optimize(
        seed_candidate=seed,
        trainset=train,
        valset=dev,
        adapter=adapter,
        reflection_lm=reflection_lm(),
        reflection_prompt_template=prompts.load("gepa_reflection"),
        reflection_minibatch_size=args.minibatch,
        candidate_selection_strategy="pareto",
        module_selector="round_robin",
        max_metric_calls=args.max_metric_calls,
        cache_evaluation=True,
        run_dir=str(run_dir),
        seed=args.seed,
        raise_on_exception=False,
    )
    report = build_report(
        result,
        seed=seed,
        components=components,
        train_ids=[record.id for record in train],
        dev_ids=[record.id for record in dev],
        rollouts=adapter.log,
        info={
            "git_sha": _git_sha(),
            "models": settings.models.model_dump(),
            "budget": budget.model_dump(),
            "tavily_cache": settings.tavily_cache,
            "langsmith_project": GEPA_PROJECT,
        },
        max_metric_calls=args.max_metric_calls,
        minibatch=args.minibatch,
        run_dir=run_dir.as_posix(),
        started_at=datetime.fromisoformat(adapter.started_at),
        finished_at=datetime.now(UTC),
    )
    write_artifacts(result, report, seed=seed, components=components)
    print(
        f"dev score: base {report['seed_dev_score']:.3f}, best {report['best_dev_score']:.3f} "
        f"(candidate {report['best_idx']} of {len(report['candidates'])}); metric calls {report['total_metric_calls']}"
    )
    print(f"optimized prompts written: {report['optimized_prompts_written'] or 'none (no candidate beat base on dev)'}")
    print(f"report: {REPORT_PATH.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

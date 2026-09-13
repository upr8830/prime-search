"""The SearchBench runner (docs/05 §3).

    uv run --env-file .env python -m eval.run_eval --mode baseline --split dev
    uv run --env-file .env python -m eval.run_eval --mode prime --split dev --prompt-set base
    uv run python -m eval.run_eval --rescore reports/bench/<experiment>.json

One invocation is one LangSmith experiment over one split. The target runs the real
agent (`run_prime` or `run_baseline`) with bench labels on its trace, and returns the
RunRecord in its outputs - the only thing an evaluator sees of a run. Results are also
written locally: `runs/<run_id>/metrics.json` (docs/02 §5) and
`reports/bench/<experiment>.json`, from which `eval.report` builds the report and
`--rescore` re-scores without re-running a single agent.

Refuses to run on keys nobody validated or on a LangSmith dataset that differs from the
committed jsonl: either would measure something other than the answer keys in the repo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.evaluators import EVALUATORS, METRIC_KEYS, composite, record_from_run, score_record
from eval.searchbench.schema import DATASET, BenchRecord, load_records
from eval.searchbench.sync import DATASET_NAME, check, plan_sync
from prime_search import events
from prime_search.agents.graph import _git_sha, run_prime
from prime_search.baseline import run_baseline
from prime_search.config import get_settings
from prime_search.schemas import RunRecord, RunRequest
from prime_search.workspace import Workspace

__all__ = ["BENCH_DIR", "BENCH_PROJECT", "experiment_prefix", "main", "make_target", "run_metadata"]

BENCH_DIR = Path("reports/bench")
# docs/01 §6: evaluation runs go to their own LangSmith project.
BENCH_PROJECT = "prime-search-bench"
# Dropped from the committed bench JSON (user decision, docs/11): the report and
# re-scoring need the answer, evidence, documents and usage; the trace holds the rest.
TRIM_FIELDS = ("tasks", "verdicts", "critic_reports")
# Rough per-question spend for --dry-run, from live 2.2/2.3 runs.
_TOKENS_PER_QUESTION = {"prime": 450_000, "baseline": 30_000}
_JUDGE_TOKENS_PER_QUESTION = 40_000


def experiment_prefix(mode: str, prompt_set: str, split: str, now: datetime) -> str:
    """docs/05 §3's `<mode>-<prompt_set>-<split>-<yyyymmdd-hhmm>`. The baseline has no
    prompt set, so its label is `none`; LangSmith appends a random suffix either way."""
    label = prompt_set if mode == "prime" else "none"
    return f"{mode}-{label}-{split}-{now:%Y%m%d-%H%M}"


def run_metadata(
    settings: Any, *, mode: str, depth: str, split: str, prompt_set: str, n: int, subset: bool
) -> dict[str, Any]:
    """docs/05 §3's `{git_sha, models, budget}` plus what the report must state."""
    prime = mode == "prime"
    return {
        "git_sha": _git_sha(),
        "models": settings.models.model_dump(),
        "budget": settings.budget(depth).model_dump() if prime else {"note": "starter agent; no budget"},
        # The baseline searches with raw TavilySearch, which is never cached (docs/03 §9).
        "tavily_cache": bool(settings.tavily_cache) if prime else False,
        "mode": mode,
        "depth": depth,
        "split": split,
        "prompt_set": prompt_set if prime else "none",
        "dataset_sha": hashlib.sha1(DATASET.read_bytes()).hexdigest()[:12],
        "evaluator_model": settings.models.evaluator,
        "n_examples": n,
        "subset": subset,
    }


def make_target(mode: str, depth: str, prompt_set: str, split: str) -> Callable[[dict], dict]:
    """The function `evaluate()` calls per example. Never raises: a failed run still
    returns what it left on disk, so it is scored as failed rather than dropped."""

    def target(inputs: dict) -> dict:
        settings = get_settings()
        request = RunRequest(
            question=inputs["question"],
            mode=mode,
            depth=depth,
            question_id=inputs.get("question_id"),
            prompt_set=prompt_set if mode == "prime" else "base",
        )
        ws = Workspace(objective=request.question, budget=settings.budget(depth))
        labels = {"ws": ws, "source": "bench", "extra_tags": [f"bench:{split}"], "project_name": BENCH_PROJECT}
        record: RunRecord | None = None
        error: str | None = None
        try:
            runner = run_prime if mode == "prime" else run_baseline
            record = runner(request, **labels)
        except Exception as exc:  # noqa: BLE001 - see docstring
            error = f"{type(exc).__name__}: {exc}"[:500]
            record = _saved_record(ws.run_id)
        return target_outputs(record, run_id=ws.run_id, error=error)

    return target


def _saved_record(run_id: str) -> RunRecord | None:
    path = events.run_dir(run_id) / "state.json"
    if not path.is_file():
        return None
    try:
        return RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - an unreadable record is no record
        return None


def target_outputs(record: RunRecord | None, *, run_id: str, error: str | None) -> dict[str, Any]:
    answer = record.answer if record is not None else None
    return {
        "run_id": run_id,
        "status": record.status if record is not None else "failed",
        "error": error or (record.error if record is not None else None),
        "langsmith_run_url": record.langsmith_run_url if record is not None else None,
        # Top-level text for LangSmith's compare view; evaluators read `record`.
        "answer": answer.body_markdown if answer is not None else None,
        "record": record.model_dump(mode="json") if record is not None else None,
    }


def trim_record(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not data:
        return None
    return {key: value for key, value in data.items() if key not in TRIM_FIELDS}


def _langsmith_score(item: Any) -> float | int | None:
    """The score, or the number `Score.to_langsmith` moved into `value` because it was
    outside LangSmith's score range (a prime run's tokens)."""
    if item.score is not None or not isinstance(item.value, str):
        return item.score
    try:
        number = float(item.value.replace(",", ""))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def rows_from_results(results: Any) -> list[dict[str, Any]]:
    """One row per example from LangSmith's `ExperimentResults`."""
    rows: list[dict[str, Any]] = []
    for result in results:
        run, example = result["run"], result["example"]
        outputs = getattr(run, "outputs", None) or {}
        scores: dict[str, dict[str, Any]] = {}
        for item in result["evaluation_results"]["results"]:
            scores[item.key] = {"score": _langsmith_score(item), "comment": item.comment, "metadata": item.metadata or {}}
        record = record_from_run(run)
        metadata = dict(getattr(example, "metadata", None) or {})
        rows.append(
            _row(
                question_id=metadata.get("id"),
                metadata=metadata,
                target_run_id=str(getattr(run, "id", "")),
                outputs=outputs,
                error=outputs.get("error") or getattr(run, "error", None),
                record=record,
                scores=scores,
            )
        )
    return rows


def _row(*, question_id, metadata, target_run_id, outputs, error, record, scores) -> dict[str, Any]:  # noqa: ANN001
    ordered = {key: scores[key] for key in METRIC_KEYS if key in scores}
    return {
        "question_id": question_id,
        "domain": metadata.get("domain"),
        "tier": metadata.get("tier"),
        "question_type": metadata.get("question_type"),
        "run_id": outputs.get("run_id"),
        "target_run_id": target_run_id,
        "status": outputs.get("status"),
        "error": error,
        "langsmith_run_url": outputs.get("langsmith_run_url"),
        "usage": record.usage.model_dump(mode="json") if record is not None else None,
        "scores": ordered,
        "composite": composite(ordered),
        "record": trim_record(outputs.get("record")),
    }


def write_outputs(payload: dict[str, Any]) -> Path:
    """`reports/bench/<experiment>.json` and each run's `metrics.json`."""
    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    path = BENCH_DIR / f"{payload['experiment_name']}.json"
    path.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    for row in payload["rows"]:
        if not row.get("run_id"):
            continue
        directory = events.run_dir(row["run_id"])
        directory.mkdir(parents=True, exist_ok=True)
        metrics = {
            "experiment_name": payload["experiment_name"],
            "experiment_url": payload.get("experiment_url"),
            "question_id": row["question_id"],
            "split": payload["config"]["split"],
            "scores": row["scores"],
            "composite": row["composite"],
            "evaluated_at": payload.get("rescored_at") or payload.get("finished_at"),
            "evaluator_git_sha": payload.get("evaluator_git_sha") or payload["metadata"].get("git_sha"),
        }
        (directory / "metrics.json").write_text(
            json.dumps(metrics, indent=1, default=str) + "\n", encoding="utf-8", newline="\n"
        )
    return path


def rescore(path: Path) -> int:
    """Re-score saved records with the current evaluators: judge calls only, no agent
    runs. LangSmith feedback keeps the original pass; the local JSON and report move."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    benches = {record.id: record for record in load_records()}
    for row in payload["rows"]:
        bench = benches.get(row["question_id"])
        if bench is None:
            print(f"skipped {row['question_id']}: not in the dataset", file=sys.stderr)
            continue
        record = RunRecord.model_validate(row["record"]) if row.get("record") else None
        scores = score_record(record, bench)
        row["scores"] = {
            key: {"score": score.score, "comment": score.comment, "metadata": score.metadata}
            for key, score in scores.items()
        }
        row["composite"] = composite(scores)
    payload["rescored_at"] = datetime.now(UTC).isoformat()
    payload["evaluator_git_sha"] = _git_sha()
    write_outputs(payload)
    print_table(payload["rows"])
    print(f"rescored {path}")
    return 0


def print_table(rows: Sequence[dict[str, Any]]) -> None:
    """ASCII only: this runs in a Windows console."""
    short = {
        "answer_correctness": "ac", "evidence_recall": "er", "citation_correctness": "cc",
        "citation_completeness": "cmp", "currency": "cur", "contradiction_handling": "con",
        "scope_handling": "scp", "primary_source_ratio": "psr", "search_cost": "cost",
        "latency_s": "sec", "tokens": "tok", "search_efficiency": "eff",
    }
    header = ["question".ljust(14)] + [short[key].rjust(6) for key in METRIC_KEYS] + ["  comp", " status"]
    print(" ".join(header))
    for row in rows:
        cells = [str(row["question_id"]).ljust(14)]
        for key in METRIC_KEYS:
            value = (row["scores"].get(key) or {}).get("score")
            cells.append(("-" if value is None else f"{value:.2f}" if isinstance(value, float) else str(value)).rjust(6))
        comp = row.get("composite")
        cells.append(("-" if comp is None else f"{comp:.2f}").rjust(6))
        cells.append(f" {row.get('status')}")
        print(" ".join(cells))


def _lenient_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except Exception:  # noqa: BLE001 - best effort on captured streams
                pass


def _client() -> Any:
    from langsmith import Client

    return Client()


def _evaluate(*args: Any, **kwargs: Any) -> Any:
    from langsmith import evaluate

    return evaluate(*args, **kwargs)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m eval.run_eval", description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("baseline", "prime"))
    parser.add_argument("--split", choices=("train", "dev", "holdout"))
    parser.add_argument("--prompt-set", choices=("base", "optimized"), default="base")
    parser.add_argument("--depth", choices=("fast", "deep"), default="deep")
    parser.add_argument("--ids", help="comma-separated record ids (a subset run, excluded from reports)")
    parser.add_argument("--concurrency", type=int, default=1, help="examples run at once (default 1)")
    parser.add_argument("--no-cache", action="store_true", help="turn the Tavily cache off")
    parser.add_argument("--dry-run", action="store_true", help="validate and show the plan; spend nothing")
    parser.add_argument("--rescore", help="re-score a saved reports/bench/<experiment>.json")
    args = parser.parse_args(argv)
    if not args.rescore and not (args.mode and args.split):
        parser.error("--mode and --split are required unless --rescore is given")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    _lenient_stdout()
    args = parse_args(argv)
    if args.rescore:
        return rescore(Path(args.rescore))

    records = load_records()
    problems = check(records)
    if problems:
        for problem in problems:
            print(f"refusing to run: {problem}", file=sys.stderr)
        return 1
    ids = {item.strip() for item in (args.ids or "").split(",") if item.strip()}
    selected: list[BenchRecord] = [
        record for record in records if record.split == args.split and (not ids or record.id in ids)
    ]
    if not selected:
        print(f"refusing to run: no records selected for split {args.split!r} {sorted(ids) or ''}", file=sys.stderr)
        return 1
    unvalidated = [record.id for record in selected if not record.answer_key.is_validated]
    if unvalidated:
        print(f"refusing to run: unvalidated keys {unvalidated}", file=sys.stderr)
        return 1

    if args.no_cache:
        os.environ["PRIME_TAVILY_CACHE"] = "false"
    get_settings.cache_clear()
    settings = get_settings()
    settings.export_sdk_env()
    now = datetime.now(UTC)
    prefix = experiment_prefix(args.mode, args.prompt_set, args.split, now)
    metadata = run_metadata(
        settings, mode=args.mode, depth=args.depth, split=args.split,
        prompt_set=args.prompt_set, n=len(selected), subset=bool(ids),
    )

    if args.dry_run:
        tokens = len(selected) * (_TOKENS_PER_QUESTION[args.mode] + _JUDGE_TOKENS_PER_QUESTION)
        print(f"experiment prefix: {prefix}")
        print(f"examples ({len(selected)}): {', '.join(record.id for record in selected)}")
        print(f"estimated tokens: ~{tokens:,} (agent + judge)")
        print(json.dumps(metadata, indent=1, default=str))
        return 0
    if not settings.langsmith_api_key:
        print("refusing to run: LANGSMITH_API_KEY is not set (run with --env-file .env)", file=sys.stderr)
        return 1

    client = _client()
    examples = [
        example
        for example in client.list_examples(dataset_name=DATASET_NAME, splits=[args.split])
        if not ids or (example.metadata or {}).get("id") in ids
    ]
    plan = plan_sync(selected, {str(example.id): example for example in examples})
    if plan.create or plan.update:
        print(
            f"refusing to run: LangSmith {DATASET_NAME} differs from the jsonl "
            f"({len(plan.create)} missing, {len(plan.update)} changed); run "
            "`uv run --env-file .env python -m eval.searchbench.sync` first",
            file=sys.stderr,
        )
        return 1

    started = datetime.now(UTC)
    results = _evaluate(
        make_target(args.mode, args.depth, args.prompt_set, args.split),
        data=examples,
        evaluators=EVALUATORS,
        experiment_prefix=prefix,
        metadata=metadata,
        description=f"SearchBench {args.split}: {args.mode} ({metadata['prompt_set']}, {args.depth})",
        max_concurrency=args.concurrency if args.concurrency > 1 else 0,  # 0 runs examples one at a time
        client=client,
        blocking=True,
    )
    rows = rows_from_results(results)
    payload = {
        "experiment_name": getattr(results, "experiment_name", prefix),
        "experiment_url": getattr(results, "url", None),
        "config": {"mode": args.mode, "prompt_set": metadata["prompt_set"], "split": args.split, "depth": args.depth},
        "metadata": metadata,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "rows": rows,
    }
    path = write_outputs(payload)
    print_table(rows)
    print(f"experiment: {payload['experiment_name']}  {payload['experiment_url'] or ''}")
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

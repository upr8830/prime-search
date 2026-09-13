"""The bench report (docs/05 §3).

    uv run python -m eval.report --split dev        # reports/dev-report.md
    uv run python -m eval.report                    # holdout -> reports/final-report.md
    uv run python -m eval.report --passes 2         # mean ± half-range over two passes

Reads only the local `reports/bench/<experiment>.json` files `eval.run_eval` writes, so the
report regenerates without spending a call. Also writes `reports/latest.json`, which the
`/bench` page reads (docs/07 §5).

Groups experiments by configuration (mode, prompt set, depth), keeps the latest N passes of
each, and never counts a subset run (`--ids`). Not-applicable scores are excluded from means;
a metric with no value at all renders as `—`, and the coverage line says which keys those are.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.evaluators import METRIC_KEYS
from eval.searchbench.schema import BenchRecord, load_records

__all__ = ["main", "prd_targets", "render_markdown", "summarize"]

BENCH_DIR = Path("reports/bench")
LATEST = Path("reports/latest.json")
INT_KEYS = {"search_cost", "tokens"}
BREAKDOWN_KEYS = ("answer_correctness", "evidence_recall", "citation_correctness", "citation_completeness", "currency")
EXCERPT_LINES = 40


def default_out(split: str) -> Path:
    return Path("reports/final-report.md") if split == "holdout" else Path(f"reports/{split}-report.md")


# --- loading and grouping ---------------------------------------------------------------


def load_experiments(bench_dir: Path, split: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in sorted(bench_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (payload.get("config") or {}).get("split") != split:
            continue
        if (payload.get("metadata") or {}).get("subset"):
            continue
        payload["_file"] = path.as_posix()
        found.append(payload)
    return found


def config_label(payload: dict[str, Any]) -> str:
    config = payload["config"]
    return f"{config['mode']}-{config.get('prompt_set') or 'none'}-{config.get('depth') or 'deep'}"


def group_configs(experiments: Sequence[dict[str, Any]], passes: int) -> dict[str, list[dict[str, Any]]]:
    """Latest `passes` experiments per configuration, baseline first."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for payload in experiments:
        groups[config_label(payload)].append(payload)
    ordered = sorted(groups, key=lambda label: (not label.startswith("baseline"), label))
    return {
        label: sorted(groups[label], key=lambda p: p.get("started_at") or "", reverse=True)[: max(1, passes)]
        for label in ordered
    }


# --- summarizing ------------------------------------------------------------------------


def _score(row: dict[str, Any], key: str) -> Any:
    return ((row.get("scores") or {}).get(key) or {}).get("score")


def _mean(values: Iterable[Any]) -> tuple[float | None, int]:
    present = [float(value) for value in values if value is not None]
    return (sum(present) / len(present), len(present)) if present else (None, 0)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _across_passes(passes: Sequence[dict[str, Any]], pick) -> dict[str, Any]:  # noqa: ANN001
    """Mean over passes of each pass's mean, with half the range as the spread."""
    means: list[float] = []
    count = 0
    for payload in passes:
        mean, n = pick(payload["rows"])
        if mean is not None:
            means.append(mean)
            count = max(count, n)
    if not means:
        return {"mean": None, "spread": None, "n": 0}
    spread = (max(means) - min(means)) / 2 if len(means) > 1 else None
    return {"mean": _round(sum(means) / len(means)), "spread": _round(spread), "n": count}


def _breakdown(rows: Sequence[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field))].append(row)
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(groups):
        items = groups[name]
        entry: dict[str, Any] = {"n": len(items)}
        for key in BREAKDOWN_KEYS:
            entry[key] = _round(_mean(_score(row, key) for row in items)[0])
        entry["composite"] = _round(_mean(row.get("composite") for row in items)[0])
        result[name] = entry
    return result


def summarize(label: str, passes: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latest = passes[0]
    rows = latest["rows"]
    metrics = {
        key: _across_passes(passes, lambda items, key=key: _mean(_score(row, key) for row in items))
        for key in METRIC_KEYS
    }
    scores = [score for row in rows for score in (row.get("scores") or {}).values()]
    return {
        "config": label,
        "mode": latest["config"]["mode"],
        "prompt_set": latest["config"].get("prompt_set"),
        "depth": latest["config"].get("depth"),
        "split": latest["config"]["split"],
        "experiments": [
            {
                "name": payload.get("experiment_name"),
                "url": payload.get("experiment_url"),
                "tavily_cache": (payload.get("metadata") or {}).get("tavily_cache"),
                "git_sha": (payload.get("metadata") or {}).get("git_sha"),
                "evaluator_model": (payload.get("metadata") or {}).get("evaluator_model"),
                "dataset_sha": (payload.get("metadata") or {}).get("dataset_sha"),
                "started_at": payload.get("started_at"),
                "rescored_at": payload.get("rescored_at"),
                "file": payload.get("_file"),
            }
            for payload in passes
        ],
        "n": len(rows),
        "metrics": metrics,
        "composite": _across_passes(passes, lambda items: _mean(row.get("composite") for row in items)),
        "per_tier": _breakdown(rows, "tier"),
        "per_domain": _breakdown(rows, "domain"),
        "judge_errors": sum(1 for score in scores if (score.get("metadata") or {}).get("error")),
        "failed_runs": sum(1 for row in rows if row.get("status") == "failed" or not row.get("record")),
        "judge_tokens": sum(int((score.get("metadata") or {}).get("judge_tokens") or 0) for score in scores),
        "missing_keys": [key for key in METRIC_KEYS if metrics[key]["n"] == 0],
        "_rows": rows,
    }


def prd_targets(summaries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """docs/00 §9's targets, each on the subset it is defined for."""
    baseline = next((s for s in summaries if s["mode"] == "baseline"), None)
    baseline_ac = baseline["metrics"]["answer_correctness"]["mean"] if baseline else None
    targets: list[dict[str, Any]] = []
    for summary in summaries:
        rows = summary["_rows"]
        adversarial = _mean(
            _score(row, "contradiction_handling") for row in rows if row.get("tier") == 4
        )
        change = _mean(_score(row, "currency") for row in rows if row.get("question_type") == "change_detection")
        checks = [
            ("contradiction_handling", "tier 4 with expected contradictions", adversarial, 0.6),
            ("currency", "change-detection questions", change, 0.8),
            ("evidence_recall", "all", (summary["metrics"]["evidence_recall"]["mean"], summary["metrics"]["evidence_recall"]["n"]), 0.75),
            ("citation_correctness", "all", (summary["metrics"]["citation_correctness"]["mean"], summary["metrics"]["citation_correctness"]["n"]), 0.85),
        ]
        for metric, subset, (value, n), target in checks:
            targets.append(_target(summary["config"], metric, subset, value, n, target))
        if summary["mode"] != "baseline" and baseline_ac is not None:
            mine = summary["metrics"]["answer_correctness"]["mean"]
            delta = None if mine is None else mine - baseline_ac
            targets.append(
                _target(summary["config"], "answer_correctness", "delta over baseline", delta,
                        summary["metrics"]["answer_correctness"]["n"], 0.25)
            )
    return targets


def _target(config: str, metric: str, subset: str, value: float | None, n: int, target: float) -> dict[str, Any]:
    return {
        "config": config, "metric": metric, "subset": subset, "value": _round(value), "n": n,
        "target": target, "met": None if value is None else value >= target,
    }


# --- rendering --------------------------------------------------------------------------


def _fmt(value: Any, key: str = "", spread: float | None = None) -> str:
    if value is None:
        return "—"
    if key in INT_KEYS:
        text = f"{round(value):,}"
    elif key == "latency_s":
        text = f"{value:.1f}"
    else:
        text = f"{value:.2f}"
    return f"{text} ± {spread:.2f}" if spread is not None else text


def _table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _cache_statement(summary: dict[str, Any]) -> str:
    if summary["mode"] == "baseline":
        return "uncached (raw TavilySearch, by construction)"
    flags = {experiment.get("tavily_cache") for experiment in summary["experiments"]}
    if flags == {True}:
        return "Tavily cache on"
    if flags == {False}:
        return "Tavily cache off"
    return "Tavily cache mixed across passes"


def coverage_line(summaries: Sequence[dict[str, Any]]) -> str:
    parts = []
    for summary in summaries:
        missing = summary["missing_keys"]
        parts.append(f"{summary['config']} ✓" if not missing else f"{summary['config']} missing {', '.join(missing)}")
    complete = all(not summary["missing_keys"] for summary in summaries)
    return f"All {len(METRIC_KEYS)} metric keys populated: {'yes' if complete else 'no'} — " + "; ".join(parts)


def _excerpt(row: dict[str, Any] | None) -> list[str]:
    record = (row or {}).get("record") or {}
    body = (record.get("answer") or {}).get("body_markdown") or ""
    if not body:
        return ["> (no answer)"]
    lines = body.splitlines()
    kept: list[str] = []
    keep = not any(line.startswith("## ") for line in lines)
    for line in lines:
        if line.startswith("## "):
            keep = line[3:].strip().lower().startswith(("answer", "criteria"))
        if keep:
            kept.append(line)
    kept = kept[:EXCERPT_LINES] or lines[:EXCERPT_LINES]
    return [f"> {line}" if line else ">" for line in kept]


def _examples(records: Sequence[BenchRecord]) -> list[tuple[str, BenchRecord]]:
    chosen: list[tuple[str, BenchRecord]] = []
    if records:
        chosen.append(("Easy", min(records, key=lambda record: (record.tier, record.id))))
    contradiction = next((r for r in records if r.question_type == "contradiction"), None) or next(
        (r for r in records if r.answer_key.expected_contradictions), None
    )
    if contradiction is not None:
        chosen.append(("Contradiction", contradiction))
    out_of_scope = next((r for r in records if r.question_type == "out_of_scope"), None)
    if out_of_scope is not None:
        chosen.append(("Out of scope", out_of_scope))
    return chosen


def render_markdown(
    split: str,
    summaries: Sequence[dict[str, Any]],
    targets: Sequence[dict[str, Any]],
    records: Sequence[BenchRecord],
    *,
    generated_at: str,
    passes: int,
) -> str:
    lines = [f"# SearchBench {split} report", ""]
    lines.append(
        f"Generated {generated_at} by `uv run python -m eval.report --split {split}"
        f"{' --passes ' + str(passes) if passes > 1 else ''}` from the local bench files listed below."
    )
    lines.append("")
    if split != "holdout":
        lines += [
            f"> The {split} split is a build-time check: n = {max((s['n'] for s in summaries), default=0)} "
            "questions per configuration, and several metrics rest on a single record. Not a result to quote.",
            "",
        ]
    lines += ["## Configurations", ""]
    for summary in summaries:
        lines.append(f"- **{summary['config']}** — n = {summary['n']}; {_cache_statement(summary)}")
        for experiment in summary["experiments"]:
            link = f"[{experiment['name']}]({experiment['url']})" if experiment.get("url") else f"`{experiment['name']}`"
            extra = f", rescored {experiment['rescored_at']}" if experiment.get("rescored_at") else ""
            lines.append(
                f"  - {link} — git `{experiment.get('git_sha')}`, evaluator `{experiment.get('evaluator_model')}`, "
                f"dataset `{experiment.get('dataset_sha')}`, file `{experiment.get('file')}`{extra}"
            )
    lines += ["", "## Coverage", "", coverage_line(summaries), ""]

    lines += ["## Headline", ""]
    header = ["config", "n", *METRIC_KEYS, "composite", "judge errors", "failed runs"]
    body_rows = []
    for summary in summaries:
        cells = [summary["config"], str(summary["n"])]
        for key in METRIC_KEYS:
            metric = summary["metrics"][key]
            cells.append(_fmt(metric["mean"], key, metric["spread"]))
        cells += [_fmt(summary["composite"]["mean"], "", summary["composite"]["spread"]),
                  str(summary["judge_errors"]), str(summary["failed_runs"])]
        body_rows.append(cells)
    lines += _table(header, body_rows) + [""]

    lines += ["## PRD targets (docs/00 §9)", ""]
    lines += _table(
        ["config", "metric", "subset", "value", "n", "target", "met"],
        (
            [t["config"], t["metric"], t["subset"], _fmt(t["value"]), str(t["n"]), f"{t['target']:.2f}",
             "—" if t["met"] is None else ("yes" if t["met"] else "no")]
            for t in targets
        ),
    ) + [""]

    for title, field in (("Per tier", "per_tier"), ("Per domain", "per_domain")):
        lines += [f"## {title}", ""]
        rows = []
        for summary in summaries:
            for name, entry in summary[field].items():
                rows.append([name, summary["config"], str(entry["n"]), *(_fmt(entry[key]) for key in BREAKDOWN_KEYS), _fmt(entry["composite"])])
        lines += _table([field.split("_")[1], "config", "n", *BREAKDOWN_KEYS, "composite"], rows) + [""]

    lines += ["## Per question", ""]
    rows = []
    question_ids = sorted({row["question_id"] for summary in summaries for row in summary["_rows"]})
    for question_id in question_ids:
        for summary in summaries:
            row = next((r for r in summary["_rows"] if r["question_id"] == question_id), None)
            if row is None:
                continue
            trace = f"[trace]({row['langsmith_run_url']})" if row.get("langsmith_run_url") else "—"
            rows.append([question_id, summary["config"], _fmt(row.get("composite")),
                         *(_fmt(_score(row, key)) for key in BREAKDOWN_KEYS), str(row.get("status")), trace])
    lines += _table(["question", "config", "composite", *BREAKDOWN_KEYS, "status", "trace"], rows) + [""]

    lines += ["## Worked examples", ""]
    for kind, record in _examples(records):
        lines += [f"### {kind}: `{record.id}` (tier {record.tier}, {record.question_type})", "",
                  f"**Question.** {record.question}", "", f"**Answer key.** {record.answer_key.summary}", ""]
        example_rows = []
        for summary in summaries:
            row = next((r for r in summary["_rows"] if r["question_id"] == record.id), None)
            example_rows.append([summary["config"], _fmt((row or {}).get("composite")),
                                 *(_fmt(_score(row, key)) if row else "—" for key in BREAKDOWN_KEYS)])
        lines += _table(["config", "composite", *BREAKDOWN_KEYS], example_rows) + [""]
        for summary in summaries:
            row = next((r for r in summary["_rows"] if r["question_id"] == record.id), None)
            trace = f" ([trace]({row['langsmith_run_url']}))" if row and row.get("langsmith_run_url") else ""
            lines += [f"**{summary['config']}**{trace}", "", *_excerpt(row), ""]

    lines += ["## Cost and latency", ""]
    cost_rows = []
    for summary in summaries:
        cells = [summary["config"]]
        for key in ("search_cost", "latency_s", "tokens", "search_efficiency"):
            values = [v for v in (_score(row, key) for row in summary["_rows"]) if v is not None]
            cells.append(_fmt(statistics.fmean(values) if values else None, key))
            cells.append(_fmt(statistics.median(values) if values else None, key))
        total = sum(v for v in (_score(row, "tokens") for row in summary["_rows"]) if v is not None)
        cells += [f"{total:,}", f"{summary['judge_tokens']:,}"]
        cost_rows.append(cells)
    lines += _table(
        ["config", "search_cost mean", "median", "latency_s mean", "median", "tokens mean", "median",
         "search_efficiency mean", "median", "agent tokens total", "judge tokens total"],
        cost_rows,
    ) + [""]

    lines += ["## Evaluator comments", ""]
    for question_id in question_ids:
        lines += [f"### `{question_id}`", ""]
        for summary in summaries:
            row = next((r for r in summary["_rows"] if r["question_id"] == question_id), None)
            if row is None:
                continue
            lines.append(f"**{summary['config']}**")
            lines.append("")
            for key in METRIC_KEYS:
                score = (row.get("scores") or {}).get(key)
                if score is not None:
                    comment = " ".join(str(score.get("comment") or "").split())
                    lines.append(f"- `{key}` {_fmt(score.get('score'), key)} — {comment}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def latest_payload(split: str, passes: int, summaries: Sequence[dict[str, Any]], targets: Sequence[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "split": split,
        "passes": passes,
        "sources": [experiment["file"] for summary in summaries for experiment in summary["experiments"]],
        "configs": [{key: value for key, value in summary.items() if not key.startswith("_")} for summary in summaries],
        "prd_targets": list(targets),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.report", description="SearchBench report (docs/05 §3)")
    parser.add_argument("--split", choices=("train", "dev", "holdout"), default="holdout")
    parser.add_argument("--passes", type=int, default=1, help="latest N experiments per configuration")
    parser.add_argument("--bench-dir", default=str(BENCH_DIR))
    parser.add_argument("--out", help="markdown path (default reports/final-report.md or reports/<split>-report.md)")
    parser.add_argument("--latest", default=str(LATEST), help="summary JSON for /bench")
    args = parser.parse_args(argv)

    experiments = load_experiments(Path(args.bench_dir), args.split)
    if not experiments:
        print(f"no bench experiments for split {args.split!r} in {args.bench_dir}", file=sys.stderr)
        return 1
    groups = group_configs(experiments, args.passes)
    summaries = [summarize(label, passes) for label, passes in groups.items()]
    targets = prd_targets(summaries)
    records = [record for record in load_records() if record.split == args.split]
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    out = Path(args.out) if args.out else default_out(args.split)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_markdown(args.split, summaries, targets, records, generated_at=generated_at, passes=args.passes),
        encoding="utf-8",
        newline="\n",
    )
    latest = Path(args.latest)
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(latest_payload(args.split, args.passes, summaries, targets, generated_at), indent=1, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    ascii_line = coverage_line(summaries).replace("✓", "ok").replace("—", "-")
    print(ascii_line)
    print(f"written: {out} and {latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

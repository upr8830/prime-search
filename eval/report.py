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
GEPA_REPORT = Path("reports/gepa-run.json")
# docs/05 §5: accept optimized prompts only if citation correctness drops by at most this.
ACCEPT_CITATION_DROP = 0.03
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
        # Every pass's rows, latest first, so subset targets average passes as the headline does.
        "_passes": [payload["rows"] for payload in passes],
    }


def prd_targets(summaries: Sequence[dict[str, Any]], gepa: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """docs/00 §9's targets, each on the subset it is defined for."""
    baseline = next((s for s in summaries if s["mode"] == "baseline"), None)
    baseline_ac = baseline["metrics"]["answer_correctness"]["mean"] if baseline else None
    targets: list[dict[str, Any]] = []
    for summary in summaries:
        passes = summary.get("_passes") or [summary["_rows"]]
        adversarial = _pass_mean(
            passes, lambda rows: _mean(_score(row, "contradiction_handling") for row in rows if row.get("tier") == 4)
        )
        change = _pass_mean(
            passes, lambda rows: _mean(_score(row, "currency") for row in rows if row.get("question_type") == "change_detection")
        )
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
    # docs/00 §9: "GEPA lift on held-out split: >= +0.05 answer correctness".
    lift = gepa_lift(summaries, gepa)
    if lift is not None:
        targets.append(_target(lift["config"], "gepa_lift", lift["subset"], lift["lift"], lift["n"], 0.05))
    return targets


def _pass_mean(passes: Sequence[Sequence[dict[str, Any]]], pick) -> tuple[float | None, int]:  # noqa: ANN001
    """A subset metric averaged over passes the way the headline is (`_across_passes`)."""
    result = _across_passes([{"rows": rows} for rows in passes], pick)
    return result["mean"], result["n"]


def gepa_outcome(path: Path | str = GEPA_REPORT) -> dict[str, Any] | None:
    """What task 3.1's GEPA run concluded (docs/05 §5), from `reports/gepa-run.json`."""
    source = Path(path)
    if not source.is_file():
        return None
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    keys = ("components", "total_metric_calls", "seed_dev_score", "best_dev_score", "improved_on_dev",
            "optimized_prompts_written", "run_dir", "git_sha")
    outcome = {key: data.get(key) for key in keys}
    # Candidate 0 is the seed: when no proposal wins, best_dev_score is the seed's own score,
    # so the proposals' best is reported separately rather than as "best 0.75 against base 0.75".
    proposals = [c.get("dev_score") for c in (data.get("candidates") or [])[1:] if c.get("dev_score") is not None]
    outcome["proposals"] = len((data.get("candidates") or [])[1:])
    outcome["best_proposal_dev_score"] = max(proposals) if proposals else None
    return outcome


def _prime(summaries: Sequence[dict[str, Any]], prompt_set: str) -> dict[str, Any] | None:
    return next((s for s in summaries if s["mode"] == "prime" and s.get("prompt_set") == prompt_set), None)


def gepa_lift(summaries: Sequence[dict[str, Any]], gepa: dict[str, Any] | None) -> dict[str, Any] | None:
    """docs/00 §9's GEPA lift and docs/05 §5's acceptance check.

    With no optimized experiment and a GEPA run that wrote no optimized prompts, PRIME + GEPA
    is the base prompts, so the lift is 0 by construction rather than unknown."""
    base = _prime(summaries, "base")
    optimized = _prime(summaries, "optimized")
    if base is None:
        return None
    if optimized is None:
        if gepa is None or gepa.get("improved_on_dev") or gepa.get("optimized_prompts_written"):
            return None
        return {
            "config": base["config"], "subset": "no optimized prompts (equals base)", "lift": 0.0,
            "citation_delta": 0.0, "accepted": False, "equals_base": True,
            "n": base["metrics"]["answer_correctness"]["n"],
        }

    def delta(key: str) -> float | None:
        mine, theirs = optimized["metrics"][key]["mean"], base["metrics"][key]["mean"]
        return None if mine is None or theirs is None else mine - theirs

    lift, citation = delta("answer_correctness"), delta("citation_correctness")
    accepted = None if lift is None or citation is None else lift > 0 and citation >= -ACCEPT_CITATION_DROP
    return {
        "config": optimized["config"], "subset": "optimized vs base", "lift": lift, "citation_delta": citation,
        "accepted": accepted, "equals_base": False, "n": optimized["metrics"]["answer_correctness"]["n"],
    }


def _signed(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}"


def gepa_lines(summaries: Sequence[dict[str, Any]], gepa: dict[str, Any] | None) -> list[str]:
    """The report's PRIME + GEPA section (docs/05 §5)."""
    base = _prime(summaries, "base")
    optimized = _prime(summaries, "optimized")
    lines: list[str] = []
    if gepa is not None:
        components = [str(name) for name in gepa.get("components") or []]
        named = " and ".join([", ".join(components[:-1]), components[-1]] if len(components) > 2 else components)
        proposals = gepa.get("proposals")
        if proposals is None:
            found = ""
        elif proposals == 0:
            found = " and made no proposal"
        else:
            found = (
                f" and made {proposals} proposal{'s' if proposals != 1 else ''}; the best scored "
                f"{_fmt(gepa.get('best_proposal_dev_score'))} on dev"
            )
        lines.append(
            f"GEPA (task 3.1) optimized {named or 'no prompts'} with {gepa.get('total_metric_calls')} metric calls{found}. "
            f"The base prompts scored {_fmt(gepa.get('seed_dev_score'))} on dev (`reports/gepa-run.json`)."
        )
    if optimized is None:
        lift = gepa_lift(summaries, gepa)
        if lift is not None and lift["equals_base"]:
            lines.append(
                f"No candidate beat base on dev, so GEPA wrote no optimized prompts and PRIME + GEPA is "
                f"`{lift['config']}`. It was not run separately; its lift is 0 by construction (docs/05 §5)."
            )
        else:
            lines.append("There is no `prime-optimized` experiment on this split.")
        return lines
    if base is None:
        lines.append(f"`{optimized['config']}` has no `prime-base` experiment on this split to compare with.")
        return lines
    lift = gepa_lift(summaries, gepa) or {}
    verdict = {True: "accepted", False: "not accepted"}.get(lift.get("accepted"), "undecided")
    lines.append(
        f"`{optimized['config']}` against `{base['config']}`: answer_correctness {_signed(lift.get('lift'))}, "
        f"citation_correctness {_signed(lift.get('citation_delta'))}."
    )
    lines.append(
        "docs/05 §5 acceptance (answer correctness improves and citation correctness drops at most "
        f"{ACCEPT_CITATION_DROP:.2f}): {verdict}."
    )
    return lines


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
    gepa: dict[str, Any] | None = None,
) -> str:
    lines = [f"# SearchBench {split} report", ""]
    latest_note = (
        [f"_From the latest pass of each configuration; the headline and PRD targets average all {passes} passes._", ""]
        if passes > 1 else []
    )
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

    if gepa is not None or _prime(summaries, "optimized") is not None:
        lines += ["## PRIME + GEPA", "", *gepa_lines(summaries, gepa), ""]

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
        lines += [f"## {title}", "", *latest_note]
        rows = []
        for summary in summaries:
            for name, entry in summary[field].items():
                rows.append([name, summary["config"], str(entry["n"]), *(_fmt(entry[key]) for key in BREAKDOWN_KEYS), _fmt(entry["composite"])])
        lines += _table([field.split("_")[1], "config", "n", *BREAKDOWN_KEYS, "composite"], rows) + [""]

    lines += ["## Per question", "", *latest_note]
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

    lines += ["## Worked examples", "", *latest_note]
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

    lines += ["## Cost and latency", "", *latest_note]
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


def latest_payload(
    split: str, passes: int, summaries: Sequence[dict[str, Any]], targets: Sequence[dict[str, Any]], generated_at: str,
    gepa: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "split": split,
        "passes": passes,
        "sources": [experiment["file"] for summary in summaries for experiment in summary["experiments"]],
        "configs": [{key: value for key, value in summary.items() if not key.startswith("_")} for summary in summaries],
        "prd_targets": list(targets),
        "gepa": gepa,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.report", description="SearchBench report (docs/05 §3)")
    parser.add_argument("--split", choices=("train", "dev", "holdout"), default="holdout")
    parser.add_argument("--passes", type=int, default=1, help="latest N experiments per configuration")
    parser.add_argument("--bench-dir", default=str(BENCH_DIR))
    parser.add_argument("--out", help="markdown path (default reports/final-report.md or reports/<split>-report.md)")
    parser.add_argument("--latest", default=str(LATEST), help="summary JSON for /bench")
    parser.add_argument("--gepa", default=str(GEPA_REPORT), help="GEPA run report (docs/05 §5)")
    args = parser.parse_args(argv)

    experiments = load_experiments(Path(args.bench_dir), args.split)
    if not experiments:
        print(f"no bench experiments for split {args.split!r} in {args.bench_dir}", file=sys.stderr)
        return 1
    groups = group_configs(experiments, args.passes)
    summaries = [summarize(label, passes) for label, passes in groups.items()]
    gepa = gepa_outcome(args.gepa)
    targets = prd_targets(summaries, gepa)
    records = [record for record in load_records() if record.split == args.split]
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    out = Path(args.out) if args.out else default_out(args.split)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_markdown(args.split, summaries, targets, records, generated_at=generated_at, passes=args.passes, gepa=gepa),
        encoding="utf-8",
        newline="\n",
    )
    latest = Path(args.latest)
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(latest_payload(args.split, args.passes, summaries, targets, generated_at, gepa), indent=1, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    ascii_line = coverage_line(summaries).replace("✓", "ok").replace("—", "-")
    print(ascii_line)
    print(f"written: {out} and {latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

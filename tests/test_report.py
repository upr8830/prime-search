"""The bench report (docs/05 §3), built from hand-made bench JSON payloads."""

from __future__ import annotations

import json

import pytest

from eval import report
from eval.evaluators import METRIC_KEYS
from eval.searchbench.schema import load_records


def _row(question_id: str, *, tier: int = 2, domain: str = "cgm", question_type: str = "eligibility",
         scores: dict | None = None, status: str = "completed", composite: float | None = 0.5,
         body: str = "## Answer\n\nCovered [1].", error: bool = False) -> dict:
    values = {key: 0.5 for key in METRIC_KEYS}
    values.update(scores or {})
    return {
        "question_id": question_id, "domain": domain, "tier": tier, "question_type": question_type,
        "run_id": f"run-{question_id}", "status": status,
        "langsmith_run_url": f"https://smith.langchain.com/r/{question_id}",
        "scores": {
            key: {"score": value, "comment": f"{key} comment", "metadata": {"error": True} if error and key == "answer_correctness" else {"judge_tokens": 10}}
            for key, value in values.items()
        },
        "composite": composite,
        "record": {"answer": {"body_markdown": body}},
    }


def _payload(name: str, mode: str = "prime", *, started: str = "2026-09-13T10:00:00", rows=None,  # noqa: ANN001
             cache: bool = True, subset: bool = False, split: str = "dev") -> dict:
    return {
        "experiment_name": name, "experiment_url": f"https://smith.langchain.com/e/{name}",
        "config": {"mode": mode, "prompt_set": "base" if mode == "prime" else "none", "split": split, "depth": "deep"},
        "metadata": {"tavily_cache": cache if mode == "prime" else False, "subset": subset, "git_sha": "abc",
                     "evaluator_model": "moonshotai/Kimi-K2.6", "dataset_sha": "d1"},
        "started_at": started, "rows": rows if rows is not None else [_row("q1")],
    }


def _summaries(*payloads, passes: int = 1) -> list[dict]:  # noqa: ANN002
    groups = report.group_configs(list(payloads), passes)
    return [report.summarize(label, items) for label, items in groups.items()]


def test_the_latest_experiment_per_config_wins() -> None:
    old = _payload("old", started="2026-09-13T09:00:00", rows=[_row("q1", scores={"answer_correctness": 0.1})])
    new = _payload("new", started="2026-09-13T11:00:00", rows=[_row("q1", scores={"answer_correctness": 0.9})])
    (summary,) = _summaries(old, new)
    assert summary["metrics"]["answer_correctness"]["mean"] == 0.9
    assert [e["name"] for e in summary["experiments"]] == ["new"]


def test_two_passes_report_the_mean_and_half_range() -> None:
    first = _payload("p1", started="2026-09-13T09:00:00", rows=[_row("q1", scores={"answer_correctness": 0.6})])
    second = _payload("p2", started="2026-09-13T11:00:00", rows=[_row("q1", scores={"answer_correctness": 0.8})])
    (summary,) = _summaries(first, second, passes=2)
    metric = summary["metrics"]["answer_correctness"]
    assert (metric["mean"], metric["spread"]) == (0.7, 0.1)


def test_not_applicable_scores_are_excluded_and_an_empty_metric_renders_as_a_dash() -> None:
    rows = [_row("q1", scores={"scope_handling": None, "currency": None}), _row("q2", scores={"scope_handling": None, "currency": 1.0})]
    summaries = _summaries(_payload("p", rows=rows))
    assert summaries[0]["metrics"]["currency"] == {"mean": 1.0, "spread": None, "n": 1}
    assert summaries[0]["missing_keys"] == ["scope_handling"]
    text = report.render_markdown("dev", summaries, report.prd_targets(summaries), [], generated_at="now", passes=1)
    assert "—" in text


def test_the_coverage_line_names_missing_keys() -> None:
    complete = _payload("b", mode="baseline")
    incomplete = _payload("p", rows=[_row("q1", scores={"scope_handling": None})])
    line = report.coverage_line(_summaries(complete, incomplete))
    assert line.startswith("All 12 metric keys populated: no")
    assert "baseline-none-deep ✓" in line and "prime-base-deep missing scope_handling" in line


def test_subset_runs_are_left_out(tmp_path) -> None:
    (tmp_path / "a.json").write_text(json.dumps(_payload("full")), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(_payload("subset", subset=True)), encoding="utf-8")
    (tmp_path / "c.json").write_text(json.dumps(_payload("holdout", split="holdout")), encoding="utf-8")
    assert [p["experiment_name"] for p in report.load_experiments(tmp_path, "dev")] == ["full"]


def test_worked_examples_are_easy_contradiction_and_out_of_scope() -> None:
    dev = [record for record in load_records() if record.split == "dev"]
    assert [(kind, record.id) for kind, record in report._examples(dev)] == [
        ("Easy", "cgm-elig-004"), ("Contradiction", "adv-glp1-002"), ("Out of scope", "oos-003"),
    ]


def test_prd_targets_use_their_subsets() -> None:
    rows = [
        _row("adv", tier=4, question_type="contradiction", scores={"contradiction_handling": 1.0}),
        _row("chg", tier=3, question_type="change_detection", scores={"currency": 0.4, "contradiction_handling": None}),
        _row("elig", tier=2, scores={"contradiction_handling": 0.0, "currency": 1.0}),
    ]
    summaries = _summaries(_payload("b", mode="baseline", rows=[_row("x", scores={"answer_correctness": 0.2})]), _payload("p", rows=rows))
    targets = {(t["config"], t["metric"], t["subset"]): t for t in report.prd_targets(summaries)}
    assert targets[("prime-base-deep", "contradiction_handling", "tier 4 with expected contradictions")]["value"] == 1.0
    assert targets[("prime-base-deep", "currency", "change-detection questions")]["value"] == 0.4
    assert targets[("prime-base-deep", "answer_correctness", "delta over baseline")]["value"] == 0.3


def test_the_report_states_the_cache_per_config() -> None:
    summaries = _summaries(_payload("b", mode="baseline"), _payload("p", cache=True))
    text = report.render_markdown("dev", summaries, report.prd_targets(summaries), [], generated_at="now", passes=1)
    assert "uncached (raw TavilySearch, by construction)" in text
    assert "Tavily cache on" in text


def test_main_writes_the_dev_report_and_latest_json(tmp_path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    rows = [_row("cgm-elig-004", tier=1), _row("oos-003", tier=4, domain="other", question_type="out_of_scope")]
    (bench / "b.json").write_text(json.dumps(_payload("b", mode="baseline", rows=rows)), encoding="utf-8")
    (bench / "p.json").write_text(json.dumps(_payload("p", rows=rows)), encoding="utf-8")
    out, latest = tmp_path / "dev-report.md", tmp_path / "latest.json"

    assert report.main(["--split", "dev", "--bench-dir", str(bench), "--out", str(out), "--latest", str(latest)]) == 0
    text = out.read_text(encoding="utf-8")
    for heading in ("## Coverage", "## Headline", "## PRD targets", "## Per tier", "## Per domain",
                    "## Per question", "## Worked examples", "## Cost and latency", "## Evaluator comments"):
        assert heading in text
    payload = json.loads(latest.read_text(encoding="utf-8"))
    config = payload["configs"][0]
    assert config["config"] == "baseline-none-deep"
    assert {"metrics", "per_tier", "per_domain", "experiments", "composite"} <= set(config)
    assert config["experiments"][0]["url"].startswith("https://")
    assert "_rows" not in config


def test_main_reports_no_experiments(tmp_path, capsys) -> None:
    assert report.main(["--split", "dev", "--bench-dir", str(tmp_path)]) == 1
    assert "no bench experiments" in capsys.readouterr().err


# --- PRIME + GEPA (docs/05 §5, task 3.2) ------------------------------------------------------

GEPA_NO_WIN = {
    "components": ["plan", "judge"], "total_metric_calls": 16, "seed_dev_score": 0.7512, "best_dev_score": 0.7069,
    "improved_on_dev": False, "optimized_prompts_written": [], "run_dir": "runs/gepa/x", "git_sha": "abc",
}


def test_gepa_outcome_reads_the_run_report_and_tolerates_its_absence(tmp_path) -> None:
    path = tmp_path / "gepa-run.json"
    path.write_text(json.dumps({**GEPA_NO_WIN, "candidates": [], "rollouts": []}), encoding="utf-8")
    assert report.gepa_outcome(path) == GEPA_NO_WIN
    assert report.gepa_outcome(tmp_path / "missing.json") is None


def test_without_optimized_prompts_prime_plus_gepa_is_base_and_its_lift_is_zero() -> None:
    summaries = _summaries(_payload("b", mode="baseline", split="holdout"), _payload("p", split="holdout"))
    targets = report.prd_targets(summaries, GEPA_NO_WIN)
    (lift,) = [t for t in targets if t["metric"] == "gepa_lift"]
    assert (lift["config"], lift["value"], lift["target"], lift["met"]) == ("prime-base-deep", 0.0, 0.05, False)
    assert lift["subset"] == "no optimized prompts (equals base)"

    text = report.render_markdown("holdout", summaries, targets, [], generated_at="now", passes=2, gepa=GEPA_NO_WIN)
    section = text.split("## PRIME + GEPA", 1)[1].split("## PRD targets", 1)[0]
    assert "GEPA wrote no optimized prompts" in section and "`prime-base-deep`" in section
    assert "16 metric calls" in section


def test_an_optimized_config_gets_its_lift_and_the_acceptance_check() -> None:
    base = _payload("p", split="holdout", rows=[_row("q1", scores={"answer_correctness": 0.60, "citation_correctness": 0.80})])
    optimized = _payload("o", split="holdout", rows=[_row("q1", scores={"answer_correctness": 0.70, "citation_correctness": 0.78})])
    optimized["config"]["prompt_set"] = "optimized"
    improved = {**GEPA_NO_WIN, "improved_on_dev": True, "optimized_prompts_written": ["prime_search/prompts/optimized/plan.md"]}
    summaries = _summaries(_payload("b", mode="baseline", split="holdout"), base, optimized)

    lift = report.gepa_lift(summaries, improved)
    assert lift["lift"] == pytest.approx(0.10) and lift["citation_delta"] == pytest.approx(-0.02)
    assert lift["accepted"] is True
    (row,) = [t for t in report.prd_targets(summaries, improved) if t["metric"] == "gepa_lift"]
    assert (row["config"], row["met"]) == ("prime-optimized-deep", True)
    text = report.render_markdown("holdout", summaries, [], [], generated_at="now", passes=1, gepa=improved)
    assert "citation correctness drops at most 0.03): accepted." in text


def test_a_citation_drop_past_the_guardrail_is_not_accepted() -> None:
    base = _payload("p", split="holdout", rows=[_row("q1", scores={"answer_correctness": 0.60, "citation_correctness": 0.80})])
    optimized = _payload("o", split="holdout", rows=[_row("q1", scores={"answer_correctness": 0.70, "citation_correctness": 0.70})])
    optimized["config"]["prompt_set"] = "optimized"
    summaries = _summaries(base, optimized)
    assert report.gepa_lift(summaries, None)["accepted"] is False


def test_main_passes_the_gepa_outcome_to_the_report_and_latest_json(tmp_path) -> None:
    bench = tmp_path / "bench"
    bench.mkdir()
    rows = [_row("cgm-elig-003", tier=2)]
    (bench / "b.json").write_text(json.dumps(_payload("b", mode="baseline", rows=rows, split="holdout")), encoding="utf-8")
    (bench / "p.json").write_text(json.dumps(_payload("p", rows=rows, split="holdout")), encoding="utf-8")
    gepa = tmp_path / "gepa-run.json"
    gepa.write_text(json.dumps(GEPA_NO_WIN), encoding="utf-8")
    out, latest = tmp_path / "final-report.md", tmp_path / "latest.json"
    args = ["--split", "holdout", "--bench-dir", str(bench), "--out", str(out), "--latest", str(latest)]

    assert report.main([*args, "--gepa", str(gepa)]) == 0
    assert "## PRIME + GEPA" in out.read_text(encoding="utf-8")
    assert json.loads(latest.read_text(encoding="utf-8"))["gepa"]["improved_on_dev"] is False

    assert report.main([*args, "--gepa", str(tmp_path / "missing.json")]) == 0
    assert "## PRIME + GEPA" not in out.read_text(encoding="utf-8")
    assert json.loads(latest.read_text(encoding="utf-8"))["gepa"] is None

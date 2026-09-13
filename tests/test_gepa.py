"""The GEPA adapter and runner (docs/05 §5), offline: the runner and the scorer are fakes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from eval.evaluators import Score
from eval.gepa import run_gepa
from eval.gepa.adapter import GEPA_PROJECT, PrimeAdapter, candidate_problems, prompt_set_name
from eval.searchbench.schema import load_records
from prime_search import prompts
from prime_search.config import Budget
from prime_search.schemas import (
    Answer,
    Branch,
    QueryUnderstanding,
    RunRecord,
    SearchPlan,
    Verdict,
)

RECORDS = load_records()
TRAIN = [record for record in RECORDS if record.split == "train"]
HOLDOUT = [record for record in RECORDS if record.split == "holdout"]


def _record(request, run_id: str) -> RunRecord:  # noqa: ANN001
    understanding = QueryUnderstanding(
        normalized_question="q", domain="cgm", question_type="eligibility", time_sensitivity="high"
    )
    return RunRecord(
        run_id=run_id,
        request=request,
        started_at=datetime.now(UTC),
        status="completed",
        plan=SearchPlan(
            understanding=understanding,
            branches=[Branch(branch_id="b1", question="criteria?", rationale="r", source_hint="primary_policy", priority=1)],
            stop_criteria="criteria cited",
            budget=Budget(),
        ),
        verdicts=[
            Verdict(round=1, sufficient=False, coverage={"b1": "partial"}, missing=["the revision date"], new_tasks=[], reasoning="dates missing")
        ],
        answer=Answer(
            summary="Covered.", body_markdown="## Answer\nCovered.", claims=[], citations=[],
            effective_dates=[], contradictions=[], unknowns=[], confidence=0.5,
        ),
    )


@pytest.fixture
def fakes():
    calls: list[dict] = []

    def runner(request, **kwargs):  # noqa: ANN001, ANN003, ANN202
        calls.append({"request": request, **kwargs})
        return _record(request, kwargs["ws"].run_id)

    def scorer(record, bench):  # noqa: ANN001, ANN202
        return {
            "answer_correctness": Score("answer_correctness", 0.5, "claims 1/2 weighted present; missing: c2"),
            "search_cost": Score("search_cost", 10, "6 searches + 4 fetches"),
        }

    return SimpleNamespace(calls=calls, runner=runner, scorer=scorer)


def _candidate(extra: str = "") -> dict[str, str]:
    return {"plan": prompts.load("plan") + extra, "judge": prompts.load("judge")}


def test_a_candidate_runs_under_its_own_prompt_set_with_the_capped_budget(fakes) -> None:
    budget = Budget(max_searches=20, max_agents=4)
    adapter = PrimeAdapter(TRAIN, budget=budget, concurrency=2, runner=fakes.runner, scorer=fakes.scorer)
    candidate = _candidate("\nPrefer the coding article for code questions.")
    name = prompt_set_name(candidate)
    try:
        batch = adapter.evaluate(TRAIN[:2], candidate, capture_traces=True)
        assert prompts.load("plan", name).endswith("Prefer the coding article for code questions.")
    finally:
        prompts.unregister_prompt_set(name)

    assert batch.scores == [0.5, 0.5]  # docs/05 §2's composite of the fake scores
    assert {call["prompt_set"] for call in fakes.calls} == {name}
    assert {call["source"] for call in fakes.calls} == {"gepa"}
    assert {call["project_name"] for call in fakes.calls} == {GEPA_PROJECT}
    assert all(call["request"].budget_override == budget for call in fakes.calls)
    assert {call["request"].question_id for call in fakes.calls} == {TRAIN[0].id, TRAIN[1].id}
    assert "b1 [primary_policy, priority 1]" in batch.trajectories[0].plan
    assert "round 1: insufficient" in batch.trajectories[0].judge
    assert [entry["prompt_set"] for entry in adapter.log] == [name, name]


def test_holdout_records_are_refused_before_anything_runs(fakes) -> None:
    adapter = PrimeAdapter(RECORDS, budget=Budget(), runner=fakes.runner, scorer=fakes.scorer)
    with pytest.raises(ValueError, match="holdout"):
        adapter.evaluate([TRAIN[0], HOLDOUT[0]], _candidate())
    assert fakes.calls == []


def test_a_candidate_that_drops_a_placeholder_scores_zero_without_running(fakes) -> None:
    candidate = {"plan": prompts.load("plan").replace("{budget}", "the budget"), "judge": prompts.load("judge")}
    assert any("{budget}" in problem for problem in candidate_problems(candidate))
    adapter = PrimeAdapter(TRAIN, budget=Budget(), runner=fakes.runner, scorer=fakes.scorer)
    batch = adapter.evaluate(TRAIN[:3], candidate, capture_traces=True)
    assert batch.scores == [0.0, 0.0, 0.0]
    assert batch.num_metric_calls == 0  # nothing ran, so nothing counts against the budget
    assert fakes.calls == []
    assert "was not run" in batch.trajectories[0].feedback


def test_the_reflective_dataset_pairs_each_components_output_with_the_feedback(fakes) -> None:
    adapter = PrimeAdapter(TRAIN, budget=Budget(), runner=fakes.runner, scorer=fakes.scorer)
    candidate = _candidate()
    try:
        batch = adapter.evaluate(TRAIN[:1], candidate, capture_traces=True)
    finally:
        prompts.unregister_prompt_set(prompt_set_name(candidate))
    dataset = adapter.make_reflective_dataset(candidate, batch, ["plan", "judge"])

    assert set(dataset) == {"plan", "judge"}
    (plan_item,) = dataset["plan"]
    assert plan_item["Inputs"]["question"] == TRAIN[0].question
    assert "stop criteria: criteria cited" in plan_item["Generated Outputs"]
    assert "missing: the revision date" in dataset["judge"][0]["Generated Outputs"]
    assert "composite score 0.50" in plan_item["Feedback"] and "missing: c2" in plan_item["Feedback"]
    json.dumps(dataset)  # GEPA serializes it into the reflection prompt


def test_a_record_already_run_with_a_candidate_is_reused_not_paid_again(fakes) -> None:
    """GEPA re-evaluates a parent on each minibatch and caches only dev (spec review)."""
    adapter = PrimeAdapter(TRAIN, budget=Budget(), runner=fakes.runner, scorer=fakes.scorer)
    candidate = _candidate()
    try:
        first = adapter.evaluate(TRAIN[:3], candidate)
        second = adapter.evaluate(TRAIN[1:4], candidate, capture_traces=True)
    finally:
        prompts.unregister_prompt_set(prompt_set_name(candidate))
    assert (first.num_metric_calls, second.num_metric_calls) == (3, 1)
    assert len(fakes.calls) == 4
    assert second.trajectories[0].run_id == first.outputs[1].run_id
    assert len(adapter.log) == 4  # paid rollouts only


def test_the_rollout_log_and_reuse_survive_a_resume(fakes) -> None:
    candidate = _candidate()
    adapter = PrimeAdapter(TRAIN, budget=Budget(), runner=fakes.runner, scorer=fakes.scorer)
    adapter.started_at = "2026-09-14T10:00:00+00:00"
    try:
        adapter.evaluate(TRAIN[:2], candidate)
        state = adapter.get_adapter_state()
        json.dumps(state)  # GEPA writes it into its checkpoint

        resumed = PrimeAdapter(TRAIN, budget=Budget(), runner=fakes.runner, scorer=fakes.scorer)
        resumed.started_at = "a later start"
        resumed.set_adapter_state(state)
        assert resumed.log == adapter.log and resumed.started_at == "2026-09-14T10:00:00+00:00"
        batch = resumed.evaluate(TRAIN[:2], candidate)
    finally:
        prompts.unregister_prompt_set(prompt_set_name(candidate))
    assert batch.num_metric_calls == 0 and len(fakes.calls) == 2


def test_gepa_proposes_and_keeps_a_better_candidate_through_the_adapter(tmp_path) -> None:
    """End to end with the real `gepa.optimize` and fake runs. Spec review: without
    `propose_new_texts` on the adapter, GEPA 0.1.4 made no candidate and never called the
    reflection model, and the tests that called the adapter directly could not see it."""
    import gepa

    train = TRAIN[:4]
    dev = [record for record in RECORDS if record.split == "dev"][:2]
    reflections: list[str] = []

    def runner(request, **kwargs):  # noqa: ANN001, ANN003, ANN202
        record = _record(request, kwargs["ws"].run_id)
        prompt_set = kwargs["prompt_set"]
        edited = "Rule " in prompts.load("plan", prompt_set) + prompts.load("judge", prompt_set)
        record.usage.searches = 1 if edited else 0
        return record

    def scorer(record, bench):  # noqa: ANN001, ANN202
        value = 0.9 if record.usage.searches == 1 else 0.3
        return {
            "answer_correctness": Score("answer_correctness", value, "claims present" if value > 0.5 else "missing: c1"),
            "search_cost": Score("search_cost", 0, "0 calls"),
        }

    def reflect(prompt):  # noqa: ANN001, ANN202
        target = "plan" if "{workspace_api}" in str(prompt) else "judge"
        reflections.append(target)
        return "```\n" + prompts.load(target) + f"\nRule {len(reflections)}.\n```"

    adapter = PrimeAdapter([*train, *dev], budget=Budget(), concurrency=2, runner=runner, scorer=scorer)
    seed = {"plan": prompts.load("plan"), "judge": prompts.load("judge")}
    result = gepa.optimize(
        seed_candidate=seed,
        trainset=train,
        valset=dev,
        adapter=adapter,
        reflection_lm=reflect,
        reflection_prompt_template=prompts.load("gepa_reflection"),
        reflection_minibatch_size=2,
        candidate_selection_strategy="pareto",
        module_selector="round_robin",
        max_metric_calls=14,
        cache_evaluation=True,
        run_dir=str(tmp_path / "gepa"),
        seed=0,
        raise_on_exception=True,
    )

    assert reflections, "the reflection model was never called"
    assert len(result.candidates) > 1
    best = result.candidates[result.best_idx]
    assert result.val_aggregate_scores[result.best_idx] > result.val_aggregate_scores[0]
    assert "Rule " in best["plan"] + best["judge"]
    assert not candidate_problems(best)  # the fenced code inside plan.md survived extraction
    # GEPA's engine counts every dev record it sends, even one the adapter reuses, so its
    # count is never below the paid runs: the cap can stop early, never overspend.
    assert 0 < len(adapter.log) <= result.total_metric_calls


def test_the_runner_refuses_holdout_and_any_split_but_train(capsys) -> None:
    assert run_gepa.main(["--split", "holdout"]) == 1
    assert "holdout is never used" in capsys.readouterr().err
    assert run_gepa.main(["--split", "dev"]) == 1
    assert run_gepa.main(["--components", "plan,synthesize"]) == 1


def test_a_dry_run_prints_the_plan_and_estimate_and_spends_nothing(offline_credentials, monkeypatch, capsys) -> None:
    def spend(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("a dry run must not optimize")

    monkeypatch.setattr(run_gepa.gepa, "optimize", spend)
    assert run_gepa.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "GEPA on plan, judge: train 15 records, dev 5" in out
    assert "max metric calls 60" in out
    assert "20 searches, 4 agents per round" in out
    assert "estimated cost $36-$57" in out
    assert "up to 11 more past the cap" in out


def _result(seed: dict[str, str], best: dict[str, str], scores: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        candidates=[seed, best],
        parents=[[None], [0]],
        val_aggregate_scores=scores,
        val_subscores=[{0: scores[0]}, {0: scores[1]}],
        discovery_eval_counts=[5, 23],
        per_val_instance_best_candidates={0: {scores.index(max(scores))}},
        total_metric_calls=60,
        num_full_val_evals=2,
        best_idx=scores.index(max(scores)),
    )


def _report(result, seed):  # noqa: ANN001, ANN202
    now = datetime.now(UTC)
    return run_gepa.build_report(
        result, seed=seed, components=["plan", "judge"], train_ids=["t1"], dev_ids=["d1"], rollouts=[],
        info={"git_sha": "abc"}, max_metric_calls=60, minibatch=3, run_dir="runs/gepa/x", started_at=now, finished_at=now,
    )


def test_optimized_prompts_are_written_only_for_a_candidate_that_beat_base_on_dev(tmp_path) -> None:
    seed = {"plan": "PLAN {objective}\n", "judge": "JUDGE {branches}\n"}
    better = {"plan": "PLAN {objective}\nExtra rule.\n", "judge": seed["judge"]}
    optimized, report_path = tmp_path / "optimized", tmp_path / "gepa-run.json"
    optimized.mkdir()
    (optimized / "judge.md").write_text("an older optimized judge", encoding="utf-8")

    result = _result(seed, better, [0.50, 0.62])
    report = run_gepa.write_artifacts(
        result, _report(result, seed), seed=seed, components=["plan", "judge"], optimized_dir=optimized, report_path=report_path
    )
    assert report["improved_on_dev"] is True
    assert (optimized / "plan.md").read_text(encoding="utf-8") == better["plan"]
    assert not (optimized / "judge.md").exists()  # the set is exactly the best candidate
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["candidates"][1]["changed"] == ["plan"]
    assert "+Extra rule." in saved["candidates"][1]["diff"]["plan"]
    assert saved["pareto_front"] == {"d1": [1]}

    (optimized / "plan.md").unlink()
    worse = _result(seed, better, [0.50, 0.41])
    report = run_gepa.write_artifacts(
        worse, _report(worse, seed), seed=seed, components=["plan", "judge"], optimized_dir=optimized, report_path=report_path
    )
    assert report["improved_on_dev"] is False and report["optimized_prompts_written"] == []
    assert not (optimized / "plan.md").exists()


def test_the_reflection_template_keeps_gepas_slots_and_the_placeholder_rule() -> None:
    template = prompts.load("gepa_reflection")
    assert "<curr_param>" in template and "<side_info>" in template
    assert "Keep every placeholder in curly braces" in template
    assert "Do not name these example questions" in template

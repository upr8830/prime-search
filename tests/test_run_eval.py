"""The SearchBench runner (docs/05 §3), offline.

LangSmith's client and `evaluate()` are faked at `run_eval._client` / `run_eval._evaluate`,
the agents at `run_eval.run_prime` / `run_eval.run_baseline`, and the judge at
`evaluators.structured` (it raises, so judge metrics come back as judge failures). What is
pinned: what the runner refuses, how it labels an experiment, that its target never
raises and carries bench labels, and what it writes.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from langsmith.evaluation import EvaluationResult

from eval import evaluators, run_eval
from eval.evaluators import METRIC_KEYS
from eval.searchbench.schema import load_records
from eval.searchbench.sync import to_example
from prime_search import events
from prime_search.schemas import Answer, RunRequest


def _examples(split: str = "dev") -> list[SimpleNamespace]:
    found = []
    for record in load_records():
        if record.split != split:
            continue
        example = to_example(record)
        found.append(
            SimpleNamespace(
                id=uuid.UUID(example["id"]), inputs=example["inputs"], outputs=example["outputs"],
                metadata={**example["metadata"], "dataset_split": [example["split"]]},
            )
        )
    return found


class FakeClient:
    def __init__(self, examples) -> None:  # noqa: ANN001
        self.examples = examples

    def list_examples(self, *, dataset_name, splits):  # noqa: ANN001, ANN201
        return [e for e in self.examples if e.metadata["dataset_split"][0] in splits]


class FakeResults(list):
    experiment_name = "prime-base-dev-20260913-1500-abcd1234"
    url = "https://smith.langchain.com/o/x/datasets/y/compare?selectedSessions=z"


def _fake_evaluate(captured: dict):  # noqa: ANN202
    def evaluate(target, *, data, evaluators, **kwargs):  # noqa: ANN001, ANN003, ANN202
        captured.update(kwargs)
        rows = FakeResults()
        for example in data:
            outputs = target(example.inputs)
            run = SimpleNamespace(id=uuid.uuid4(), outputs=outputs, error=None)
            results = []
            for evaluator in evaluators:
                output = evaluator(run, example)
                results.extend(EvaluationResult(**item) for item in output.get("results", [output]))
            rows.append({"run": run, "example": example, "evaluation_results": {"results": results}})
        return rows

    return evaluate


def _answer() -> Answer:
    return Answer(
        summary="Covered.", body_markdown="## Answer\n\nCovered [1].", claims=[], citations=[],
        effective_dates=[], contradictions=[], unknowns=[], confidence=0.5,
    )


@pytest.fixture
def bench(sandboxed_run, monkeypatch, tmp_path):
    """LangSmith key set, bench output under tmp_path, judge unavailable."""
    from prime_search.config import get_settings

    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_" + "x" * 30)
    # main() writes PRIME_TAVILY_CACHE for --no-cache; setting it here makes monkeypatch restore it.
    monkeypatch.setenv("PRIME_TAVILY_CACHE", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(run_eval, "BENCH_DIR", tmp_path / "bench")

    def no_judge(role, schema, **kwargs):  # noqa: ANN001, ANN003, ANN202
        raise RuntimeError("judge unavailable offline")

    monkeypatch.setattr(evaluators, "structured", no_judge)
    return tmp_path


def _must_not_call(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
    raise AssertionError("this should not have been called")


# --- refusals -------------------------------------------------------------------------


def test_refuses_when_the_dataset_check_reports_problems(bench, monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_eval, "check", lambda records: ["1 record(s) lack validated_by/as_of"])
    monkeypatch.setattr(run_eval, "_evaluate", _must_not_call)
    assert run_eval.main(["--mode", "prime", "--split", "dev"]) == 1
    assert "refusing to run" in capsys.readouterr().err


def test_refuses_when_langsmith_differs_from_the_jsonl(bench, monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_eval, "_client", lambda: FakeClient(_examples()[:-1]))
    monkeypatch.setattr(run_eval, "_evaluate", _must_not_call)
    assert run_eval.main(["--mode", "prime", "--split", "dev"]) == 1
    assert "eval.searchbench.sync" in capsys.readouterr().err


def test_a_dry_run_spends_nothing(bench, monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_eval, "_client", _must_not_call)
    monkeypatch.setattr(run_eval, "_evaluate", _must_not_call)
    assert run_eval.main(["--mode", "baseline", "--split", "dev", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "baseline-none-dev-" in out and "examples (5)" in out


def test_no_cache_turns_the_cache_off(bench, monkeypatch, capsys) -> None:
    monkeypatch.setattr(run_eval, "_client", _must_not_call)
    assert run_eval.main(["--mode", "prime", "--split", "dev", "--dry-run", "--no-cache"]) == 0
    assert '"tavily_cache": false' in capsys.readouterr().out


# --- labels ---------------------------------------------------------------------------------


def test_experiment_prefix_and_metadata(bench) -> None:
    from prime_search.config import get_settings

    now = datetime(2026, 9, 13, 15, 4, tzinfo=UTC)
    assert run_eval.experiment_prefix("baseline", "base", "dev", now) == "baseline-none-dev-20260913-1504"
    assert run_eval.experiment_prefix("prime", "base", "dev", now) == "prime-base-dev-20260913-1504"
    settings = get_settings()
    baseline = run_eval.run_metadata(settings, mode="baseline", depth="deep", split="dev", prompt_set="base", n=5, subset=False)
    prime = run_eval.run_metadata(settings, mode="prime", depth="deep", split="dev", prompt_set="base", n=5, subset=False)
    assert baseline["tavily_cache"] is False and baseline["prompt_set"] == "none"
    assert prime["tavily_cache"] is True and prime["budget"]["max_tokens"] == 400_000
    assert {"git_sha", "models", "budget", "dataset_sha", "evaluator_model"} <= set(prime)


def test_the_target_carries_bench_labels_and_never_raises(bench, monkeypatch) -> None:
    seen: dict = {}

    def failing(request, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen.update(kwargs, request=request)
        record = kwargs["ws"].to_record(request, status="failed", error="RuntimeError: boom")
        events.write_run_artifacts(record)
        raise RuntimeError("boom")

    monkeypatch.setattr(run_eval, "run_prime", failing)
    outputs = run_eval.make_target("prime", "deep", "base", "dev")({"question": "q?", "question_id": "cgm-elig-004"})
    assert (seen["source"], seen["extra_tags"], seen["project_name"]) == ("bench", ["bench:dev"], "prime-search-bench")
    assert seen["request"].question_id == "cgm-elig-004"
    assert outputs["error"].startswith("RuntimeError") and outputs["record"]["status"] == "failed"


# --- a whole run -------------------------------------------------------------------------------


def test_a_run_writes_the_experiment_json_and_each_metrics_json(bench, monkeypatch, capsys) -> None:
    def fake_prime(request: RunRequest, **kwargs):  # noqa: ANN003, ANN202
        from prime_search.schemas import SearchTask

        ws = kwargs["ws"]
        ws.tasks.append(SearchTask(task_id="b1-r0", branch_id="b1", round=0, instruction="i"))
        record = ws.to_record(request, status="completed", answer=_answer())
        events.write_run_artifacts(record)
        return record

    captured: dict = {}
    monkeypatch.setattr(run_eval, "run_prime", fake_prime)
    monkeypatch.setattr(run_eval, "_client", lambda: FakeClient(_examples()))
    monkeypatch.setattr(run_eval, "_evaluate", _fake_evaluate(captured))

    assert run_eval.main(["--mode", "prime", "--split", "dev"]) == 0
    assert captured["experiment_prefix"].startswith("prime-base-dev-")
    assert captured["max_concurrency"] == 0  # sequential by default

    path = bench / "bench" / f"{FakeResults.experiment_name}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 5
    row = payload["rows"][0]
    assert set(row["scores"]) == set(METRIC_KEYS)
    assert "tasks" not in row["record"]  # trimmed (docs/11)
    metrics = json.loads((events.run_dir(row["run_id"]) / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["experiment_name"] == FakeResults.experiment_name and metrics["split"] == "dev"


def test_concurrency_n_runs_n_examples_at_once(bench, monkeypatch) -> None:
    def fake_prime(request: RunRequest, **kwargs):  # noqa: ANN003, ANN202
        record = kwargs["ws"].to_record(request, status="completed", answer=_answer())
        events.write_run_artifacts(record)
        return record

    captured: dict = {}
    monkeypatch.setattr(run_eval, "run_prime", fake_prime)
    monkeypatch.setattr(run_eval, "_client", lambda: FakeClient(_examples()))
    monkeypatch.setattr(run_eval, "_evaluate", _fake_evaluate(captured))
    assert run_eval.main(["--mode", "prime", "--split", "dev", "--concurrency", "3"]) == 0
    assert captured["max_concurrency"] == 3


def test_rescore_scores_saved_records_without_running_agents(bench, monkeypatch) -> None:
    monkeypatch.setattr(run_eval, "run_prime", _must_not_call)
    monkeypatch.setattr(run_eval, "_evaluate", _must_not_call)
    from prime_search.workspace import Workspace

    ws = Workspace(objective="q?")
    saved = ws.to_record(RunRequest(question="q?"), status="completed", answer=_answer()).model_dump(mode="json")
    payload = {
        "experiment_name": "prime-base-dev-x", "experiment_url": None,
        "config": {"mode": "prime", "prompt_set": "base", "split": "dev", "depth": "deep"},
        "metadata": {"git_sha": "abc"}, "started_at": "t", "finished_at": "t",
        "rows": [{"question_id": "cgm-elig-004", "run_id": ws.run_id, "scores": {}, "composite": None, "record": saved}],
    }
    path = bench / "saved.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert run_eval.main(["--rescore", str(path)]) == 0
    rescored = json.loads((bench / "bench" / "prime-base-dev-x.json").read_text(encoding="utf-8"))
    assert set(rescored["rows"][0]["scores"]) == set(METRIC_KEYS)
    assert "rescored_at" in rescored


def test_rows_keep_a_score_langsmith_received_as_a_value() -> None:
    # A prime run's tokens exceed LangSmith's score range; the local JSON must keep the number.
    item = EvaluationResult(**evaluators.Score("tokens", 586002, "586002 tokens").to_langsmith())
    result = {
        "run": SimpleNamespace(id=uuid.uuid4(), outputs={}, error=None),
        "example": SimpleNamespace(metadata={"id": "cgm-elig-004"}),
        "evaluation_results": {"results": [item]},
    }
    (row,) = run_eval.rows_from_results([result])
    assert row["scores"]["tokens"]["score"] == 586002

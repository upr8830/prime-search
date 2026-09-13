"""The evidence judge (docs/03 §6).

The model is stubbed at `judge_module.structured`: what matters here is what the judge
is shown and what the harness does with its answer - which tasks survive, what they are
called, and what a failure leaves behind - not whether a model can emit JSON (that is
`test_structured.py` and `make smoke`).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime

import pytest
from langchain_core.messages import AIMessage

from prime_search import events
from prime_search.agents import judge as judge_module
from prime_search.agents.judge import FAILED_TAG, build_prompt, run_judge
from prime_search.schemas import (
    Branch,
    Claim,
    Document,
    Evidence,
    Location,
    QueryUnderstanding,
    SearchPlan,
    SearchTask,
    TaskResult,
    Usage,
    Verdict,
)


class FakeCaller:
    def __init__(self, value=None, *, error=None, message=None, mode="native") -> None:  # noqa: ANN001
        self.value = value
        self.error = error
        self.last_mode = mode
        self.last_message = message
        self.messages = [message] if message is not None else []
        self.prompts: list[str] = []

    def invoke(self, prompt: str):  # noqa: ANN201
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.value


@pytest.fixture
def ws(sandboxed_run):
    """Two branches: b1 answered from a dated primary source, b2 searched once and
    still open."""
    ws = sandboxed_run
    ws.understanding = QueryUnderstanding(
        normalized_question="q", domain="cgm", question_type="eligibility", time_sensitivity="high"
    )
    ws.plan = SearchPlan(
        understanding=ws.understanding,
        branches=[
            Branch(branch_id="b1", question="What does the LCD require?", rationale="r",
                   source_hint="primary_policy", priority=1),
            Branch(branch_id="b2", question="What changed recently?", rationale="r",
                   source_hint="primary_policy", priority=2),
        ],
        stop_criteria="Every criterion cited to a dated primary source",
        budget=ws.budget,
    )
    ws.documents["doc_lcd"] = Document(
        doc_id="doc_lcd", url="https://www.cms.gov/lcd", title="LCD", source_tier="primary_policy",
        document_id_external="L33822", revision_date=date(2024, 10, 1),
        retrieved_at=datetime.now(UTC), fetch_method="extract",
    )
    ws.evidence.append(
        Evidence(
            evidence_id="ev_1", doc_id="doc_lcd", branch_id="b1",
            claim_text="Insulin treatment qualifies", evidence_text="The beneficiary is insulin-treated",
            location=Location(paragraph_index=71, char_start=0, char_end=34),
            effective_date=date(2024, 10, 1), relevance=0.8, source_quality=1.0, confidence=0.9,
            stance="supports",
        )
    )
    ws.claims.append(
        Claim(claim_id="c1", text="Insulin treatment qualifies", branch_id="b1",
              supported_by=["ev_1"], status="supported", confidence=0.9,
              governing_date=date(2024, 10, 1))
    )
    ws.tasks.append(
        SearchTask(
            task_id="b2-r0", branch_id="b2", round=0, instruction="Find recent changes",
            status="done",
            result=TaskResult(
                queries_issued=["CGM LCD revision 2024"], documents_fetched=[], evidence_ids=[],
                summary="", unresolved="no revision notice found", usage=Usage(),
            ),
        )
    )
    ws.unknowns.append("no revision notice found")
    return ws


def _task(
    branch: str = "b2",
    instruction: str = "Fetch the revision history of L33822",
    queries: tuple[str, ...] = ("L33822 revision history",),
    **fields,
) -> SearchTask:
    payload = {"task_id": "anything", "round": 9, "status": "done"}
    payload.update(fields)
    return SearchTask(branch_id=branch, instruction=instruction, queries_hint=list(queries), **payload)


def _raw(sufficient: bool = False, tasks=(), coverage=None) -> Verdict:  # noqa: ANN001
    return Verdict(
        round=42,
        sufficient=sufficient,
        coverage={"b1": "resolved", "b2": "partial"} if coverage is None else coverage,
        missing=["the revision date"],
        new_tasks=list(tasks),
        reasoning=" b2 has no governing date. ",
    )


def _judge(ws, monkeypatch, value=None, *, error=None, message=None, mode="native", **params):  # noqa: ANN001, ANN003, ANN202
    caller = FakeCaller(value, error=error, message=message, mode=mode)
    monkeypatch.setattr(judge_module, "structured", lambda *a, **k: caller)
    arguments = {"judged_round": 0, "max_new_tasks": 3, "rounds_left": 2}
    arguments.update(params)
    return run_judge(ws, **arguments), caller


# --- what the judge is shown ----------------------------------------------------------


def test_the_prompt_carries_stop_criteria_claims_dates_unresolved_and_budget(ws) -> None:
    """docs/03 §6's input list, each item present."""
    prompt = build_prompt(ws, judged_round=0, max_new_tasks=3, rounds_left=2)

    assert "Every criterion cited to a dated primary source" in prompt
    assert (
        "c1 [supported · governing 2024-10-01 · 1 for / 0 against · best source primary_policy]"
        in prompt
    )
    assert "no revision notice found" in prompt
    assert '"CGM LCD revision 2024"' in prompt  # the no-duplicate rule needs the queries run
    assert "searches 30" in prompt and "search rounds left: 2" in prompt
    assert "at most **3** new tasks" in prompt
    assert not re.search(r"\{[a-z_]+\}", prompt)


def test_no_round_left_tells_the_judge_it_may_add_nothing(ws, monkeypatch) -> None:
    outcome, caller = _judge(ws, monkeypatch, _raw(tasks=[_task()]), max_new_tasks=0)
    assert "at most **0** new tasks" in caller.prompts[0]
    assert outcome.verdict.new_tasks == []


# --- what the harness does with the answer --------------------------------------------


def test_the_harness_rewrites_task_id_round_and_status(ws, monkeypatch) -> None:
    outcome, _ = _judge(ws, monkeypatch, _raw(tasks=[_task()]), judged_round=0)

    task = outcome.verdict.new_tasks[0]
    assert (task.task_id, task.round, task.status, task.result) == ("b2-r1", 1, "pending", None)
    assert outcome.verdict.round == 0  # the round judged, not whatever the model wrote
    assert outcome.verdict.reasoning == "b2 has no governing date."


def test_no_task_survives_for_a_resolved_or_unknown_branch(ws, monkeypatch) -> None:
    """docs/03 §6: "It must not create tasks for branches already `resolved`"."""
    proposed = [_task(branch="b1"), _task(branch="b9"), _task()]
    outcome, _ = _judge(ws, monkeypatch, _raw(tasks=proposed))

    assert [t.branch_id for t in outcome.verdict.new_tasks] == ["b2"]
    assert outcome.dropped_tasks == 2


def test_new_tasks_are_capped_and_numbered_per_branch(ws, monkeypatch) -> None:
    proposed = [
        _task(instruction=f"Fetch source {i}", queries=(f"query {i}",)) for i in range(5)
    ]
    outcome, _ = _judge(ws, monkeypatch, _raw(tasks=proposed), max_new_tasks=3)

    assert [t.task_id for t in outcome.verdict.new_tasks] == ["b2-r1", "b2-r1-2", "b2-r1-3"]


def test_a_task_repeating_an_earlier_search_is_dropped(ws, monkeypatch) -> None:
    """A repeated instruction or an already-run query spends a sub-agent learning
    nothing new. Matched ignoring case and spacing."""
    proposed = [
        _task(instruction="find  recent changes", queries=("something new",)),
        _task(instruction="A new instruction", queries=("cgm lcd revision 2024",)),
        _task(instruction="A new instruction", queries=("a new query",)),
        _task(instruction="A new instruction", queries=("another new query",)),  # same instruction twice
    ]
    outcome, _ = _judge(ws, monkeypatch, _raw(tasks=proposed))

    assert [t.queries_hint for t in outcome.verdict.new_tasks] == [["a new query"]]


def test_a_sufficient_verdict_carries_no_tasks(ws, monkeypatch) -> None:
    outcome, _ = _judge(ws, monkeypatch, _raw(sufficient=True, tasks=[_task()]))
    assert outcome.verdict.sufficient is True
    assert outcome.verdict.new_tasks == []


def test_every_branch_gets_a_coverage_status_and_unknown_ones_are_dropped(ws, monkeypatch) -> None:
    outcome, _ = _judge(ws, monkeypatch, _raw(coverage={"b9": "resolved"}))
    # b1 has evidence, so it is at least partial; b2 has none.
    assert outcome.verdict.coverage == {"b1": "partial", "b2": "unresolved"}


def test_domains_are_reduced_to_hosts_and_time_range_is_checked(ws, monkeypatch) -> None:
    proposed = [
        _task(include_domains=["https://www.cms.gov/medicare", "cms.gov/", "CMS.gov"], time_range="decade")
    ]
    outcome, _ = _judge(ws, monkeypatch, _raw(tasks=proposed))

    task = outcome.verdict.new_tasks[0]
    assert task.include_domains == ["www.cms.gov", "cms.gov"]
    assert task.time_range is None


# --- failure and accounting ------------------------------------------------------------


def test_a_failed_judge_returns_a_structured_failure(ws, monkeypatch) -> None:
    """docs/01 §9: after the repair attempt, "the node returns a structured failure and
    the graph proceeds"."""
    error = RuntimeError("judge: structured output failed in both modes")
    outcome, _ = _judge(ws, monkeypatch, error=error)

    assert outcome.fallback_tag == FAILED_TAG
    assert outcome.verdict.sufficient is False
    assert outcome.verdict.new_tasks == []
    assert outcome.verdict.coverage == {"b1": "partial", "b2": "unresolved"}
    logged = [r for r in events.replay(ws.run_id) if r["type"] == "error"]
    assert logged and "judge" in json.dumps(logged[-1])
    assert logged[-1]["payload"]["severity"] == "warning"  # the run goes on (docs/02 §4)


def test_judge_tokens_are_charged_to_the_run(ws, monkeypatch) -> None:
    message = AIMessage(
        content="", usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
    )
    _judge(ws, monkeypatch, _raw(), message=message)

    assert (ws.usage.input_tokens, ws.usage.output_tokens) == (120, 30)
    assert ws.tokens_estimated is False


def test_a_reply_with_no_usage_is_charged_by_estimate(ws, monkeypatch) -> None:
    _judge(ws, monkeypatch, _raw(), message=None)
    assert ws.usage.input_tokens > 0
    assert ws.tokens_estimated is True


def test_a_fenced_json_answer_is_tagged_as_a_fallback(ws, monkeypatch) -> None:
    """docs/06 §2: "`fallback:<...>` when any fallback fires"; docs/01 §4 rule 3 makes
    fenced JSON the judge's fallback."""
    outcome, _ = _judge(ws, monkeypatch, _raw(), mode="fenced_json")
    assert outcome.fallback_tag == "fallback:judge_fenced_json"


def test_every_reply_the_ladder_received_is_charged(ws, monkeypatch) -> None:
    """A failed native attempt spent tokens too; charging only the reply that worked
    undercounts `max_tokens` exactly when the fallback fires."""
    caller = FakeCaller(_raw())
    caller.messages = [
        AIMessage(content="", usage_metadata={"input_tokens": 100, "output_tokens": 0, "total_tokens": 100}),
        AIMessage(content="", usage_metadata={"input_tokens": 110, "output_tokens": 40, "total_tokens": 150}),
    ]
    monkeypatch.setattr(judge_module, "structured", lambda *a, **k: caller)
    run_judge(ws, judged_round=0, max_new_tasks=3, rounds_left=2)
    assert (ws.usage.input_tokens, ws.usage.output_tokens) == (210, 40)

"""The graph (docs/03 §1, §5, §10).

The interesting assertions here are the three places the implementation deviates from
§1's diagram, because those are the ones a reader will check: the fan-out edge, the
`Send` payload, and what a branch is allowed to return. Plus the one accounting rule
that is easy to get wrong and silent when wrong - usage is not counted twice.
"""

from __future__ import annotations

import time


from prime_search.agents import graph as graph_module
from prime_search.agents.graph import DEPTH, PrimeState, _slice_budget, build_graph
from prime_search.config import Budget
from prime_search.evidence.store import EvidenceStore
from prime_search.schemas import (
    Branch,
    QueryUnderstanding,
    RunRequest,
    SearchPlan,
    SearchTask,
    TaskResult,
    Usage,
)



def _understanding(**overrides) -> QueryUnderstanding:
    payload = {
        "normalized_question": "q",
        "domain": "cgm",
        "question_type": "eligibility",
        "time_sensitivity": "high",
    }
    payload.update(overrides)
    return QueryUnderstanding(**payload)


def _plan(ws, count: int = 3) -> SearchPlan:
    plan = SearchPlan(
        understanding=ws.understanding or _understanding(),
        branches=[
            Branch(
                branch_id=f"b{i}",
                question=f"question {i}",
                rationale="r",
                source_hint="primary_policy",
                priority=i,
            )
            for i in range(1, count + 1)
        ],
        stop_criteria="cited",
        budget=ws.budget,
    )
    ws.plan = plan
    return plan


def _state(ws, **overrides) -> PrimeState:
    state: PrimeState = {
        "run_id": ws.run_id,
        "request": RunRequest(question=ws.objective),
        "ws": ws,
        "store": EvidenceStore(documents=ws.documents, items=ws.evidence),
        "pending_tasks": [],
        "task_results": [],
        "round": 0,
        "critic_rounds": 0,
        "deadline": time.time() + 300,
        "events": [],
        "depth": "deep",
        "prompt_set": "base",
        "models": {},
        "fallback_tags": [],
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state


# --- the three deviations -----------------------------------------------------------


def test_the_fan_out_edge_returns_sends_not_the_node(sandboxed_run) -> None:
    """docs/03 §1 draws `dispatch` returning Sends; only a conditional edge may. The
    node computes, the edge sends."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws)
    state = _state(ws)

    update = graph_module._dispatch(state)
    assert isinstance(update["pending_tasks"], list)  # a state update, not Sends
    assert all(isinstance(task, SearchTask) for task in update["pending_tasks"])

    sends = graph_module._fan_out({**state, **update})
    assert [send.node for send in sends] == ["search_agent"] * 3


def test_the_send_payload_carries_the_workspace_and_the_store(sandboxed_run) -> None:
    """§1's payload is {task, run_id, budget}, which run_search_agent cannot work
    from - it needs somewhere to fetch into and somewhere to record against."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws)
    state = _state(ws)
    state.update(graph_module._dispatch(state))  # type: ignore[typeddict-item]

    payload = graph_module._fan_out(state)[0].arg
    assert payload["ws"] is ws
    assert payload["store"] is state["store"]
    assert isinstance(payload["budget"], Budget)


def test_a_branch_returns_only_task_results_and_events(sandboxed_run, monkeypatch) -> None:
    """PrimeState.ws has no reducer, so a branch returning it raises
    InvalidUpdateError as soon as two branches run in the same superstep."""
    ws = sandboxed_run
    result = TaskResult(
        queries_issued=["q"], documents_fetched=[], evidence_ids=[], summary="s",
        unresolved=None, usage=Usage(),
    )
    monkeypatch.setattr(graph_module, "run_search_agent", lambda *a, **k: result)
    update = graph_module._search_agent(
        {
            "task": SearchTask(task_id="b1-r0", branch_id="b1", round=0, instruction="i"),
            "ws": ws,
            "store": EvidenceStore(documents=ws.documents, items=ws.evidence),
            "budget": ws.budget,
            "run_id": ws.run_id,
        }
    )
    assert set(update) == {"task_results", "events"}


def test_two_branches_fanning_out_do_not_collide(sandboxed_run, monkeypatch) -> None:
    """The end-to-end version of the rule above, through the real compiled graph."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=2)

    def fake_agent(task, **kwargs):  # noqa: ANN001, ANN202
        return TaskResult(
            queries_issued=[f"q-{task.branch_id}"], documents_fetched=[], evidence_ids=[],
            summary=f"summary {task.branch_id}", unresolved=None, usage=Usage(searches=1),
        )

    monkeypatch.setattr(graph_module, "run_search_agent", fake_agent)
    monkeypatch.setattr(graph_module, "plan_run", lambda ws, **k: _FakeOutcome(ws.plan))
    monkeypatch.setattr(graph_module, "synthesize", lambda ws, **k: _answer())
    monkeypatch.setattr(graph_module, "structured", lambda *a, **k: _FakeCaller(_understanding()))

    final = build_graph().invoke(_state(ws))
    assert len(final["task_results"]) == 2
    assert {r.summary for r in final["task_results"]} == {"summary b1", "summary b2"}


# --- accounting ---------------------------------------------------------------------


def test_collect_does_not_re_add_task_usage(sandboxed_run) -> None:
    """TaskResult.usage is a *report*; the tools already charged ws.usage as they went.
    Adding it again doubles every search, fetch and token in the record and the bench
    cost column - a plausible number, silently wrong."""
    ws = sandboxed_run
    ws.usage.searches = 4  # what the tools actually charged
    _plan(ws, count=1)
    ws.tasks = [SearchTask(task_id="b1-r0", branch_id="b1", round=0, instruction="i", status="running")]
    results = [
        TaskResult(
            queries_issued=["a", "b", "c", "d"], documents_fetched=[], evidence_ids=[],
            summary="s", unresolved=None, usage=Usage(searches=4),
        )
    ]

    graph_module._collect(_state(ws, task_results=results))
    assert ws.usage.searches == 4


def test_collect_advances_the_round_and_clears_pending(sandboxed_run) -> None:
    ws = sandboxed_run
    _plan(ws, count=1)
    update = graph_module._collect(_state(ws, round=1, task_results=[]))
    assert update["round"] == 2
    assert update["pending_tasks"] == []
    assert ws.usage.rounds == 2


def test_unresolved_branches_become_unknowns(sandboxed_run) -> None:
    """The answer's "Unknowns / not verified" section is only honest if a branch that
    found nothing says so."""
    ws = sandboxed_run
    _plan(ws, count=2)
    results = [
        TaskResult(
            queries_issued=[], documents_fetched=[], evidence_ids=[], summary="",
            unresolved="could not find the revision date", usage=Usage(),
        )
    ]
    graph_module._collect(_state(ws, task_results=results))

    assert "could not find the revision date" in ws.unknowns
    assert any("question 1" in note for note in ws.unknowns)
    assert any("question 2" in note for note in ws.unknowns)


# --- budget and depth ---------------------------------------------------------------


def test_dispatch_truncates_to_max_agents(sandboxed_run) -> None:
    """docs/03 §1: "dispatch truncates pending_tasks to what the remaining budget
    allows"."""
    ws = sandboxed_run
    ws.budget = Budget(max_agents=2)
    ws.understanding = _understanding()
    _plan(ws, count=5)

    update = graph_module._dispatch(_state(ws))
    assert len(update["pending_tasks"]) == 2
    # And it keeps the ones the planner ranked highest, not the first two it saw.
    assert [t.branch_id for t in update["pending_tasks"]] == ["b1", "b2"]


def test_the_budget_slice_divides_what_remains_not_the_original(sandboxed_run) -> None:
    """On a later round the first round has already spent; slicing the original would
    hand out budget that is gone."""
    ws = sandboxed_run
    ws.budget = Budget(max_searches=30)
    ws.usage.searches = 24  # 6 left
    sliced = _slice_budget(ws, tasks=3, depth="deep")
    assert sliced.max_searches == 2


def test_a_slice_is_never_zero(sandboxed_run) -> None:
    """A task dispatched with nothing to spend burns an agent and a model call to
    discover it cannot act."""
    ws = sandboxed_run
    ws.budget = Budget(max_searches=2)
    sliced = _slice_budget(ws, tasks=6, depth="deep")
    assert sliced.max_searches >= 1


def test_fast_depth_narrows_agents_and_tool_calls() -> None:
    """docs/03 §10's table."""
    assert DEPTH["fast"]["max_agents"] == 1
    assert DEPTH["fast"]["max_branches"] == 2
    assert DEPTH["fast"]["tool_calls"] < DEPTH["deep"]["tool_calls"]


def test_fast_depth_dispatches_one_agent(sandboxed_run) -> None:
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=2)
    update = graph_module._dispatch(_state(ws, depth="fast"))
    assert len(update["pending_tasks"]) == 1


# --- the change-detection contract ---------------------------------------------------


def test_a_change_detection_question_gets_a_time_filtered_task(sandboxed_run) -> None:
    """docs/03 §3: "change-detection questions must include a branch with
    time_range='year'". Branch has no such field, so the rule lands on the task."""
    ws = sandboxed_run
    ws.understanding = _understanding(question_type="change_detection")
    ws.plan = SearchPlan(
        understanding=ws.understanding,
        branches=[
            Branch(branch_id="b1", question="What are the criteria?", rationale="r",
                   source_hint="primary_policy", priority=1),
            Branch(branch_id="b2", question="What changed most recently?", rationale="r",
                   source_hint="primary_policy", priority=2),
        ],
        stop_criteria="cited",
        budget=ws.budget,
    )
    tasks = graph_module._tasks_from_plan(_state(ws))
    windows = {task.branch_id: task.time_range for task in tasks}
    assert windows["b2"] == "year"
    assert windows["b1"] is None  # not every branch; that would waste half the budget


def test_a_change_detection_plan_with_no_recency_branch_still_gets_a_window(
    sandboxed_run,
) -> None:
    """Otherwise the contract is unmet by omission and nothing notices."""
    ws = sandboxed_run
    ws.understanding = _understanding(question_type="change_detection")
    ws.plan = SearchPlan(
        understanding=ws.understanding,
        branches=[
            Branch(branch_id="b1", question="What are the criteria?", rationale="r",
                   source_hint="primary_policy", priority=1),
        ],
        stop_criteria="cited",
        budget=ws.budget,
    )
    tasks = graph_module._tasks_from_plan(_state(ws))
    assert tasks[0].time_range == "year"


def test_an_eligibility_question_gets_no_window(sandboxed_run) -> None:
    ws = sandboxed_run
    ws.understanding = _understanding(question_type="eligibility")
    _plan(ws, count=2)
    tasks = graph_module._tasks_from_plan(_state(ws))
    assert all(task.time_range is None for task in tasks)


# --- failure and deadline ------------------------------------------------------------


def test_one_failing_branch_does_not_fail_the_run(sandboxed_run, monkeypatch) -> None:
    def dies(task, **kwargs):  # noqa: ANN001, ANN202
        raise RuntimeError("tavily down")

    monkeypatch.setattr(graph_module, "run_search_agent", dies)
    update = graph_module._search_agent(
        {
            "task": SearchTask(task_id="b1-r0", branch_id="b1", round=0, instruction="i"),
            "ws": sandboxed_run,
            "store": EvidenceStore(documents={}, items=[]),
            "budget": sandboxed_run.budget,
            "run_id": sandboxed_run.run_id,
        }
    )
    result = update["task_results"][0]
    assert "tavily down" in result.unresolved
    assert result.evidence_ids == []


def test_an_expired_deadline_short_circuits_the_nodes(sandboxed_run) -> None:
    """docs/03 §1: every node checks the deadline and the run synthesizes what it has."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws)
    expired = _state(ws, deadline=time.time() - 1)

    assert graph_module._understand(expired) == {}
    assert graph_module._plan(expired) == {}
    assert graph_module._dispatch(expired)["pending_tasks"] == []
    # And with nothing dispatched the edge routes to collect, not into a dead superstep.
    assert graph_module._fan_out(expired) == "collect"


def test_nothing_to_dispatch_routes_to_collect(sandboxed_run) -> None:
    """An empty Send list leaves the superstep with no outgoing task and the graph
    stops with the answer unwritten."""
    assert graph_module._fan_out(_state(sandboxed_run, pending_tasks=[])) == "collect"


# --- the whole graph ------------------------------------------------------------------


def test_the_graph_runs_end_to_end_offline(sandboxed_run, monkeypatch) -> None:
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=2)
    monkeypatch.setattr(graph_module, "plan_run", lambda ws, **k: _FakeOutcome(ws.plan))
    monkeypatch.setattr(graph_module, "structured", lambda *a, **k: _FakeCaller(_understanding()))
    monkeypatch.setattr(
        graph_module,
        "run_search_agent",
        lambda task, **k: TaskResult(
            queries_issued=["q"], documents_fetched=[], evidence_ids=[], summary="s",
            unresolved=None, usage=Usage(),
        ),
    )
    monkeypatch.setattr(graph_module, "synthesize", lambda ws, **k: _answer())

    final = build_graph().invoke(_state(ws))
    assert final["answer"].summary == "the answer"
    assert final["round"] == 1  # collect ran once


def test_a_planner_fallback_reaches_the_root_run_tags(sandboxed_run, monkeypatch) -> None:
    """docs/06 §2: a reviewer scanning traces should see that this run planned badly."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=1)
    monkeypatch.setattr(
        graph_module, "plan_run", lambda ws, **k: _FakeOutcome(ws.plan, "fallback:default_plan")
    )
    update = graph_module._plan(_state(ws))
    assert update["fallback_tags"] == ["fallback:default_plan"]


class _FakeOutcome:
    def __init__(self, plan, tag=None) -> None:  # noqa: ANN001
        self.plan = plan
        self.mode = "code"
        self.fallback_tag = tag
        self.repairs = 0


class _FakeCaller:
    def __init__(self, value) -> None:  # noqa: ANN001
        self.value = value

    def invoke(self, prompt):  # noqa: ANN001, ANN201
        return self.value


def _answer():
    from prime_search.schemas import Answer

    return Answer(
        summary="the answer", body_markdown="## Answer\n\nthe answer", claims=[], citations=[],
        effective_dates=[], contradictions=[], unknowns=[], confidence=0.5,
    )

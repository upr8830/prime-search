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
from prime_search.agents.judge import JudgeOutcome
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
    Verdict,
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
    assert set(update) == {"task_results", "results_by_task", "events"}


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
    monkeypatch.setattr(graph_module, "run_judge", _sufficient_judge)

    final = build_graph().invoke(_state(ws))
    assert len(final["task_results"]) == 2
    assert {r.summary for r in final["task_results"]} == {"summary b1", "summary b2"}
    assert set(final["results_by_task"]) == {"b1-r0", "b2-r0"}


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

    graph_module._collect(_state(ws, task_results=results, results_by_task={"b1-r0": results[0]}))
    assert ws.usage.searches == 4
    assert ws.tasks[0].result is results[0]


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
    ws.tasks = [SearchTask(task_id="b1-r0", branch_id="b1", round=0, instruction="i", status="running")]
    graph_module._collect(_state(ws, task_results=results, results_by_task={"b1-r0": results[0]}))

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


def test_a_slice_never_hands_out_budget_that_is_gone(sandboxed_run) -> None:
    """At least one while any remains - but a spent budget slices to zero, not one."""
    ws = sandboxed_run
    ws.budget = Budget(max_searches=30, max_fetches=20)
    ws.usage.searches = 30
    sliced = _slice_budget(ws, tasks=2, depth="deep")
    assert sliced.max_searches == 0
    assert sliced.max_fetches == 10


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
    monkeypatch.setattr(graph_module, "run_judge", _sufficient_judge)

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


def test_the_graph_run_is_not_named_like_the_root_run() -> None:
    """docs/06 §1 names the root run `prime_search`. LangGraph always adds its own run
    for the compiled graph, so naming both the same produced a trace whose only visible
    child was an identically named row, with understand/plan/synthesize hidden a level
    below it - two `prime_search` rows read as a rendering glitch, not a hierarchy."""
    import inspect

    source = inspect.getsource(graph_module.run_prime)
    assert '"run_name": "graph"' in source
    assert source.count('"run_name": "prime_search"') == 0


# --- multi-round plumbing (task 2.2) ---------------------------------------------------


def _task(task_id: str, branch_id: str, round_: int, status: str = "pending") -> SearchTask:
    return SearchTask(
        task_id=task_id, branch_id=branch_id, round=round_, instruction=f"find {branch_id}",
        status=status,
    )


def _result(summary: str, unresolved: str | None = None) -> TaskResult:
    return TaskResult(
        queries_issued=[summary], documents_fetched=[], evidence_ids=[], summary=summary,
        unresolved=unresolved, usage=Usage(),
    )


def test_dispatch_does_not_reseed_the_plan_after_round_zero(sandboxed_run) -> None:
    """A later node routing back with nothing pending must not re-dispatch every
    branch of the plan."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=3)
    ws.tasks = [_task(f"b{i}-r0", f"b{i}", 0, status="done") for i in (1, 2, 3)]

    update = graph_module._dispatch(_state(ws, round=1, pending_tasks=[]))
    assert update["pending_tasks"] == []
    assert len(ws.tasks) == 3


def test_a_later_round_gets_the_full_per_round_agent_cap(sandboxed_run) -> None:
    """max_agents caps each round. As a run total, a 6-branch round 0 left none."""
    ws = sandboxed_run
    ws.budget = Budget(max_agents=6)
    ws.understanding = _understanding()
    _plan(ws, count=6)
    ws.usage.agents = 6  # round 0 dispatched six

    pending = [_task(f"b{i}-r1", f"b{i}", 1) for i in (1, 2, 3)]
    update = graph_module._dispatch(_state(ws, round=1, pending_tasks=pending))
    assert [t.task_id for t in update["pending_tasks"]] == ["b1-r1", "b2-r1", "b3-r1"]
    assert ws.usage.agents == 9  # still counted for the record


def test_no_searches_left_dispatches_nothing(sandboxed_run) -> None:
    ws = sandboxed_run
    ws.budget = Budget(max_searches=30)
    ws.usage.searches = 30
    ws.understanding = _understanding()
    _plan(ws, count=2)
    assert graph_module._dispatch(_state(ws))["pending_tasks"] == []


def test_collect_pairs_results_by_task_id_across_rounds(sandboxed_run) -> None:
    """`task_results` accumulates across rounds; zipping it against the running tasks
    attached round-0 results to round-1 tasks."""
    ws = sandboxed_run
    _plan(ws, count=2)
    r0 = _result("round zero")
    r1 = _result("round one, b2")
    ws.tasks = [
        _task("b1-r0", "b1", 0, status="done"),
        _task("b1-r1", "b1", 1, status="running"),
        _task("b2-r1", "b2", 1, status="running"),
    ]
    ws.tasks[0].result = r0

    graph_module._collect(
        _state(ws, round=1, task_results=[r0, r1], results_by_task={"b1-r0": r0, "b2-r1": r1})
    )
    by_id = {task.task_id: task for task in ws.tasks}
    assert by_id["b2-r1"].result is r1 and by_id["b2-r1"].status == "done"
    assert by_id["b1-r1"].result is None and by_id["b1-r1"].status == "failed"
    assert by_id["b1-r0"].result is r0


def test_a_task_past_the_deadline_is_not_started(sandboxed_run, monkeypatch) -> None:
    """docs/01 §9: a checked deadline at every node boundary, sub-agents included."""
    def must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("the sub-agent ran after the deadline")

    monkeypatch.setattr(graph_module, "run_search_agent", must_not_run)
    task = _task("b1-r1", "b1", 1, status="running")
    update = graph_module._search_agent(
        {
            "task": task,
            "ws": sandboxed_run,
            "store": EvidenceStore(documents={}, items=[]),
            "budget": sandboxed_run.budget,
            "run_id": sandboxed_run.run_id,
            "deadline": time.time() - 1,
        }
    )
    assert "deadline" in update["results_by_task"]["b1-r1"].unresolved
    assert task.status == "failed"


def test_the_send_payload_carries_the_deadline(sandboxed_run) -> None:
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=1)
    deadline = time.time() + 999
    state = _state(ws, deadline=deadline)
    state.update(graph_module._dispatch(state))  # type: ignore[typeddict-item]
    assert graph_module._fan_out(state)[0].arg["deadline"] == deadline


# --- the judge and its edge (task 2.2) -------------------------------------------------


def _verdict(sufficient: bool = True, tasks=(), round_: int = 0) -> Verdict:  # noqa: ANN001
    return Verdict(
        round=round_, sufficient=sufficient, coverage={}, missing=[], new_tasks=list(tasks),
        reasoning="r",
    )


def _sufficient_judge(ws, **kwargs) -> JudgeOutcome:  # noqa: ANN001, ANN003
    return JudgeOutcome(_verdict(round_=kwargs.get("judged_round", 0)), "native")


def _recording_judge(verdict: Verdict, seen: dict, tag: str | None = None):  # noqa: ANN202
    def judge(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen.update(kwargs)
        return JudgeOutcome(verdict, "native", tag)

    return judge


def test_an_insufficient_verdict_with_rounds_left_routes_back_to_dispatch(
    sandboxed_run, monkeypatch
) -> None:
    ws = sandboxed_run
    _plan(ws, count=2)
    seen: dict = {}
    verdict = _verdict(False, [_task("b2-r1", "b2", 1)])
    monkeypatch.setattr(graph_module, "run_judge", _recording_judge(verdict, seen))
    state = _state(ws, round=1)

    update = graph_module._judge(state)
    # collect already advanced the round: this verdict judges round 0, tasks go in round 1.
    assert (seen["judged_round"], seen["max_new_tasks"], seen["rounds_left"]) == (0, 3, 2)
    assert [t.task_id for t in update["pending_tasks"]] == ["b2-r1"]
    assert graph_module._after_judge({**state, **update}) == "dispatch"
    assert ws.verdicts == [verdict]
    assert [record["type"] for record in update["events"]] == ["verdict"]


def test_no_rounds_left_ignores_new_tasks_and_routes_to_the_critic(sandboxed_run, monkeypatch) -> None:
    """docs/03 §6: "the graph ignores `new_tasks` when `round == max_rounds`"."""
    ws = sandboxed_run
    _plan(ws, count=2)
    seen: dict = {}
    monkeypatch.setattr(
        graph_module, "run_judge", _recording_judge(_verdict(False, [_task("b2-r3", "b2", 3)]), seen)
    )
    state = _state(ws, round=3)

    update = graph_module._judge(state)
    assert seen["max_new_tasks"] == 0
    assert update["pending_tasks"] == []
    assert ws.verdicts[0].new_tasks == []  # the record lists only what was dispatched
    assert graph_module._after_judge({**state, **update}) == "critic"


def test_fast_depth_never_re_searches_and_skips_the_critic(sandboxed_run, monkeypatch) -> None:
    """docs/03 §10: fast is "1 (no re-search)" and "critic skipped"."""
    ws = sandboxed_run
    _plan(ws, count=1)
    seen: dict = {}
    monkeypatch.setattr(
        graph_module, "run_judge", _recording_judge(_verdict(False, [_task("b1-r1", "b1", 1)]), seen)
    )
    state = _state(ws, round=1, depth="fast")

    update = graph_module._judge(state)
    assert seen["max_new_tasks"] == 0
    assert update["pending_tasks"] == []
    assert graph_module._after_judge({**state, **update}) == "synthesize"


def test_too_little_time_left_adds_no_round(sandboxed_run, monkeypatch) -> None:
    ws = sandboxed_run
    _plan(ws, count=1)
    seen: dict = {}
    monkeypatch.setattr(
        graph_module, "run_judge", _recording_judge(_verdict(False, [_task("b1-r1", "b1", 1)]), seen)
    )
    update = graph_module._judge(_state(ws, round=1, deadline=time.time() + 10))
    assert seen["max_new_tasks"] == 0
    assert update["pending_tasks"] == []


def test_a_sufficient_verdict_routes_to_the_critic(sandboxed_run, monkeypatch) -> None:
    ws = sandboxed_run
    _plan(ws, count=1)
    monkeypatch.setattr(graph_module, "run_judge", _sufficient_judge)
    state = _state(ws, round=1)
    update = graph_module._judge(state)
    assert graph_module._after_judge({**state, **update}) == "critic"


def test_an_expired_deadline_skips_the_judge_and_synthesizes(sandboxed_run, monkeypatch) -> None:
    def must_not_run(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("the judge ran after the deadline")

    monkeypatch.setattr(graph_module, "run_judge", must_not_run)
    expired = _state(sandboxed_run, round=1, deadline=time.time() - 1)
    assert graph_module._judge(expired) == {}
    assert graph_module._after_judge(expired) == "synthesize"


def test_a_failed_judge_reaches_the_run_tags(sandboxed_run, monkeypatch) -> None:
    ws = sandboxed_run
    _plan(ws, count=1)
    monkeypatch.setattr(
        graph_module, "run_judge", _recording_judge(_verdict(False), {}, "fallback:judge_failed")
    )
    update = graph_module._judge(_state(ws, round=1))
    assert update["fallback_tags"] == ["fallback:judge_failed"]


def test_a_two_round_run_end_to_end(sandboxed_run, monkeypatch) -> None:
    """The loop the stubs never exercised: round 0, an insufficient verdict adding one
    task, round 1, a sufficient verdict, synthesis."""
    ws = sandboxed_run
    ws.understanding = _understanding()
    _plan(ws, count=2)
    monkeypatch.setattr(graph_module, "plan_run", lambda ws, **k: _FakeOutcome(ws.plan))
    monkeypatch.setattr(graph_module, "structured", lambda *a, **k: _FakeCaller(_understanding()))
    monkeypatch.setattr(graph_module, "synthesize", lambda ws, **k: _answer())
    monkeypatch.setattr(
        graph_module, "run_search_agent", lambda task, **k: _result(f"summary {task.task_id}")
    )
    judged: list[int] = []

    def judge(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
        judged.append(kwargs["judged_round"])
        if len(judged) == 1:
            return JudgeOutcome(_verdict(False, [_task("b1-r1", "b1", 1)]), "native")
        return JudgeOutcome(_verdict(True, round_=1), "native")

    monkeypatch.setattr(graph_module, "run_judge", judge)

    final = build_graph().invoke(_state(ws))
    assert judged == [0, 1]
    assert final["round"] == 2
    assert [task.task_id for task in ws.tasks] == ["b1-r0", "b2-r0", "b1-r1"]
    assert all(task.status == "done" for task in ws.tasks)
    assert ws.tasks[2].result.summary == "summary b1-r1"
    assert len(ws.verdicts) == 2

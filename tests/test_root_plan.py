"""The root planner's ladder (docs/03 §3, §13).

Every rung is exercised offline with a scripted model, because the ladder only matters
when a model misbehaves and a live model does that on its own schedule.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from prime_search.agents import root
from prime_search.agents.root import plan_run, strategy_card
from prime_search.schemas import QueryUnderstanding, SearchPlan

from conftest import ScriptedChatModel

GOOD_CELL = '''```python
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(branch_id="b1", question="What are the current LCD criteria?",
               rationale="the criteria are the answer", source_hint="primary_policy",
               priority=1),
        Branch(branch_id="b2", question="Do they cover non-insulin type 2?",
               rationale="the population asked about", source_hint="primary_policy",
               priority=1),
        Branch(branch_id="b3", question="What is the most recent revision?",
               rationale="currency", source_hint="primary_policy", priority=2),
    ],
    stop_criteria="Each criterion cited with its revision date.",
    budget=ws.budget,
)
```'''


def _understanding(**overrides) -> QueryUnderstanding:
    payload = {
        "normalized_question": "Is a therapeutic CGM covered for non-insulin type 2?",
        "domain": "cgm",
        "question_type": "eligibility",
        "time_sensitivity": "high",
    }
    payload.update(overrides)
    return QueryUnderstanding(**payload)


@pytest.fixture
def ws(sandboxed_run):
    sandboxed_run.understanding = _understanding()
    return sandboxed_run


def test_a_good_cell_becomes_the_plan(ws) -> None:
    model = ScriptedChatModel(script=[AIMessage(content=GOOD_CELL)])
    outcome = plan_run(ws, model=model)

    assert outcome.mode == "code"
    assert outcome.fallback_tag is None
    assert outcome.repairs == 0
    assert [b.branch_id for b in outcome.plan.branches] == ["b1", "b2", "b3"]
    assert ws.plan is outcome.plan  # the cell assigned it, the harness kept it


def test_a_broken_cell_gets_exactly_one_repair_turn(ws) -> None:
    """docs/03 §3: "on failure asks once for a corrected block"."""
    model = ScriptedChatModel(
        script=[AIMessage(content="```python\nws.plan = Branch(oops\n```"), AIMessage(content=GOOD_CELL)]
    )
    outcome = plan_run(ws, model=model)

    assert outcome.mode == "code"
    assert outcome.repairs == 1
    assert len(model.seen) == 2
    # The repair turn must carry the actual error, or the model is guessing blind.
    repair_prompt = "\n".join(str(m.content) for m in model.seen[1])
    assert "SyntaxError" in repair_prompt


def test_a_cell_that_runs_but_assigns_nothing_is_caught(ws) -> None:
    """The failure mode a naive harness misses: exec succeeds, ws.plan is still None."""
    model = ScriptedChatModel(
        script=[AIMessage(content="```python\nprint('thinking')\n```"), AIMessage(content=GOOD_CELL)]
    )
    outcome = plan_run(ws, model=model)

    assert outcome.repairs == 1
    problem = "\n".join(str(m.content) for m in model.seen[1])
    assert "did not assign ws.plan" in problem


def test_a_plan_outside_the_branch_contract_is_rejected(ws) -> None:
    one_branch = """```python
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(branch_id="b1", question="criteria?", rationale="r",
               source_hint="primary_policy", priority=1),
    ],
    stop_criteria="cited",
    budget=ws.budget,
)
```"""
    model = ScriptedChatModel(script=[AIMessage(content=one_branch), AIMessage(content=GOOD_CELL)])
    outcome = plan_run(ws, model=model)

    assert outcome.repairs == 1
    problem = "\n".join(str(m.content) for m in model.seen[1])
    assert "1 branches" in problem and "3-7" in problem


def test_an_empty_stop_criteria_is_rejected(ws) -> None:
    """Without it the judge at 2.2 has no definition of "enough" to test against."""
    no_criteria = GOOD_CELL.replace(
        'stop_criteria="Each criterion cited with its revision date."', 'stop_criteria=""'
    )
    model = ScriptedChatModel(script=[AIMessage(content=no_criteria), AIMessage(content=GOOD_CELL)])
    outcome = plan_run(ws, model=model)

    assert outcome.repairs == 1
    assert "stop_criteria is empty" in "\n".join(str(m.content) for m in model.seen[1])


def test_duplicate_branch_ids_are_rejected(ws) -> None:
    """Two branches sharing an id collapse in the search tree and in the claim graph."""
    duplicated = GOOD_CELL.replace('branch_id="b2"', 'branch_id="b1"')
    model = ScriptedChatModel(script=[AIMessage(content=duplicated), AIMessage(content=GOOD_CELL)])
    outcome = plan_run(ws, model=model)

    assert outcome.repairs == 1
    assert "unique" in "\n".join(str(m.content) for m in model.seen[1])


def test_no_fenced_block_twice_falls_back_to_structured_output(ws, monkeypatch) -> None:
    """docs/03 §3's rung 3, tagged `fallback:plan_structured`."""
    plan = SearchPlan(
        understanding=_understanding(),
        branches=[
            root.Branch(
                branch_id=f"b{i}",
                question=f"q{i}",
                rationale="r",
                source_hint="primary_policy",
                priority=1,
            )
            for i in (1, 2, 3)
        ],
        stop_criteria="cited",
        budget=ws.budget,
    )

    class FakeCaller:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            return plan

    monkeypatch.setattr(root, "structured", lambda *a, **k: FakeCaller())
    model = ScriptedChatModel(
        script=[AIMessage(content="I will plan carefully."), AIMessage(content="Still thinking.")]
    )
    outcome = plan_run(ws, model=model)

    assert outcome.mode == "structured"
    assert outcome.fallback_tag == "fallback:plan_structured"
    from prime_search import events as event_log

    plans = [r["payload"] for r in event_log.replay(ws.run_id) if r["type"] == "plan"]
    assert plans and plans[-1]["code"] is None  # docs/07 §4: a fallback plan has no cell
    assert ws.plan is plan


def test_both_rungs_failing_gives_the_default_two_branch_plan(ws, monkeypatch) -> None:
    """docs/03 §13: "a default two-branch plan is used (primary policy + recent
    changes) and tagged `fallback:default_plan`"."""

    class Dies:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            raise RuntimeError("structured output unavailable")

    monkeypatch.setattr(root, "structured", lambda *a, **k: Dies())
    model = ScriptedChatModel(script=[AIMessage(content="no block"), AIMessage(content="none")])
    outcome = plan_run(ws, model=model)

    assert outcome.mode == "default"
    assert outcome.fallback_tag == "fallback:default_plan"
    from prime_search import events as event_log

    plans = [r["payload"] for r in event_log.replay(ws.run_id) if r["type"] == "plan"]
    assert plans and plans[-1]["code"] is None  # docs/07 §4: a fallback plan has no cell
    assert len(outcome.plan.branches) == 2
    assert outcome.plan.branches[0].source_hint == "primary_policy"
    # The objective is substituted in, not left as a template hole.
    assert "{objective}" not in outcome.plan.branches[0].question
    assert ws.objective in outcome.plan.branches[0].question


def test_an_endpoint_failure_drops_straight_to_the_next_rung(ws, monkeypatch) -> None:
    """A 500 is not something a repair turn can fix, so it must not consume one."""
    calls: list[int] = []

    class Dies(ScriptedChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(1)
            raise RuntimeError("nebius 500")

    class FakeCaller:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            raise RuntimeError("also down")

    monkeypatch.setattr(root, "structured", lambda *a, **k: FakeCaller())
    outcome = plan_run(ws, model=Dies())

    assert len(calls) == 1  # not retried
    assert outcome.mode == "default"


def test_the_model_cannot_fabricate_the_budget_or_the_understanding(ws) -> None:
    """A model constructing SearchPlan by hand routinely invents both. Neither is its
    call: `dispatch` would believe a fabricated max_searches."""
    forged = GOOD_CELL.replace("budget=ws.budget", "budget=Budget(max_searches=9999)").replace(
        "understanding=ws.understanding",
        'understanding=QueryUnderstanding(normalized_question="wrong", domain="other",'
        ' question_type="other", time_sensitivity="low")',
    )
    model = ScriptedChatModel(script=[AIMessage(content=forged)])
    outcome = plan_run(ws, model=model)

    assert outcome.plan.budget.max_searches == ws.budget.max_searches
    assert outcome.plan.understanding.domain == "cgm"


def test_fast_depth_narrows_the_contract(ws) -> None:
    """docs/03 §10: fast plans <= 2 branches."""
    two = '''```python
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(branch_id="b1", question="criteria?", rationale="r",
               source_hint="primary_policy", priority=1),
        Branch(branch_id="b2", question="current?", rationale="r",
               source_hint="primary_policy", priority=2),
    ],
    stop_criteria="cited",
    budget=ws.budget,
)
```'''
    model = ScriptedChatModel(script=[AIMessage(content=two)])
    outcome = plan_run(ws, depth="fast", max_branches=2, model=model)
    assert outcome.mode == "code"
    assert len(outcome.plan.branches) == 2

    # And the deep-sized plan is rejected under fast.
    model = ScriptedChatModel(script=[AIMessage(content=GOOD_CELL), AIMessage(content=two)])
    outcome = plan_run(ws, depth="fast", max_branches=2, model=model)
    assert outcome.repairs == 1


def test_the_prompt_carries_the_domain_strategy_card(ws) -> None:
    """docs/03 §3 requires the card; a planner without it plans generically."""
    model = ScriptedChatModel(script=[AIMessage(content=GOOD_CELL)])
    plan_run(ws, model=model)
    prompt = "\n".join(str(m.content) for m in model.seen[0])
    assert "L33822" in prompt and "A52464" in prompt
    assert "ws.plan" in prompt  # the workspace API docstring


def test_the_glp1_card_points_at_sources_rather_than_asserting_answers() -> None:
    """The card is authored (no spec contains one). It must not hand the model the
    conclusions the bench measures - the teaching-to-the-test problem the 1.6 spec
    review flagged in search_agent.md."""
    card = strategy_card("glp1")
    assert "Part B" in card and "Part D" in card
    lowered = card.lower()
    assert "is not covered" not in lowered
    assert "is covered" not in lowered


def test_an_unknown_domain_still_gets_usable_guidance() -> None:
    card = strategy_card("other")
    assert "primary sources" in card.lower()

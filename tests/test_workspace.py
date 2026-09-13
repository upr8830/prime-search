"""Workspace and the code-as-action sandbox (docs/02 §3, docs/03 §12).

docs/09 §1.4 requires three of these: the sandbox blocks `open`/`__import__`, a
plan-constructing cell round-trips, and the timeout fires.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime

import pytest

from prime_search.config import Budget
from prime_search.schemas import (
    Document,
    Evidence,
    Location,
    QueryUnderstanding,
    SearchPlan,
    SearchTask,
)
from prime_search.workspace import MAX_STDOUT_CHARS, Workspace, new_run_id

PLAN_CELL = '''
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(
            branch_id="b1",
            question="What are the LCD coverage criteria for therapeutic CGM?",
            hypothesis="Insulin treatment or problematic hypoglycemia is required",
            rationale="The LCD is the operative rule",
            source_hint="primary_policy",
            priority=1,
        ),
        Branch(
            branch_id="b2",
            question="Has the CGM policy changed recently?",
            hypothesis=None,
            rationale="Coverage criteria were revised",
            source_hint="news",
            priority=2,
            depends_on=["b1"],
        ),
    ],
    stop_criteria="Both branches resolved against a primary source with dates",
    budget=ws.budget,
)
print("branches:", len(ws.plan.branches))
'''


@pytest.fixture
def ws() -> Workspace:
    return Workspace(
        objective="Is a therapeutic CGM covered for a type 2 diabetic not on insulin?",
        understanding=QueryUnderstanding(
            normalized_question="Is a therapeutic CGM covered ...",
            domain="cgm",
            question_type="eligibility",
            time_sensitivity="medium",
        ),
    )


# --- docs/09 §1.4 test 1: the sandbox blocks open/__import__ ----------------------


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("open", 'open("secrets.txt")'),
        ("__import__", '__import__("os").getcwd()'),
        ("import statement", "import os"),
        ("from-import", "from os import getcwd"),
        ("eval", 'eval("1+1")'),
        ("exec", 'exec("x = 1")'),
    ],
)
def test_the_sandbox_refuses_dangerous_names(ws: Workspace, name: str, code: str) -> None:
    """docs/03 §12 names all four denials; the import *statement* is covered too,
    because it compiles to a `__import__` lookup."""
    result = ws.exec(code)
    assert not result.ok
    assert result.error
    assert not result.timed_out


def test_a_refused_cell_returns_text_rather_than_raising(ws: Workspace) -> None:
    """docs/03 §12: "Any exception is returned as text; the root gets one repair
    turn." A raise here would kill the graph instead of prompting a repair."""
    result = ws.exec("open('x')")
    assert "NameError" in result.error
    assert "ERROR" in result.as_text()


def test_safe_computation_still_works(ws: Workspace) -> None:
    result = ws.exec("print(sorted({3, 1, 2}), len('abc'), max(1, 2))")
    assert result.ok
    assert result.stdout.strip() == "[1, 2, 3] 3 2"


# --- docs/09 §1.4 test 2: a plan-constructing cell round-trips --------------------


def test_a_plan_constructing_cell_round_trips(ws: Workspace) -> None:
    """The docs/03 §3 shape: the root writes its plan as Python, the harness runs it,
    and `ws.plan` is a validated SearchPlan afterwards."""
    result = ws.exec(PLAN_CELL)

    assert result.ok, result.error
    assert result.stdout.strip() == "branches: 2"
    assert isinstance(ws.plan, SearchPlan)  # mutated in place, not in a copy
    assert [branch.branch_id for branch in ws.plan.branches] == ["b1", "b2"]
    assert ws.plan.branches[0].source_hint == "primary_policy"
    assert ws.plan.budget == ws.budget  # the cell could reach ws.budget at all
    assert ws.plan.understanding is ws.understanding


def test_an_invalid_plan_cell_surfaces_the_validation_error(ws: Workspace) -> None:
    """Pydantic validates inside the cell, so a bad plan is a repairable message
    rather than a silently malformed workspace."""
    result = ws.exec(
        'ws.plan = SearchPlan(understanding=ws.understanding, branches=[], '
        'stop_criteria="x", budget="not-a-budget")'
    )
    assert not result.ok
    assert "ValidationError" in result.error or "validation error" in result.error.lower()
    assert ws.plan is None


def test_each_cell_gets_a_fresh_namespace_but_ws_persists(ws: Workspace) -> None:
    """Locals must not leak between cells — a failed cell's half-bound names would
    otherwise confuse the repair turn — while `ws` is the state that does carry."""
    assert ws.exec("scratch = 41").ok
    assert not ws.exec("print(scratch)").ok  # gone
    ws.exec('ws.unknowns.append("a date could not be found")')
    assert ws.unknowns == ["a date could not be found"]


# --- docs/09 §1.4 test 3: the timeout fires ---------------------------------------


def test_the_timeout_fires_on_a_runaway_cell(ws: Workspace) -> None:
    started = time.monotonic()
    result = ws.exec("while True: pass", timeout=1.0)
    elapsed = time.monotonic() - started

    assert result.timed_out
    assert not result.ok
    assert elapsed < 3.0  # actually interrupted, not merely joined and abandoned
    assert "exceeded" in result.error
    assert "TIMEOUT" in result.as_text()


def test_the_timeout_does_not_fire_on_ordinary_work(ws: Workspace) -> None:
    result = ws.exec("total = sum(range(100000))\nprint(total)", timeout=5.0)
    assert result.ok and not result.timed_out


# --- stdout handling (docs/03 §12) ------------------------------------------------


def test_stdout_is_truncated_with_a_note(ws: Workspace) -> None:
    result = ws.exec('print("x" * 10000)')
    assert result.ok
    assert len(result.stdout) <= MAX_STDOUT_CHARS + len("\n... [output truncated at 4000 chars]")
    assert "truncated" in result.stdout


def test_a_cell_with_no_output_says_so(ws: Workspace) -> None:
    assert ws.exec("x = 1").as_text() == "(no output)"


# --- workspace helpers (docs/02 §3) -----------------------------------------------


def _document(doc_id: str, tier: str, **kwargs) -> Document:
    return Document(
        doc_id=doc_id,
        url=f"https://example.gov/{doc_id}",
        title=doc_id,
        source_tier=tier,  # type: ignore[arg-type]
        retrieved_at=datetime.now(UTC),
        fetch_method=kwargs.pop("fetch_method", "extract"),
        text_path=kwargs.pop("text_path", f"/tmp/{doc_id}.txt"),
        paragraph_count=kwargs.pop("paragraph_count", 30),
        **kwargs,
    )


def _evidence(evidence_id: str, branch_id: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        doc_id="doc_a",
        branch_id=branch_id,
        claim_text="c",
        evidence_text="verbatim",
        location=Location(paragraph_index=0, char_start=0, char_end=8),
        relevance=0.8,
        source_quality=1.0,
        confidence=0.9,
        stance="supports",
    )


def test_evidence_for_filters_by_branch(ws: Workspace) -> None:
    ws.evidence = [_evidence("e1", "b1"), _evidence("e2", "b2"), _evidence("e3", "b1")]
    assert [e.evidence_id for e in ws.evidence_for("b1")] == ["e1", "e3"]
    assert ws.evidence_for("b9") == []


def test_docs_by_tier_supports_exact_and_threshold(ws: Workspace) -> None:
    """docs/05's primary_source_ratio needs "official_secondary or better"."""
    ws.documents = {
        "a": _document("a", "primary_policy"),
        "b": _document("b", "official_secondary"),
        "c": _document("c", "web"),
    }
    assert [d.doc_id for d in ws.docs_by_tier("primary_policy")] == ["a"]
    assert sorted(d.doc_id for d in ws.docs_by_tier("official_secondary", at_least=True)) == [
        "a",
        "b",
    ]


def test_dates_reports_the_governing_date_not_only_effective(ws: Workspace) -> None:
    """Measured on the live pages: both CMS flagship documents carry a revision date
    and no effective date, so an effective-only helper would return nothing for
    exactly the documents docs/03 §12 cites as its reason for existing."""
    ws.documents = {
        "a": _document("a", "primary_policy", revision_date=date(2024, 10, 1)),
        "b": _document("b", "primary_policy", effective_date=date(2015, 10, 1)),
        "c": _document("c", "web", fetch_method="snippet_only", text_path="", paragraph_count=0),
    }
    assert dict(ws.dates()) == {"a": date(2024, 10, 1), "b": date(2015, 10, 1)}
    assert "c" not in dict(ws.dates())  # never fetched, so nothing is known about it


def test_budget_remaining_subtracts_usage_and_floors_at_zero(ws: Workspace) -> None:
    ws.budget = Budget(max_searches=5, max_fetches=2)
    ws.usage.searches = 3
    ws.usage.fetches = 9  # over budget: must not report a negative allowance
    remaining = ws.budget_remaining()
    assert remaining.max_searches == 2
    assert remaining.max_fetches == 0


def test_budget_remaining_does_not_spend_agents_run_wide(ws: Workspace) -> None:
    """max_agents caps each round (docs/11): subtracting the agents already dispatched
    left a deep run with a 6-branch plan no agents for any judge or critic re-search."""
    ws.budget = Budget(max_agents=6)
    ws.usage.agents = 6
    assert ws.budget_remaining().max_agents == 6


def test_search_tree_is_derived_from_tasks_and_evidence(ws: Workspace) -> None:
    ws.tasks = [
        SearchTask(task_id="t1", branch_id="b1", round=0, instruction="x", status="done"),
        SearchTask(task_id="t2", branch_id="b2", round=0, instruction="y", status="running"),
    ]
    ws.evidence = [_evidence("e1", "b1")]
    tree = ws.search_tree
    assert tree["b1"] == {"tasks": ["t1"], "evidence_ids": ["e1"], "status": "resolved"}
    assert tree["b2"]["status"] == "running"


def test_a_cell_can_inspect_the_workspace_the_way_docs_03_12_describes(ws: Workspace) -> None:
    """The RLM property: the root reasons over stored objects instead of re-reading
    documents through its context."""
    ws.documents = {"a": _document("a", "primary_policy", revision_date=date(2024, 10, 1))}
    ws.evidence = [_evidence("e1", "b3")]
    result = ws.exec(
        "print(len(ws.evidence_for('b3')), ws.dates(), ws.budget_remaining().max_searches)"
    )
    assert result.ok, result.error
    assert result.stdout.strip().startswith("1 [('a', datetime.date(2024, 10, 1))]")


def test_run_id_is_a_time_ordered_uuid7() -> None:
    """docs/02 §2.1 says uuid7; the point is that runs/ sorts chronologically."""
    first = new_run_id()
    time.sleep(0.005)
    second = new_run_id()
    assert uuid.UUID(first).version == 7
    assert first < second


# --- regressions and gaps found by the 1.4 spec review ---------------------------


def test_the_traceback_keeps_the_exception_message(ws: Workspace) -> None:
    """The harness-frame filter used to drop any line containing "in run", which ate
    the final `ValueError: ...` line and left the root nothing to repair."""
    result = ws.exec("label = 'in run order'\nraise ValueError(label)")
    assert not result.ok
    assert "ValueError: in run order" in result.error


def test_the_traceback_hides_the_harness_frame(ws: Workspace) -> None:
    """The root is told `exec` is forbidden; its error must not open with a call to
    `exec(compile(...))` from this module."""
    result = ws.exec("raise ValueError('boom')")
    assert "compile(code" not in result.error
    assert "workspace.py" not in result.error
    assert '"<cell>"' in result.error  # the cell's own frame survives


def test_a_cell_can_define_a_class_and_catch_an_error(ws: Workspace) -> None:
    """`class` compiles to a __build_class__ lookup and a defensive try/except needs
    to name what it catches; both used to fail with a bare NameError."""
    assert ws.exec("class Tally: pass\nprint(Tally.__name__)").stdout.strip() == "Tally"
    caught = ws.exec("try:\n    1 / 0\nexcept ZeroDivisionError:\n    print('caught')")
    assert caught.stdout.strip() == "caught"


def test_cell_output_does_not_capture_other_threads(ws: Workspace) -> None:
    """The cell owns `print` rather than swapping sys.stdout process-wide: a global
    redirect would have swallowed structlog and any streaming answer for the
    duration of every cell."""
    import sys as real_sys

    before = real_sys.stdout
    result = ws.exec("print('inside')")
    assert result.stdout.strip() == "inside"
    assert real_sys.stdout is before  # never swapped


# --- search_within from a cell ----------------------------------------------------


@pytest.fixture
def fetched_ws(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    from prime_search.config import get_settings
    from prime_search.primitives import docmeta

    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-" + "x" * 24)
    monkeypatch.setenv("NEBIUS_API_KEY", "n" * 24)
    monkeypatch.setenv("PRIME_TAVILY_CACHE_DIR", str(tmp_path))

    text = docmeta.normalize_text(
        "## Coverage Guidance\n\n"
        "A therapeutic CGM is covered when the beneficiary is treated with insulin.\n\n"
        "The beneficiary must have a history of problematic hypoglycemia.\n\n"
        + "\n\n".join(f"Filler {i}." for i in range(10))
    )
    path = tmp_path / "docs" / "doc_a.txt"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8", newline="\n")

    workspace = Workspace(objective="x")
    workspace.documents["doc_a"] = _document(
        "doc_a",
        "primary_policy",
        text_path=str(path),
        paragraph_count=len(docmeta.split_paragraphs(text)),
    )
    yield workspace
    get_settings.cache_clear()


def test_search_within_returns_citable_passages_and_counts_a_deep_read(
    fetched_ws: Workspace,
) -> None:
    passages = fetched_ws.search_within("doc_a", "problematic hypoglycemia insulin", k=2)
    assert passages
    assert "problematic hypoglycemia" in passages[0]["text"]
    assert set(passages[0]) >= {"paragraph_index", "text", "char_start", "char_end"}
    assert fetched_ws.usage.deep_reads == 1  # budgeted (docs/01 §3 max_deep_reads)


def test_search_within_from_inside_a_cell(fetched_ws: Workspace) -> None:
    """docs/02 §3's stated use: the root sees specific paragraphs without the
    document ever entering its context."""
    result = fetched_ws.exec("print(len(ws.search_within('doc_a', 'insulin', k=1)))")
    assert result.ok, result.error
    assert result.stdout.strip() == "1"


def test_search_within_refuses_an_unknown_document(fetched_ws: Workspace) -> None:
    with pytest.raises(KeyError, match="search first"):
        fetched_ws.search_within("doc_missing", "insulin")


def test_search_within_refuses_a_path_outside_the_run(fetched_ws: Workspace, tmp_path) -> None:
    """A cell can put a Document of its own into ws.documents, so the path is checked
    rather than trusted — docs/01 §8 says the sandbox does no file I/O."""
    outside = tmp_path.parent / "elsewhere.txt"
    outside.write_text("secret", encoding="utf-8")
    fetched_ws.documents["doc_evil"] = _document("doc_evil", "web", text_path=str(outside))
    with pytest.raises(ValueError, match="outside this run"):
        fetched_ws.search_within("doc_evil", "secret")


def test_search_within_stops_at_the_deep_read_budget(fetched_ws: Workspace) -> None:
    fetched_ws.budget = Budget(max_deep_reads=1)
    fetched_ws.search_within("doc_a", "insulin")
    with pytest.raises(ValueError, match="deep-read budget exhausted"):
        fetched_ws.search_within("doc_a", "insulin")


# --- persistence ------------------------------------------------------------------


def test_to_record_uses_the_runs_start_not_the_projection_time(ws: Workspace) -> None:
    """Stamping datetime.now() here recorded the moment the record was written, i.e.
    the run's end."""
    from prime_search.schemas import RunRequest

    record = ws.to_record(RunRequest(question=ws.objective))
    assert record.started_at == ws.started_at
    assert record.started_at.tzinfo is not None
    assert record.run_id == ws.run_id


def test_to_record_carries_the_search_and_accepts_the_graphs_fields(ws: Workspace) -> None:
    from prime_search.schemas import Answer, RunRequest

    ws.tasks = [SearchTask(task_id="t1", branch_id="b1", round=0, instruction="x")]
    ws.evidence = [_evidence("e1", "b1")]
    answer = Answer(summary="s", body_markdown="b", confidence=0.7)

    record = ws.to_record(
        RunRequest(question=ws.objective),
        answer=answer,
        status="completed",
        finished_at=datetime.now(UTC),
    )
    assert [t.task_id for t in record.tasks] == ["t1"]
    assert [e.evidence_id for e in record.evidence] == ["e1"]
    assert record.answer is answer
    assert record.status == "completed"
    assert record.finished_at is not None


def test_new_workspace_takes_the_budget_for_the_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    from prime_search.config import get_settings
    from prime_search.workspace import new_workspace

    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-" + "x" * 24)
    monkeypatch.setenv("NEBIUS_API_KEY", "n" * 24)
    try:
        assert new_workspace("q", "fast").budget.max_searches == 3  # docs/01 §3
        assert new_workspace("q", "deep").budget.max_searches == 30
    finally:
        get_settings.cache_clear()


def test_a_branch_with_evidence_but_no_task_is_not_stuck_pending(ws: Workspace) -> None:
    ws.evidence = [_evidence("e1", "b7")]
    assert ws.search_tree["b7"]["status"] == "resolved"


def test_to_record_carries_verdicts_and_critic_reports(ws: Workspace) -> None:
    from prime_search.schemas import CriticReport, RunRequest, Verdict

    ws.verdicts.append(
        Verdict(round=0, sufficient=False, coverage={"b1": "partial"}, missing=["dates"], reasoning="r")
    )
    ws.critic_reports.append(CriticReport(completion_probability=0.6, reasoning="r"))

    record = ws.to_record(RunRequest(question=ws.objective))
    assert record.verdicts[0].coverage == {"b1": "partial"}
    assert record.critic_reports[0].completion_probability == 0.6


def test_charge_tokens_adds_a_replys_usage(ws: Workspace) -> None:
    from langchain_core.messages import AIMessage

    message = AIMessage(
        content="x", usage_metadata={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}
    )
    ws.charge_tokens(message)
    assert (ws.usage.input_tokens, ws.usage.output_tokens) == (10, 4)


def test_limit_notes_are_plain_language() -> None:
    """The answer's Unknowns are read by people deciding on coverage: no numbers, no
    "budget" or "tokens", no internal limit names (user decision, docs/11)."""
    import re
    from datetime import UTC, datetime, timedelta

    from prime_search.config import Budget

    run = Workspace(
        objective="q",
        budget=Budget(max_searches=1, max_fetches=1, max_deep_reads=1, max_tokens=10, max_seconds=1),
    )
    run.usage.searches = run.usage.fetches = run.usage.deep_reads = 1
    run.usage.input_tokens = 10
    run.started_at = datetime.now(UTC) - timedelta(seconds=5)

    limits = dict(run.exhausted_limits())
    assert set(limits) == {"max_seconds", "max_searches", "max_fetches", "max_deep_reads", "max_tokens"}
    for note in limits.values():
        assert not re.search(r"budget|token|max_|\d", note, re.IGNORECASE), note

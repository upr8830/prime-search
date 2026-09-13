"""The search sub-agent (docs/03 §4, §13).

Everything here runs with a scripted model and stubbed Tavily: the loop, the
tool-call cap, the verbatim rejection path and `TaskResult` assembly are properties
of this module, not of the network. The live docs/09 §1.6 Check is in
tests/test_search_agent_live.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from prime_search import events
from prime_search.agents import search_agent
from prime_search.agents.search_agent import (
    MAX_TOOL_CALLS,
    PROMPT_SPLIT_MARKER,
    run_search_agent,
)
from prime_search.config import Budget, get_settings
from prime_search.prompts import load, render
from prime_search.schemas import Document, SearchTask

from conftest import ScriptedChatModel, tool_call

DOC_ID = "doc_lcd33822"
URL = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"
PARAGRAPHS = [
    "Local Coverage Determination (LCD): Glucose Monitors (L33822)",
    "Revision Effective Date: 04/16/2023",
    "The beneficiary is insulin-treated or has a history of problematic hypoglycemia.",
    "The beneficiary has been seen by the treating practitioner within six months.",
]
CRITERIA = "The beneficiary is insulin-treated or has a history of problematic hypoglycemia."


def _task(**kwargs) -> SearchTask:
    return SearchTask(
        task_id=kwargs.pop("task_id", "t1"),
        branch_id=kwargs.pop("branch_id", "b1"),
        round=kwargs.pop("round", 0),
        instruction=kwargs.pop(
            "instruction", "Find the current LCD coverage criteria for therapeutic CGM."
        ),
        **kwargs,
    )


def _install_fake_tavily(monkeypatch, *, search_error: str | None = None):
    """Stub search/fetch at the names search_agent imported them under.

    The fake fetch does what the real one does to the caller's `docs` mapping — writes
    the text, sets paragraph_count, flips fetch_method — because everything downstream
    (within.load_paragraphs, EvidenceStore.add) reads those, not Tavily.
    """
    from prime_search.primitives import docmeta
    from prime_search.primitives.tavily import FetchResult, SearchHit, SearchResult

    def fake_search(query, *, include_domains=None, time_range=None, docs=None, **kwargs):
        if search_error:
            return SearchResult(query=query, hits=[], cached=False, error=search_error)
        hit = SearchHit(
            doc_id=DOC_ID,
            url=URL,
            title="LCD L33822 Glucose Monitors",
            snippet="x" * 900,  # long enough to prove the clip
            tier="primary_policy",
            date_hint="2023-04-16",
        )
        if docs is not None and DOC_ID not in docs:
            docs[DOC_ID] = Document(
                doc_id=DOC_ID,
                url=URL,
                title=hit.title,
                source_tier="primary_policy",
                retrieved_at=datetime.now(UTC),
                fetch_method="snippet_only",
            )
        return SearchResult(query=query, hits=[hit], cached=False)

    def fake_fetch(target, *, docs=None, run_dir=None, **kwargs):
        text = docmeta.normalize_text("\n\n".join(PARAGRAPHS))
        path = Path(get_settings().tavily_cache_dir) / "docs" / f"{DOC_ID}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        document = Document(
            doc_id=DOC_ID,
            url=URL,
            title="LCD L33822 Glucose Monitors",
            source_tier="primary_policy",
            publisher="CMS",
            doc_type="LCD",
            document_id_external="L33822",
            revision_date=date(2023, 4, 16),
            retrieved_at=datetime.now(UTC),
            text_path=str(path),
            paragraph_count=len(docmeta.split_paragraphs(text)),
            fetch_method="extract",
        )
        if docs is not None:
            docs[DOC_ID] = document
        return FetchResult(document=document, sections=["Coverage Indications"])

    monkeypatch.setattr(search_agent.tavily, "search", fake_search)
    monkeypatch.setattr(search_agent.tavily, "fetch", fake_fetch)


def _last_tool_message(prompt):
    return next(m for m in reversed(prompt) if getattr(m, "type", "") == "tool")


# --- the happy path ----------------------------------------------------------------


def test_task_result_is_built_from_the_tool_log(sandboxed_run, monkeypatch) -> None:
    """docs/03 §4's TaskResult. Assembled from what the tools actually did, not from
    a structured-output call the model might fumble."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[tool_call("search", query="CGM LCD criteria", include_domains=["cms.gov"])],
            ),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(
                content="",
                tool_calls=[tool_call("search_within", doc_id=DOC_ID, query="insulin")],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=2,
                        claim_text="Coverage requires insulin treatment or problematic hypoglycemia",
                        evidence_text=CRITERIA,
                        stance="supports",
                        confidence=0.9,
                    )
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=1,
                        claim_text="LCD L33822 revision effective 2023-04-16",
                        evidence_text="Revision Effective Date: 04/16/2023",
                        stance="context",
                    )
                ],
            ),
            AIMessage(content="CGM coverage turns on insulin treatment.\nUnresolved: the codes."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)

    assert result.queries_issued == ["CGM LCD criteria"]
    assert result.documents_fetched == [DOC_ID]
    assert len(result.evidence_ids) == 2
    assert result.summary == "CGM coverage turns on insulin treatment."
    assert result.unresolved == "the codes."
    assert (result.usage.searches, result.usage.fetches, result.usage.deep_reads) == (1, 1, 1)
    assert result.usage.agents == 1
    # The tools charge the run, not only the task — dispatch's siblings must see it.
    assert sandboxed_run.usage.searches == 1
    # branch_id is injected from the task and never asked of the model.
    assert [item.branch_id for item in sandboxed_run.evidence] == ["b1", "b1"]
    assert {item.stance for item in sandboxed_run.evidence} == {"supports", "context"}


def test_the_five_spec_tools_are_bound(sandboxed_run, monkeypatch) -> None:
    """docs/03 §4's tool table is exactly five; a sixth would be a tool the frozen
    prompt never taught."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(script=[AIMessage(content="Nothing to do.")])
    run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert model.bound_tools == [
        "search",
        "fetch",
        "search_within",
        "add_evidence",
        "note_unresolved",
    ]


def test_no_documents_travel_back_to_the_root(sandboxed_run, monkeypatch) -> None:
    """docs/03 §4: "The subgraph never returns raw documents to the root; only ids.\""""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(content="Done."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    serialized = result.model_dump_json()
    assert DOC_ID in serialized  # the id travels
    assert CRITERIA not in serialized  # the text does not
    assert "http" not in serialized


# --- docs/03 §13: the tool-call cap ------------------------------------------------


def test_the_tool_call_cap_ends_the_loop_and_sets_unresolved(sandboxed_run, monkeypatch) -> None:
    """docs/03 §13: the 9th call raises, the model is asked to summarize what it has,
    and TaskResult.unresolved records why it stopped."""
    _install_fake_tavily(monkeypatch)
    sandboxed_run.budget = Budget(max_searches=50)
    searches = [
        AIMessage(content="", tool_calls=[tool_call("search", query=f"q{i}")]) for i in range(9)
    ]
    model = ScriptedChatModel(script=[*searches, AIMessage(content="Partial.\nUnresolved: ran out.")])

    result = run_search_agent(_task(), ws=sandboxed_run, model=model)

    assert result.usage.searches == MAX_TOOL_CALLS  # eight ran; the ninth never did
    assert len(result.queries_issued) == MAX_TOOL_CALLS
    assert "This line of research stopped before it was finished." in result.unresolved
    assert "tool-call cap" not in result.unresolved  # plain words in the answer (docs/11)
    assert result.summary == "Partial."  # from the summarize-what-you-have call
    # That call must not carry a tool call with no result, or the endpoint 400s.
    final_prompt = model.seen[-1]
    assert not (getattr(final_prompt[-2], "tool_calls", None) or [])


def test_a_smaller_cap_is_honoured(sandboxed_run, monkeypatch) -> None:
    """1.7 passes a smaller cap for `fast` depth, which is why it is a parameter
    rather than a Budget field."""
    _install_fake_tavily(monkeypatch)
    sandboxed_run.budget = Budget(max_searches=50)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query=f"q{i}")]) for i in range(5)
        ]
        + [AIMessage(content="Stopped.")]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model, max_tool_calls=2)
    assert result.usage.searches == 2


# --- docs/04 §3 rules, surfaced to the model ---------------------------------------


def test_a_paraphrase_is_rejected_with_the_paragraph_and_the_retry_lands(
    sandboxed_run, monkeypatch
) -> None:
    """docs/04 §3 rule 2. The rejection must carry the real paragraph back, or the
    model has nothing to correct against."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=2,
                        claim_text="Insulin is required",
                        evidence_text="Beneficiaries need insulin to qualify",  # paraphrase
                    )
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=2,
                        claim_text="Insulin is required",
                        evidence_text=CRITERIA,  # the real thing
                    )
                ],
            ),
            AIMessage(content="Fixed it."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)

    rejection = next(
        m for prompt in model.seen for m in prompt
        if getattr(m, "type", "") == "tool" and "not a verbatim passage" in m.content
    )
    assert "insulin-treated" in rejection.content  # the paragraph came back
    assert len(result.evidence_ids) == 1  # the corrected call landed


def test_evidence_from_a_snippet_is_refused_as_text(sandboxed_run, monkeypatch) -> None:
    """docs/04 §3 rule 1, surfaced as a tool message rather than an exception, so the
    agent can recover by fetching."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=0,
                        claim_text="c",
                        evidence_text="anything",
                    )
                ],
            ),
            AIMessage(content="I should have fetched."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert result.evidence_ids == []
    assert "snippet" in _last_tool_message(model.seen[-1]).content


# --- docs/01 §9: errors are text and still cost -------------------------------------


def test_a_tavily_error_is_returned_as_text_and_still_counts(sandboxed_run, monkeypatch) -> None:
    """docs/01 §9: "the sub-agent sees it and may retry once with a reformulated
    query; the budget still counts the call.\""""
    _install_fake_tavily(monkeypatch, search_error="rate limit exceeded")
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q1")]),
            AIMessage(content="", tool_calls=[tool_call("search", query="q2")]),
            AIMessage(content="Could not search."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)

    assert result.queries_issued == ["q1", "q2"]  # issued is issued
    assert result.usage.searches == 2  # the failed calls still cost
    assert "rate limit" in _last_tool_message(model.seen[-1]).content


# --- the two kinds of exhaustion ---------------------------------------------------


def test_a_spent_task_slice_refuses_but_the_agent_keeps_working(
    sandboxed_run, monkeypatch
) -> None:
    """A task slice running out must not end the run's work: the agent can still
    quote the documents it already fetched."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q1")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(content="", tool_calls=[tool_call("search", query="q2")]),  # refused
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=2,
                        claim_text="Insulin or hypoglycemia",
                        evidence_text=CRITERIA,
                    )
                ],
            ),
            AIMessage(content="Worked with what I had."),
        ]
    )
    result = run_search_agent(
        _task(), ws=sandboxed_run, model=model, budget=Budget(max_searches=1, max_fetches=2)
    )
    assert result.usage.searches == 1
    assert len(result.evidence_ids) == 1  # it kept going after the refusal


def test_an_exhausted_run_budget_ends_the_agent(sandboxed_run, monkeypatch) -> None:
    """The run running out is different: no call by anyone can succeed, so continuing
    only burns context."""
    _install_fake_tavily(monkeypatch)
    sandboxed_run.budget = Budget(max_searches=0)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q1")]),
            AIMessage(content="Stopped."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert result.usage.searches == 0
    assert "This line of research stopped before it was finished." in result.unresolved and "max_searches" not in result.unresolved


# --- events (docs/02 §4, docs/06 §4) -----------------------------------------------


def test_events_are_written_for_replay(sandboxed_run, monkeypatch) -> None:
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(
                content="",
                tool_calls=[
                    tool_call(
                        "add_evidence",
                        doc_id=DOC_ID,
                        paragraph_index=2,
                        claim_text="Insulin or hypoglycemia",
                        evidence_text=CRITERIA,
                    )
                ],
            ),
            AIMessage(content="Done."),
        ]
    )
    run_search_agent(_task(), ws=sandboxed_run, model=model)

    recorded = list(events.replay(sandboxed_run.run_id))
    types = [event["type"] for event in recorded]
    assert types[0] == "task.started" and types[-1] == "task.done"
    assert {"search", "fetch", "evidence"} <= set(types)
    # docs/02 §4's fetch payload, exactly.
    fetch_event = next(e for e in recorded if e["type"] == "fetch")
    assert set(fetch_event["payload"]) == {
        "task_id",
        "doc_id",
        "url",
        "title",
        "tier",
        "effective_date",
    }
    assert all(event["run_id"] == sandboxed_run.run_id for event in recorded)


def test_note_unresolved_reaches_the_workspace(sandboxed_run, monkeypatch) -> None:
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[tool_call("note_unresolved", text="No HCPCS codes were stated.")],
            ),
            AIMessage(content="Done."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert "No HCPCS codes were stated." in sandboxed_run.unknowns  # docs/02 §3
    assert "No HCPCS codes" in result.unresolved


# --- context hygiene ----------------------------------------------------------------


def test_tool_returns_are_clipped_for_the_context_window(sandboxed_run, monkeypatch) -> None:
    """A 900-char snippet and a long paragraph must not arrive whole; the real
    documents run to 52 KB in a single table paragraph."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="Done."),
        ]
    )
    run_search_agent(_task(), ws=sandboxed_run, model=model)
    content = _last_tool_message(model.seen[-1]).content
    assert "x" * 900 not in content
    assert len(content) < 2000


def test_an_empty_final_message_still_yields_a_summary(sandboxed_run, monkeypatch) -> None:
    """The tree view needs a sentence, and every fact in it is already in the log."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content=""),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert "1 queries" in result.summary
    assert "no closing summary" in result.summary


# --- the frozen prompt (docs/05 §5) -------------------------------------------------


def test_the_prompt_has_its_split_marker_and_every_placeholder() -> None:
    """The prompt is frozen — GEPA never rewrites it — so the marker and placeholder
    names are a contract search_agent.py depends on."""
    text = load("search_agent")
    assert PROMPT_SPLIT_MARKER in text
    for key in (
        "instruction",
        "hypothesis",
        "source_hint",
        "queries_hint",
        "include_domains",
        "time_range",
        "budget",
    ):
        assert "{" + key + "}" in text

    rendered = render(
        "search_agent",
        instruction="I",
        hypothesis="H",
        source_hint="S",
        queries_hint="Q",
        include_domains="D",
        time_range="T",
        budget="B",
    )
    kickoff = rendered.split(PROMPT_SPLIT_MARKER)[1]
    assert "{" not in kickoff  # nothing left unfilled in the task block


def test_the_prompt_states_the_rules_the_tools_enforce() -> None:
    """docs/03 §11's seed checklist: the §4 rules, tool descriptions, an add_evidence
    example, and an explicit "snippets are not evidence" line."""
    text = load("search_agent").lower()
    assert "snippets are not evidence" in text
    assert "add_evidence(" in text  # the worked example
    for tool_name in ("search(", "fetch(", "search_within(", "note_unresolved("):
        assert tool_name in text


@pytest.mark.parametrize("field", ["instruction", "hypothesis", "source_hint", "budget"])
def test_the_task_block_carries_what_section_4_promises(
    sandboxed_run, monkeypatch, field: str
) -> None:
    """docs/03 §4: "the agent receives the task instruction, the branch hypothesis,
    source hint, and remaining per-task budget.\""""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(script=[AIMessage(content="Done.")])
    run_search_agent(
        _task(instruction="UNIQUE-INSTRUCTION"),
        ws=sandboxed_run,
        model=model,
        budget=Budget(max_searches=7),
    )
    prompt_text = "\n".join(str(m.content) for m in model.seen[0])
    if field == "instruction":
        assert "UNIQUE-INSTRUCTION" in prompt_text
    elif field == "budget":
        assert "7 searches" in prompt_text
    else:
        assert field.replace("_", " ") in prompt_text.lower()


# --- gaps found by the 1.6 spec review --------------------------------------------


def test_an_unexpected_error_still_returns_a_failed_task_result(
    sandboxed_run, monkeypatch
) -> None:
    """Anything other than BudgetExceeded used to escape run_search_agent entirely:
    no TaskResult, no task.done event, and the task stuck at status "running"."""
    _install_fake_tavily(monkeypatch)

    class Exploding(ScriptedChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("nebius 503")

    task = _task()
    result = run_search_agent(task, ws=sandboxed_run, model=Exploding())

    assert result is not None
    assert "stopped early because of a technical problem" in result.unresolved
    assert "nebius 503" not in result.unresolved  # the exception stays in the log
    assert task.status == "done"  # the node completed, even though the model did not
    assert task.result is result
    types = [event["type"] for event in events.replay(sandboxed_run.run_id)]
    assert types[-1] == "task.done"  # the root still learns the task ended


def test_a_missing_document_file_is_reported_not_raised(sandboxed_run, monkeypatch) -> None:
    """within.load_text does a bare read_text, so a deleted file raises OSError —
    neither KeyError nor ValueError, so it used to escape the agent."""
    _install_fake_tavily(monkeypatch)
    original = search_agent.tavily.fetch

    def fetch_then_delete(*args, **kwargs):
        result = original(*args, **kwargs)
        Path(result.document.text_path).unlink()  # gone before search_within reads it
        return result

    monkeypatch.setattr(search_agent.tavily, "fetch", fetch_then_delete)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(content="", tool_calls=[tool_call("search_within", doc_id=DOC_ID, query="x")]),
            AIMessage(content="Could not read it."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)

    assert result.summary == "Could not read it."  # the agent kept control
    assert sandboxed_run.usage.deep_reads == 1  # docs/01 §9: the failed call still cost


def test_a_failed_deep_read_still_costs_the_run(sandboxed_run, monkeypatch) -> None:
    """A failed search or fetch charges the run; a failed deep read used not to."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            # search_within on a snippet_only document: refused by the workspace.
            AIMessage(content="", tool_calls=[tool_call("search_within", doc_id=DOC_ID, query="x")]),
            AIMessage(content="Done."),
        ]
    )
    run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert sandboxed_run.usage.deep_reads == 1


def test_the_budget_nudge_reaches_the_model(sandboxed_run, monkeypatch) -> None:
    """The nudge exists because a live run spent all 8 calls and recorded nothing; if
    it never reaches the model it is not doing anything."""
    _install_fake_tavily(monkeypatch)
    sandboxed_run.budget = Budget(max_searches=50)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query=f"q{i}")]) for i in range(6)
        ]
        + [AIMessage(content="Stopping.")]
    )
    run_search_agent(_task(), ws=sandboxed_run, model=model)
    hints = [
        message.content
        for prompt in model.seen
        for message in prompt
        if getattr(message, "type", "") == "tool" and "recorded no" in str(message.content)
    ]
    assert hints, "the low-call nudge never reached the model"


def test_a_clipped_passage_is_marked_truncated(sandboxed_run, monkeypatch) -> None:
    """The model quotes what it is shown; a silent truncation invites a quote that runs
    past the cut and gets rejected."""
    from prime_search.primitives import docmeta
    from prime_search.primitives.tavily import FetchResult

    long_paragraph = " ".join(f"Clause {i} of the coverage criteria." for i in range(200))
    _install_fake_tavily(monkeypatch)
    original = search_agent.tavily.fetch

    def fetch_long(*args, **kwargs):
        result = original(*args, **kwargs)
        text = docmeta.normalize_text("## Coverage\n\n" + long_paragraph)
        Path(result.document.text_path).write_text(text, encoding="utf-8", newline="\n")
        document = result.document.model_copy(
            update={"paragraph_count": len(docmeta.split_paragraphs(text))}
        )
        kwargs["docs"][document.doc_id] = document
        return FetchResult(document=document, sections=["Coverage"])

    monkeypatch.setattr(search_agent.tavily, "fetch", fetch_long)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(
                content="",
                tool_calls=[tool_call("search_within", doc_id=DOC_ID, query="clause")],
            ),
            AIMessage(content="Read it."),
        ]
    )
    run_search_agent(_task(), ws=sandboxed_run, model=model)
    passage_message = next(
        m
        for prompt in model.seen
        for m in prompt
        if getattr(m, "type", "") == "tool" and "paragraph_index" in str(m.content)
    )
    assert "truncated" in passage_message.content
    assert len(passage_message.content) < 4000


def test_the_error_event_payload_matches_the_spec(sandboxed_run, monkeypatch) -> None:
    """docs/02 §4: error {message, node}."""
    _install_fake_tavily(monkeypatch, search_error="rate limit exceeded")
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="Failed."),
        ]
    )
    run_search_agent(_task(), ws=sandboxed_run, model=model)
    error_event = next(e for e in events.replay(sandboxed_run.run_id) if e["type"] == "error")
    assert set(error_event["payload"]) == {"message", "node"}
    assert error_event["payload"]["node"] == "search_agent:b1"


def test_orphan_tool_messages_are_dropped_with_their_parent() -> None:
    """One AIMessage can carry several tool calls. Dropping it while leaving the
    answered siblings' ToolMessages behind produces orphans the endpoint rejects just
    as firmly as the dangling call did."""
    from langchain_core.messages import ToolMessage

    from prime_search.agents.search_agent import _drop_dangling_tool_calls

    messages = [
        AIMessage(content="hi"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "search", "args": {}, "id": "a", "type": "tool_call"},
                {"name": "search", "args": {}, "id": "b", "type": "tool_call"},
            ],
        ),
        ToolMessage(content="answered", tool_call_id="a"),  # "b" never came back
    ]
    trimmed = _drop_dangling_tool_calls(messages)
    assert [type(m).__name__ for m in trimmed] == ["AIMessage"]


def test_no_trajectory_means_no_invented_summary(sandboxed_run, monkeypatch) -> None:
    """With nothing gathered, asking the model to summarize what it has invites
    invention; the deterministic fallback states the facts instead."""
    _install_fake_tavily(monkeypatch)
    sandboxed_run.budget = Budget(max_searches=0)  # the first call raises immediately
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="I found that CGMs are always covered."),  # must not be used
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert "always covered" not in result.summary
    assert "no closing summary" in result.summary


# --- paths the 1.6 review listed as untested --------------------------------------


def test_a_failed_summarize_call_does_not_fail_the_task(sandboxed_run, monkeypatch) -> None:
    """docs/03 §13's recovery path runs when a run is already going badly; if its own
    model call throws, the task must still come back with what it gathered."""
    _install_fake_tavily(monkeypatch)
    sandboxed_run.budget = Budget(max_searches=50)

    class DiesOnSummary(ScriptedChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
            if not self.script:  # the un-tooled summarize turn
                raise RuntimeError("nebius 500 on the summary")
            return super()._generate(messages, stop, run_manager, **kwargs)

    model = DiesOnSummary(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query=f"q{i}")]) for i in range(9)
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)

    assert "This line of research stopped before it was finished." in result.unresolved
    assert "tool-call cap" not in result.unresolved  # plain words in the answer (docs/11)
    assert result.summary  # the deterministic fallback stood in
    assert "8 queries" in result.summary


def test_the_deep_read_budget_race_becomes_budget_exceeded(sandboxed_run, monkeypatch) -> None:
    """Under a parallel fan-out the workspace's own re-check can fire after the tool's
    pre-check passed. It raises DeepReadBudgetExceeded, matched by type rather than by
    looking for "budget" in the message."""
    _install_fake_tavily(monkeypatch)
    from prime_search.workspace import DeepReadBudgetExceeded

    def exhausted(*args, **kwargs):
        raise DeepReadBudgetExceeded("deep-read budget exhausted (10 used)")

    monkeypatch.setattr(sandboxed_run, "search_within", exhausted)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(content="", tool_calls=[tool_call("search_within", doc_id=DOC_ID, query="x")]),
            AIMessage(content="Stopped."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert "This line of research stopped before it was finished." in result.unresolved and "budget" not in result.unresolved


def test_another_value_error_is_not_mistaken_for_the_budget(sandboxed_run, monkeypatch) -> None:
    """The same method raises ValueError for an unreadable path and for drifted
    offsets; neither may end the agent."""
    _install_fake_tavily(monkeypatch)

    def drifted(*args, **kwargs):
        raise ValueError("paragraphs on disk vs paragraph_count on the Document")

    monkeypatch.setattr(sandboxed_run, "search_within", drifted)
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[tool_call("search", query="q")]),
            AIMessage(content="", tool_calls=[tool_call("fetch", doc_id=DOC_ID)]),
            AIMessage(content="", tool_calls=[tool_call("search_within", doc_id=DOC_ID, query="x")]),
            AIMessage(content="Routed around it."),
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert result.summary == "Routed around it."  # the agent kept control
    assert "budget" not in (result.unresolved or "")


def test_reported_token_usage_is_carried_through(sandboxed_run, monkeypatch) -> None:
    """docs/06 §5: usage_metadata when the wrapper provides it."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(
        script=[
            AIMessage(
                content="Done.",
                usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
            )
        ]
    )
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert (result.usage.input_tokens, result.usage.output_tokens) == (120, 30)
    assert sandboxed_run.usage.input_tokens == 120  # the run's max_tokens budget sees it


def test_missing_token_usage_is_estimated_not_left_at_zero(sandboxed_run, monkeypatch) -> None:
    """A wrapper that reports nothing used to leave the totals at zero, which silently
    disables the max_tokens budget and understates every cost figure in the report."""
    _install_fake_tavily(monkeypatch)
    model = ScriptedChatModel(script=[AIMessage(content="x" * 400)])  # no usage_metadata
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert result.usage.output_tokens == 100  # docs/06 §5's heuristic
    assert sandboxed_run.usage.output_tokens == 100


def test_the_optimized_prompt_set_is_used_when_gepa_wrote_one(
    sandboxed_run, monkeypatch, tmp_path
) -> None:
    """docs/05 §5 freezes search_agent.md, so this path should normally fall back to
    the base prompt — but run_search_agent takes prompt_set, and 1.7 passes it."""
    from prime_search import prompts

    optimized = tmp_path / "optimized"
    optimized.mkdir()
    (optimized / "search_agent.md").write_text(
        "OPTIMIZED SYSTEM\n<!-- task -->\nOPTIMIZED TASK {instruction}", encoding="utf-8"
    )
    (tmp_path / "search_agent.md").write_text(
        "BASE\n<!-- task -->\nBASE TASK {instruction}", encoding="utf-8"
    )
    monkeypatch.setattr(prompts, "_DIR", tmp_path)
    prompts.load.cache_clear()
    _install_fake_tavily(monkeypatch)

    model = ScriptedChatModel(script=[AIMessage(content="Done.")])
    run_search_agent(_task(), ws=sandboxed_run, model=model, prompt_set="optimized")
    prompt_text = "\n".join(str(m.content) for m in model.seen[0])
    assert "OPTIMIZED" in prompt_text
    prompts.load.cache_clear()


def test_a_standalone_run_opens_its_own_trace(sandboxed_run, monkeypatch) -> None:
    """With no parent run current, the node opens one so the tool runs have somewhere
    to hang and a URL exists for the build log."""
    from prime_search.agents import search_agent as module

    opened: list[str] = []

    class FakeHandle:
        url = "https://smith.langchain.com/o/x/trace/y"

    @contextmanager
    def fake_trace_run(name, **kwargs):
        opened.append(name)
        yield FakeHandle()

    _install_fake_tavily(monkeypatch)
    monkeypatch.setattr(module, "trace_run", fake_trace_run)
    monkeypatch.setattr(module, "_tracing_enabled", lambda: True)
    monkeypatch.setattr(module, "get_current_run_tree", lambda: None)

    model = ScriptedChatModel(script=[AIMessage(content="Done.")])
    run_search_agent(_task(), ws=sandboxed_run, model=model)

    assert opened == ["search_agent:b1 (standalone)"]  # distinct, or the trace nests b1 > b1


def test_a_nested_run_takes_its_url_from_the_parent(sandboxed_run, monkeypatch) -> None:
    """Reporting None here meant every task logged None once 1.7 wires the graph."""
    from prime_search.agents import search_agent as module

    class FakeParent:
        def get_url(self) -> str:
            return "https://smith.langchain.com/o/x/trace/parent"

    _install_fake_tavily(monkeypatch)
    monkeypatch.setattr(module, "get_current_run_tree", lambda: FakeParent())
    assert module._run_tree_url(FakeParent()) == "https://smith.langchain.com/o/x/trace/parent"

    model = ScriptedChatModel(script=[AIMessage(content="Done.")])
    result = run_search_agent(_task(), ws=sandboxed_run, model=model)
    assert result.summary == "Done."  # and nothing raised on the nested path

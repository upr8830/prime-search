"""Baseline parity (docs/03 §9).

This file exists to stop the baseline drifting. Every bench number on Day 2 is a delta
against this agent, so a well-meant improvement here quietly shrinks every reported
gain. The assertions are deliberately about *sameness*, not quality.
"""

from __future__ import annotations

import pytest

from prime_search.baseline import STARTER_SYSTEM_PROMPT, _wrap_answer, build_baseline_agent


def test_the_system_prompt_is_the_starters_three_lines() -> None:
    """Reproduced from starter_agent.py, which is never copied into this repo
    (CLAUDE.md). The prompt lives in prompts/baseline.md so a diff of the prompts
    folder shows every prompt the system uses."""
    lines = STARTER_SYSTEM_PROMPT.strip().splitlines()
    assert lines == [
        "You are a concise research assistant.",
        "Use Tavily search when you need current or factual web information.",
        "Answer the user's question directly and include source URLs when available.",
    ]


def test_the_baseline_model_is_the_starter_default(offline_credentials) -> None:
    """docs/01 §3 marks this role "starter default; do not change", and models.py
    refuses to give it a fallback for the same reason."""
    from prime_search.models import FALLBACKS, baseline_model, fallback_model

    assert baseline_model().model_name == "moonshotai/Kimi-K2.6"
    assert "baseline" not in FALLBACKS
    with pytest.raises(ValueError, match="no fallback"):
        fallback_model("baseline")


def test_the_baseline_temperature_is_the_provider_default(offline_credentials) -> None:
    """Everything else in the project is pinned to 0 for reproducibility; the baseline
    is not, because the starter is not."""
    from prime_search.models import baseline_model, root_model

    assert baseline_model().temperature is None
    assert root_model().temperature == 0.0


def test_the_agent_has_exactly_one_tool(offline_credentials) -> None:
    """docs/03 §9: "Nothing else is added, so the comparison is fair." Not our five
    budget-aware tools, not our primitives - one raw TavilySearch."""
    from langchain_tavily import TavilySearch

    agent = build_baseline_agent()
    tools = _tools_of(agent)
    assert len(tools) == 1
    assert isinstance(tools[0], TavilySearch)


def test_the_baseline_does_not_go_through_our_primitives(monkeypatch, offline_credentials) -> None:
    """The one deliberate exception to CLAUDE.md's "every Tavily call goes through
    primitives/". Our layer adds a cache, tier classification and a raw-content
    fallback; routing the control arm through it would make it better than the thing
    it is a control for."""
    from prime_search.primitives import tavily

    called: list[str] = []
    monkeypatch.setattr(tavily, "search", lambda *a, **k: called.append("search"))
    build_baseline_agent()
    assert called == []


def test_urls_in_the_prose_become_citations() -> None:
    """docs/03 §9: "the final text is wrapped into Answer with URL-parsed citations"."""
    answer = _wrap_answer(
        "Coverage is described at https://www.cms.gov/lcd/33822 and in the article "
        "at https://www.cms.gov/article/52464."
    )
    assert [c.url for c in answer.citations] == [
        "https://www.cms.gov/lcd/33822",
        "https://www.cms.gov/article/52464",
    ]
    assert [c.n for c in answer.citations] == [1, 2]


def test_a_baseline_citation_cannot_be_checked_against_a_passage() -> None:
    """Not a defect - a finding. The starter has no evidence store and no documents, so
    `evidence_id` is empty by construction, and that absence is what the docs/04 §7
    citation evaluator measures."""
    answer = _wrap_answer("See https://www.cms.gov/lcd/33822.")
    assert answer.citations[0].evidence_id == ""
    assert answer.citations[0].doc_id == ""
    assert answer.claims == []
    assert answer.effective_dates == []
    assert answer.confidence == 0.0


def test_a_repeated_url_is_cited_once() -> None:
    answer = _wrap_answer("See https://a.gov/x and again https://a.gov/x.")
    assert len(answer.citations) == 1


def test_trailing_punctuation_is_not_part_of_the_url() -> None:
    answer = _wrap_answer("Details at https://www.cms.gov/lcd/33822.")
    assert answer.citations[0].url == "https://www.cms.gov/lcd/33822"


def test_an_answer_with_no_urls_still_wraps() -> None:
    answer = _wrap_answer("Medicare covers CGMs under certain conditions.")
    assert answer.citations == []
    assert answer.body_markdown.startswith("Medicare covers")


def _tools_of(agent) -> list:  # noqa: ANN001
    """Dig the bound tools out of the compiled agent, whichever shape it has."""
    for node in agent.get_graph().nodes.values():
        data = getattr(node, "data", None)
        tools = getattr(data, "tools_by_name", None)
        if tools:
            return list(tools.values())
    raise AssertionError("no tool node found in the compiled baseline agent")


# --- regressions from the first live 1.7 run ----------------------------------------


def test_tool_messages_are_not_part_of_the_answer(sandboxed_run) -> None:
    """A Tavily result is a 4 KB JSON blob. Taking every chunk's text put it into
    body_markdown, printed it as if the model had written it, and made _wrap_answer
    parse ten "citations" out of URLs the model had not yet read."""
    from langchain_core.messages import AIMessageChunk, ToolMessage

    from prime_search.baseline import _on_message_chunk

    parts: list[str] = []
    tool_blob = ToolMessage(
        content='{"results": [{"url": "https://spam.example/x", "content": "..."}]}',
        tool_call_id="c1",
    )
    _on_message_chunk((tool_blob, {}), sandboxed_run, parts, None)
    assert parts == []

    _on_message_chunk(
        (AIMessageChunk(content="The real answer."), {}), sandboxed_run, parts, None
    )
    assert parts == ["The real answer."]


def test_a_failing_token_sink_does_not_end_the_baseline() -> None:
    from prime_search.agents.synthesizer import safe_token_sink

    def explodes(text: str) -> None:
        raise UnicodeEncodeError("charmap", text, 0, 1, "undefined")

    safe_token_sink(explodes)("anything")  # must not raise


def test_a_baseline_run_persists_its_record(sandboxed_run, monkeypatch, tmp_path) -> None:
    """docs/02 §5. The baseline returned a record and wrote nothing, so runs/<run_id>/
    held events but no run.json - and the Day 2 bench compares the two modes row by row
    from exactly these files."""
    import json

    from langchain_core.messages import AIMessageChunk

    from prime_search import baseline as module
    from prime_search.schemas import RunRequest

    class FakeAgent:
        def stream(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            yield "messages", (AIMessageChunk(content="Covered when insulin-treated."), {})

    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: FakeAgent())
    record = module.run_baseline(RunRequest(question="q", mode="baseline"))

    directory = module.events.run_dir(record.run_id)
    stored = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    assert stored["request"]["mode"] == "baseline"
    assert stored["answer"]["body_markdown"] == "Covered when insulin-treated."
    assert stored["status"] == "completed"
    # docs/02 §5 names all three files; a consumer written to the spec reads these.
    request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    assert request["mode"] == "baseline"
    assert (directory / "answer.md").read_text(encoding="utf-8") == "Covered when insulin-treated."


def test_the_baseline_trace_carries_the_source_project_and_cache_flag(sandboxed_run, monkeypatch) -> None:
    from contextlib import contextmanager

    from langchain_core.messages import AIMessageChunk

    from prime_search import baseline as module
    from prime_search.schemas import RunRequest

    seen: dict = {}

    class FakeAgent:
        def stream(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            yield "messages", (AIMessageChunk(content="answer"), {})

    @contextmanager
    def fake_trace(name, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen.update(kwargs)

        class Handle:
            url = "https://smith.langchain.com/x"

        yield Handle()

    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: FakeAgent())
    monkeypatch.setattr(module, "trace_run", fake_trace)
    ws = module.Workspace(objective="q")
    record = module.run_baseline(
        RunRequest(question="q", mode="baseline"),
        source="bench", extra_tags=["bench:dev"], project_name="prime-search-bench", ws=ws,
    )
    assert record.run_id == ws.run_id
    assert "source:bench" in seen["tags"] and "bench:dev" in seen["tags"]
    assert seen["project_name"] == "prime-search-bench"
    assert seen["metadata"]["tavily_cache"] is False


def test_the_baseline_model_reports_streamed_token_usage(offline_credentials, monkeypatch) -> None:
    """A saved baseline run showed input_tokens=0: streamed replies carried no usage."""
    from prime_search import baseline as module

    captured: dict = {}
    real = module.baseline_model

    def recording(**kwargs):  # noqa: ANN003, ANN202
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(module, "baseline_model", recording)
    module.build_baseline_agent()
    assert captured == {"streaming": True, "stream_usage": True}

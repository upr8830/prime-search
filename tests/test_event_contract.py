"""The docs/02 §4 event contract.

`GET /run/{run_id}/events` streams `event: <type>`, `data: <json>`, and the table in §4
is what an SSE client types against. Nothing tested that table until now, which is why
four payloads drifted from it unnoticed through 1.7: `plan` carried a branch *count*,
`evidence` carried round totals, `task.started` was emitted as an aggregate, and
`run.finished` had no `langsmith_run_url`.

These tests read the emitted payloads, not the emitting code, so they keep working when
the emitter moves.
"""

from __future__ import annotations

import json
import time

import pytest
from langchain_core.messages import AIMessage

from prime_search.agents import graph as graph_module
from prime_search.evidence.store import EvidenceStore
from prime_search.schemas import (
    Branch,
    QueryUnderstanding,
    RunRequest,
    SearchPlan,
)

from conftest import ScriptedChatModel

# docs/02 §4's table, as a contract: event type -> keys the payload must carry.
REQUIRED_KEYS = {
    "run.started": {"run_id", "mode", "depth", "question"},
    "understanding": {"normalized_question", "domain", "question_type", "time_sensitivity"},
    "plan": {"understanding", "branches", "stop_criteria", "budget", "code"},
    "task.started": {"task_id", "branch_id", "round", "instruction"},
    "search": {"task_id", "query", "n_results", "cached"},
    "fetch": {"task_id", "doc_id", "url", "title", "tier", "effective_date"},
    "task.done": {"task_id", "result"},
    "token": {"text"},
    "answer": {"summary", "body_markdown", "citations", "effective_dates", "unknowns"},
    "usage": {"searches", "fetches", "deep_reads", "agents", "rounds"},
    "run.finished": {"status", "langsmith_run_url", "usage"},
    "error": {"message", "node", "severity"},
    "verdict": {"round", "sufficient", "coverage", "missing", "new_tasks", "reasoning"},
    "critique": {
        "weak_claims", "missing_interpretations", "source_independence_issues",
        "secondary_when_primary_exists", "outdated_sources", "contradictions",
        "recommended_searches", "completion_probability", "reasoning",
    },
}


def _events(run_dir_path) -> list[dict]:
    path = run_dir_path / "events.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _by_type(records: list[dict], type_: str) -> list[dict]:
    return [record["payload"] for record in records if record["type"] == type_]


def _understanding() -> QueryUnderstanding:
    return QueryUnderstanding(
        normalized_question="q", domain="cgm", question_type="eligibility",
        time_sensitivity="high",
    )


def _state(ws, **overrides):
    state = {
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
        "trace_url": "https://smith.langchain.com/x",
    }
    state.update(overrides)
    return state


@pytest.fixture
def planned(sandboxed_run):
    ws = sandboxed_run
    ws.understanding = _understanding()
    ws.plan = SearchPlan(
        understanding=ws.understanding,
        branches=[
            Branch(branch_id="b1", question="criteria?", rationale="r",
                   source_hint="primary_policy", priority=1),
        ],
        stop_criteria="cited",
        budget=ws.budget,
    )
    return ws


def test_the_plan_event_carries_a_search_plan(sandboxed_run) -> None:
    """docs/02 §4: `plan | SearchPlan | search tree skeleton`. A branch *count* cannot
    build a tree skeleton - the ids and questions have to be in the stream, or the UI
    can only draw the plan by reading the record file."""
    from prime_search.agents.root import plan_run
    from prime_search.events import run_dir

    sandboxed_run.understanding = _understanding()
    cell = """```python
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(branch_id="b1", question="What are the criteria?", rationale="r",
               source_hint="primary_policy", priority=1),
        Branch(branch_id="b2", question="Do they cover this case?", rationale="r",
               source_hint="primary_policy", priority=1),
        Branch(branch_id="b3", question="What is current?", rationale="r",
               source_hint="primary_policy", priority=2),
    ],
    stop_criteria="Each criterion cited.",
    budget=ws.budget,
)
```"""
    plan_run(sandboxed_run, model=ScriptedChatModel(script=[AIMessage(content=cell)]))

    payloads = _by_type(_events(run_dir(sandboxed_run.run_id)), "plan")
    assert len(payloads) == 1, "exactly one plan event per planning pass"
    payload = payloads[0]
    assert REQUIRED_KEYS["plan"] <= set(payload)
    assert [branch["branch_id"] for branch in payload["branches"]] == ["b1", "b2", "b3"]
    assert payload["branches"][0]["question"] == "What are the criteria?"
    # docs/07 §4: the Plan tab shows the root's plan code, which only this event carries.
    assert payload["code"].startswith("ws.plan = SearchPlan(")


def test_dispatch_does_not_emit_plan_or_task_started(planned) -> None:
    """Both names are taken by payloads of a different shape. An aggregate under either
    is unreadable to a client that types the event."""
    from prime_search.events import run_dir

    graph_module._dispatch(_state(planned))
    records = _events(run_dir(planned.run_id))
    assert _by_type(records, "plan") == []
    assert _by_type(records, "task.started") == []


def test_collect_emits_usage_not_a_second_evidence_shape(planned) -> None:
    """docs/02 §4: `evidence | Evidence`. Round totals under that name made the CLI
    disambiguate by sniffing for a key."""
    from prime_search.events import run_dir

    graph_module._collect(_state(planned, task_results=[]))
    records = _events(run_dir(planned.run_id))

    usage = _by_type(records, "usage")
    assert usage and REQUIRED_KEYS["usage"] <= set(usage[-1])
    for payload in _by_type(records, "evidence"):
        assert "evidence_id" in payload, "an `evidence` event must carry an Evidence"


def test_error_events_carry_a_known_severity(sandboxed_run) -> None:
    """docs/02 §4: `error {message, node, severity, task_id?, summary?}`."""
    from prime_search import events
    from prime_search.events import run_dir

    events.emit_error(sandboxed_run.run_id, "RuntimeError: boom", "run_prime")
    events.emit_error(
        sandboxed_run.run_id, "fetch: extract yielded 0 paragraphs", "search_agent:b1",
        severity="warning", task_id="b1-r0", summary="Couldn't read a page from example.org",
    )
    payloads = _by_type(_events(run_dir(sandboxed_run.run_id)), "error")
    assert all(REQUIRED_KEYS["error"] <= set(payload) for payload in payloads)
    assert [payload["severity"] for payload in payloads] == ["error", "warning"]
    assert "task_id" not in payloads[0] and payloads[1]["task_id"] == "b1-r0"
    with pytest.raises(ValueError):
        events.emit_error(sandboxed_run.run_id, "x", "api", severity="fatal")


def test_the_answer_event_carries_the_whole_answer(sandboxed_run) -> None:
    """docs/02 §4: `answer | Answer | final answer panel`. A summary dict left the
    replay without the body, the citations or the dates."""
    from prime_search.agents.synthesizer import synthesize
    from prime_search.events import run_dir

    sandboxed_run.understanding = _understanding()
    synthesize(sandboxed_run, unresolved=["nothing found"])  # no evidence path

    payloads = _by_type(_events(run_dir(sandboxed_run.run_id)), "answer")
    assert payloads and REQUIRED_KEYS["answer"] <= set(payloads[0])


def test_synthesis_emits_token_events(sandboxed_run, monkeypatch) -> None:
    """docs/02 §4: `token | {text} | streaming answer (synthesis only)`. Without these
    `events.jsonl` holds no answer text at all and 2.4 cannot replay a streamed run."""
    from prime_search.agents import synthesizer
    from prime_search.events import run_dir

    sandboxed_run.understanding = _understanding()
    monkeypatch.setattr(
        synthesizer, "build_citations", lambda evidence, documents: _one_citation()
    )
    monkeypatch.setattr(synthesizer, "_render_evidence", lambda ws, citations: "[1] x")
    synthesizer.synthesize(
        sandboxed_run,
        model=ScriptedChatModel(script=[AIMessage(content="## Answer\n\nCovered [1].")]),
    )

    tokens = _by_type(_events(run_dir(sandboxed_run.run_id)), "token")
    assert tokens, "no token events were emitted"
    assert all(REQUIRED_KEYS["token"] <= set(payload) for payload in tokens)
    assert "Covered [1]." in "".join(payload["text"] for payload in tokens)


def test_run_finished_carries_the_trace_url(sandboxed_run, monkeypatch) -> None:
    """docs/02 §4: `run.finished | {status, langsmith_run_url} | footer link`. The URL
    was only in `run.started`, so a client that joined late could not reach the trace."""
    from prime_search.baseline import run_baseline
    from prime_search.events import run_dir

    class FakeHandle:
        url = "https://smith.langchain.com/o/x/trace/y"
        trace_id = "0b9e6a1e-trace"

    from contextlib import contextmanager

    @contextmanager
    def fake_trace(name, **kwargs):
        yield FakeHandle()

    from prime_search import baseline as module

    monkeypatch.setattr(module, "trace_run", fake_trace)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: _FakeAgent())
    record = run_baseline(RunRequest(question="q", mode="baseline"))

    payloads = _by_type(_events(run_dir(record.run_id)), "run.finished")
    assert payloads and REQUIRED_KEYS["run.finished"] <= set(payloads[0])
    assert payloads[0]["langsmith_run_url"] == FakeHandle.url
    # 2.4: feedback targets the trace, so the record keeps its id (docs/05 §4).
    assert record.langsmith_trace_id == FakeHandle.trace_id
    assert payloads[0]["usage"] == record.usage.model_dump(mode="json")  # docs/06 §5


def test_the_baseline_emits_the_six_events_the_ui_needs(sandboxed_run, monkeypatch) -> None:
    """docs/02 §4: "Baseline mode emits `run.started`, `search` (per tool call),
    `token`, `answer`, `usage`, `run.finished` so the two panes share one renderer"."""
    from contextlib import contextmanager

    from prime_search import baseline as module
    from prime_search.events import run_dir

    @contextmanager
    def fake_trace(name, **kwargs):
        class Handle:
            url = "https://smith.langchain.com/x"
            trace_id = "trace-x"

        yield Handle()

    monkeypatch.setattr(module, "trace_run", fake_trace)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: _FakeAgent())
    record = module.run_baseline(RunRequest(question="q", mode="baseline"))

    seen = {r["type"] for r in _events(run_dir(record.run_id))}
    assert {"run.started", "token", "answer", "usage", "run.finished"} <= seen
    # One renderer for both panes: the baseline's run.started lacked `depth` until 2.4.
    started = _by_type(_events(run_dir(record.run_id)), "run.started")
    assert started and REQUIRED_KEYS["run.started"] <= set(started[0])


def test_a_baseline_run_with_tracing_off_completes_without_a_trace(sandboxed_run, monkeypatch) -> None:
    """docs/07 §9: with tracing off the footer shows "tracing off". The real trace_run
    is used, not a fake handle: it must yield a null handle and nothing may assume a URL."""
    from prime_search import baseline as module
    from prime_search import tracing
    from prime_search.events import run_dir

    monkeypatch.setattr(tracing, "_tracing_on", lambda: False)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: _FakeAgent())
    record = module.run_baseline(RunRequest(question="q", mode="baseline"))

    assert record.status == "completed"
    assert record.langsmith_run_url is None and record.langsmith_trace_id is None
    finished = _by_type(_events(run_dir(record.run_id)), "run.finished")
    assert finished and finished[0]["langsmith_run_url"] is None


def test_the_baseline_record_exists_when_run_finished_is_emitted(sandboxed_run, monkeypatch) -> None:
    """A client acts on `run.finished`: the UI opens feedback, and `POST /feedback` 404s
    without a record. The baseline used to write its record after emitting it."""
    from prime_search import baseline as module
    from prime_search import tracing
    from prime_search.events import run_dir

    monkeypatch.setattr(tracing, "_tracing_on", lambda: False)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: _FakeAgent())
    seen: dict = {}

    def on_event(record: dict) -> None:
        if record["type"] == "run.finished":
            path = run_dir(record["run_id"]) / "state.json"
            seen["status"] = json.loads(path.read_text(encoding="utf-8"))["status"] if path.is_file() else None

    module.run_baseline(RunRequest(question="q", mode="baseline"), on_event=on_event)
    assert seen == {"status": "completed"}


def _one_citation():
    from prime_search.schemas import Citation

    return [Citation(n=1, evidence_id="ev1", doc_id="d1", url="https://x", label="L")]


class _FakeAgent:
    def stream(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        from langchain_core.messages import AIMessageChunk

        yield "messages", (AIMessageChunk(content="Covered when insulin-treated."), {})


# --- order and delivery, not just payload keys ---------------------------------------


def test_a_subscriber_receives_the_terminal_events(sandboxed_run, monkeypatch) -> None:
    """docs/06 section 4 has `emit()` push to the in-process subscriber queue, and
    docs/02 section 4 makes `run.finished` the footer link - the point an SSE client
    closes on. Emitting it after `unsubscribe()` delivered it to the JSONL and to nobody
    listening, and the CLI hid that by taking the URL from `run.started` and the answer
    from the returned record. Payload-key tests cannot catch this.
    """
    from contextlib import contextmanager

    from prime_search import baseline as module

    @contextmanager
    def fake_trace(name, **kwargs):
        class Handle:
            url = "https://smith.langchain.com/x"
            trace_id = "trace-x"

        yield Handle()

    monkeypatch.setattr(module, "trace_run", fake_trace)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: _FakeAgent())

    seen: list[str] = []
    module.run_baseline(
        RunRequest(question="q", mode="baseline"),
        on_event=lambda record: seen.append(record["type"]),
    )

    assert "answer" in seen, "a live subscriber never received the answer"
    assert "usage" in seen
    assert seen[-1] == "run.finished", f"run.finished must be last, got {seen}"


def test_the_answer_precedes_run_finished_in_the_log(sandboxed_run, monkeypatch) -> None:
    """A replay that reads `events.jsonl` in order must not see the run end before the
    answer it produced."""
    from contextlib import contextmanager

    from prime_search import baseline as module
    from prime_search.events import run_dir

    @contextmanager
    def fake_trace(name, **kwargs):
        class Handle:
            url = "https://smith.langchain.com/x"
            trace_id = "trace-x"

        yield Handle()

    monkeypatch.setattr(module, "trace_run", fake_trace)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: _FakeAgent())
    record = module.run_baseline(RunRequest(question="q", mode="baseline"))

    order = [r["type"] for r in _events(run_dir(record.run_id))]
    assert order.index("answer") < order.index("run.finished")
    assert order.index("usage") < order.index("run.finished")


def _stub_prime_nodes(monkeypatch, synthesize=None) -> None:  # noqa: ANN001
    from contextlib import contextmanager

    from prime_search.agents import graph as module

    @contextmanager
    def fake_trace(name, **kwargs):
        class Handle:
            url = "https://smith.langchain.com/x"
            trace_id = "trace-x"

            def add_tags(self, *tags):  # noqa: ANN001, ANN201
                return None

        yield Handle()

    monkeypatch.setattr(module, "trace_run", fake_trace)
    monkeypatch.setattr(module, "structured", lambda *a, **k: _FakeCaller(_understanding()))
    monkeypatch.setattr(module, "plan_run", lambda ws, **k: _FakeOutcome(_plan_for(ws)))
    monkeypatch.setattr(module, "run_search_agent", lambda task, **k: _empty_result())
    monkeypatch.setattr(module, "synthesize", synthesize or (lambda ws, **k: _blank_answer()))
    monkeypatch.setattr(module, "run_judge", _sufficient_judge)
    monkeypatch.setattr(module, "run_critic", _passing_critic)


def test_a_prime_subscriber_receives_run_finished(sandboxed_run, monkeypatch) -> None:
    from prime_search.agents import graph as module

    _stub_prime_nodes(monkeypatch)
    seen: list[str] = []
    record = module.run_prime(RunRequest(question="q"), on_event=lambda r: seen.append(r["type"]))
    assert seen and seen[-1] == "run.finished", f"got {seen}"
    # 2.4: feedback targets the trace, so the persisted record keeps its id (docs/05 §4).
    from prime_search.events import run_dir

    assert record.langsmith_trace_id == "trace-x"
    saved = json.loads((run_dir(record.run_id) / "state.json").read_text(encoding="utf-8"))
    assert saved["langsmith_trace_id"] == "trace-x"

    # docs/06 §5: the stream ends with the run's totals, not the last round's.
    records = _events(run_dir(record.run_id))
    usages = [r for r in records if r["type"] == "usage"]
    (finished,) = [r for r in records if r["type"] == "run.finished"]
    assert usages[-1]["payload"] == record.usage.model_dump(mode="json")
    assert finished["payload"]["usage"] == record.usage.model_dump(mode="json")
    assert usages[-1]["seq"] < finished["seq"]
    assert finished["payload"]["status"] == "completed" and finished["payload"]["limits_reached"] == []


def test_run_prime_runs_an_injected_prompt_set(sandboxed_run, monkeypatch) -> None:
    """GEPA passes each candidate's registered set (docs/05 §5)."""
    from prime_search.agents import graph as module

    _stub_prime_nodes(monkeypatch)
    seen: dict = {}

    def plan(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen["prompt_set"] = kwargs.get("prompt_set")
        return _FakeOutcome(_plan_for(ws))

    real_tags = module._trace_tags

    def spy(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        tags, metadata = real_tags(*args, **kwargs)
        seen["tags"] = tags
        return tags, metadata

    monkeypatch.setattr(module, "plan_run", plan)
    monkeypatch.setattr(module, "_trace_tags", spy)
    record = module.run_prime(RunRequest(question="q"), prompt_set="gepa-abc")
    assert seen["prompt_set"] == "gepa-abc"
    assert "prompt_set:gepa-abc" in seen["tags"]
    assert record.request.prompt_set == "base"


def test_run_finished_names_the_limits_a_run_reached(sandboxed_run, monkeypatch) -> None:
    """docs/02 §4: the UI says which limit was reached in plain words (07 §9), so the
    event names it; the status stays `budget_exhausted` for the bench."""
    from prime_search.agents import graph as module
    from prime_search.events import run_dir

    def over_the_token_limit(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
        ws.usage.input_tokens = ws.budget.max_tokens
        return _blank_answer()

    _stub_prime_nodes(monkeypatch, synthesize=over_the_token_limit)
    record = module.run_prime(RunRequest(question="q"))

    (finished,) = _by_type(_events(run_dir(record.run_id)), "run.finished")
    assert record.status == "budget_exhausted"
    assert finished["status"] == "budget_exhausted"
    assert finished["limits_reached"] == ["max_tokens"]


def test_a_failed_prime_run_emits_a_red_error_and_no_limits(sandboxed_run, monkeypatch) -> None:
    """docs/02 §4: `run_prime` and `baseline` failures are severity "error"."""
    from prime_search.agents import graph as module
    from prime_search.events import run_dir
    from prime_search.workspace import Workspace

    def broken(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
        raise RuntimeError("synthesis endpoint down")

    _stub_prime_nodes(monkeypatch, synthesize=broken)
    ws = Workspace(objective="q")
    with pytest.raises(RuntimeError):
        module.run_prime(RunRequest(question="q"), ws=ws)
    records = _events(run_dir(ws.run_id))
    (error,) = _by_type(records, "error")
    assert (error["severity"], error["node"]) == ("error", "run_prime")
    (finished,) = _by_type(records, "run.finished")
    assert finished["status"] == "failed" and finished["limits_reached"] == []


def test_a_failed_baseline_run_emits_a_red_error(sandboxed_run, monkeypatch) -> None:
    from prime_search import baseline as module
    from prime_search import tracing
    from prime_search.events import run_dir
    from prime_search.workspace import Workspace

    class Broken:
        def stream(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("model endpoint down")

    monkeypatch.setattr(tracing, "_tracing_on", lambda: False)
    monkeypatch.setattr(module, "build_baseline_agent", lambda model=None: Broken())
    ws = Workspace(objective="q")
    with pytest.raises(RuntimeError):
        module.run_baseline(RunRequest(question="q", mode="baseline"), ws=ws)
    (error,) = _by_type(_events(run_dir(ws.run_id)), "error")
    assert (error["severity"], error["node"]) == ("error", "baseline")


class _FakeCaller:
    def __init__(self, value) -> None:  # noqa: ANN001
        self.value = value

    def invoke(self, prompt):  # noqa: ANN001, ANN201
        return self.value


class _FakeOutcome:
    def __init__(self, plan) -> None:  # noqa: ANN001
        self.plan = plan
        self.mode = "code"
        self.fallback_tag = None
        self.repairs = 0


def _plan_for(ws):  # noqa: ANN001, ANN202
    ws.plan = SearchPlan(
        understanding=_understanding(),
        branches=[
            Branch(branch_id="b1", question="criteria?", rationale="r",
                   source_hint="primary_policy", priority=1),
        ],
        stop_criteria="cited",
        budget=ws.budget,
    )
    return ws.plan


def _empty_result():
    from prime_search.schemas import TaskResult, Usage

    return TaskResult(
        queries_issued=[], documents_fetched=[], evidence_ids=[], summary="s",
        unresolved=None, usage=Usage(),
    )


def _blank_answer():
    from prime_search.schemas import Answer

    return Answer(
        summary="s", body_markdown="## Answer\n\ns", claims=[], citations=[],
        effective_dates=[], contradictions=[], unknowns=[], confidence=0.1,
    )


def _sufficient_judge(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
    from prime_search.agents.judge import JudgeOutcome
    from prime_search.schemas import Verdict

    verdict = Verdict(
        round=kwargs.get("judged_round", 0), sufficient=True, coverage={}, missing=[],
        reasoning="enough",
    )
    return JudgeOutcome(verdict, "native")


def _passing_critic(ws, **kwargs):  # noqa: ANN001, ANN003, ANN202
    from prime_search.agents.critic import CriticOutcome
    from prime_search.schemas import CriticReport

    return CriticOutcome(CriticReport(completion_probability=0.9, reasoning="ok"), "fenced_json")


def test_the_verdict_event_carries_a_verdict(planned, monkeypatch) -> None:
    """docs/02 §4: `verdict | Verdict | round separator`."""
    monkeypatch.setattr(graph_module, "run_judge", _sufficient_judge)
    graph_module._judge(_state(planned, round=1))

    payloads = _by_type(_events(graph_module.events.run_dir(planned.run_id)), "verdict")
    assert payloads and REQUIRED_KEYS["verdict"] <= set(payloads[0])


def test_the_critique_event_carries_a_critic_report(planned, monkeypatch) -> None:
    """docs/02 §4: `critique | CriticReport | critic panel`."""
    monkeypatch.setattr(graph_module, "run_critic", _passing_critic)
    graph_module._critic(_state(planned, round=1))

    payloads = _by_type(_events(graph_module.events.run_dir(planned.run_id)), "critique")
    assert payloads and REQUIRED_KEYS["critique"] <= set(payloads[0])

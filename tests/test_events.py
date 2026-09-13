"""The local event stream (docs/06 §4, docs/02 §4).

The module's one promise is that it never raises: a full disk or a broken UI
connection must not end a run that is otherwise fine. Most of these test that.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from prime_search import events
from prime_search.schemas import Usage


@pytest.fixture(autouse=True)
def _isolated_runs(tmp_path: Path):
    events.set_runs_root(tmp_path)
    yield
    events.set_runs_root("runs")


def test_emit_writes_jsonl_and_returns_the_record() -> None:
    record = events.emit("r1", "search", {"task_id": "t1", "query": "cgm"})
    assert record["type"] == "search"
    assert record["run_id"] == "r1"
    assert record["ts"]

    lines = (events.run_dir("r1") / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["payload"]["query"] == "cgm"


def test_replay_returns_events_in_order() -> None:
    for index in range(3):
        events.emit("r1", "search", {"n": index})
    assert [event["payload"]["n"] for event in events.replay("r1")] == [0, 1, 2]


def test_replay_of_an_unknown_run_is_empty_not_an_error() -> None:
    assert list(events.replay("never-happened")) == []


def test_replay_skips_a_torn_final_line() -> None:
    """A killed process can leave half a line; the rest of the run is still readable."""
    events.emit("r1", "search", {"n": 1})
    path = events.run_dir("r1") / "events.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"ts": "2026-09-12", "ty')
    assert [event["payload"]["n"] for event in events.replay("r1")] == [1]


def test_subscribers_receive_events_and_can_unsubscribe() -> None:
    seen: list[dict] = []
    unsubscribe = events.subscribe("r1", seen.append)
    events.emit("r1", "search", {"n": 1})
    unsubscribe()
    events.emit("r1", "search", {"n": 2})
    assert [event["payload"]["n"] for event in seen] == [1]


def test_a_subscriber_that_throws_does_not_break_the_run() -> None:
    """Task 2.4 hangs an SSE queue off this; a dropped browser connection must not
    take the run down with it."""
    def explode(_record: dict) -> None:
        raise RuntimeError("the browser went away")

    events.subscribe("r1", explode)
    record = events.emit("r1", "search", {"n": 1})  # must not raise
    assert record["payload"]["n"] == 1
    assert list(events.replay("r1"))  # and the JSONL still got it


def test_subscribers_are_scoped_to_their_run() -> None:
    seen: list[dict] = []
    events.subscribe("r1", seen.append)
    events.emit("r2", "search", {"n": 1})
    assert seen == []


def test_an_unserializable_payload_is_logged_not_raised() -> None:
    """json.dumps used to sit outside the guard, so a circular reference escaped
    emit(), escaped the tool, and escaped the agent."""
    circular: dict = {}
    circular["self"] = circular
    record = events.emit("r1", "error", {"message": "x", "node": "n", "extra": circular})
    assert record["type"] == "error"  # the caller still gets its record back
    assert "unencodable" in record["payload"]
    assert list(events.replay("r1"))  # and the line is still written


def test_a_payload_carrying_run_id_does_not_break_the_info_log() -> None:
    """`emit` passes run_id to the logger itself; a payload with the same key used to
    raise "multiple values for keyword argument" from the logging call."""
    record = events.emit("r1", "run.finished", {"run_id": "r1", "status": "completed"})
    assert record["payload"]["status"] == "completed"


def test_jsonable_handles_models_dates_and_nesting() -> None:
    payload = {"usage": Usage(searches=2), "when": date(2024, 10, 1), "ids": ("a", "b")}
    encoded = events.jsonable(payload)
    assert encoded["usage"]["searches"] == 2
    assert encoded["when"] == "2024-10-01"
    assert encoded["ids"] == ["a", "b"]
    json.dumps(encoded)  # must be serializable without a default= fallback


def test_run_dir_is_created_and_is_where_document_text_goes() -> None:
    """docs/02 §5: `runs/<run_id>/` holds events.jsonl and docs/<doc_id>.txt, and this
    is the one definition of that path — primitives.tavily.fetch is handed it."""
    directory = events.run_dir("r1")
    assert directory.is_dir()
    assert directory.name == "r1"
    assert directory.parent == events.runs_root()


def test_every_emitted_type_is_one_the_ui_knows() -> None:
    """EVENT_TYPES documents docs/02 §4's table. Unknown types are still written
    rather than dropped, but the sub-agent should not be inventing any."""
    for type_name in ("task.started", "search", "fetch", "evidence", "task.done", "error"):
        assert type_name in events.EVENT_TYPES


def test_the_runs_root_is_absolute_so_a_chdir_cannot_orphan_a_run(tmp_path: Path) -> None:
    """Workspace._assert_readable compares document paths against this root; a relative
    one rebinds to the working directory, so a process that changed directory mid-run
    would start refusing documents it had just fetched."""
    events.set_runs_root("runs")
    assert events.runs_root().is_absolute()
    events.set_runs_root(tmp_path)
    assert events.runs_root().is_absolute()

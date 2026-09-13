"""The API's run endpoints and event stream (docs/07 §7, docs/02 §4), offline.

The runners are fakes that emit through `events.emit` from the worker thread, as the real
ones do, and wait on a gate so a test can join a run midway. The fixture releases the gate
and waits for every run before restoring the runs root: a run that outlived its test would
write into the real `runs/`.
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from prime_search import events
from prime_search.api import main, runs, sse
from prime_search.schemas import RunRequest
from prime_search.workspace import Workspace

QUESTION = "Does Medicare cover a CGM for a type 2 diabetic not on insulin?"
EVENTS_PER_RUN = 8  # run.started, six searches, run.finished


@pytest.fixture
def api(tmp_path, offline_credentials, monkeypatch):
    events.set_runs_root(tmp_path / "runs")
    gate = threading.Event()
    calls: list[tuple] = []

    def fake_runner(mode: str):
        def run(request, *, ws, source, **kwargs):  # noqa: ANN001, ANN003, ANN202
            calls.append((mode, request, ws, source))
            events.emit(
                ws.run_id,
                "run.started",
                {"run_id": ws.run_id, "question": request.question, "mode": mode, "depth": request.depth},
            )
            for i in range(3):
                events.emit(ws.run_id, "search", {"task_id": "t", "query": f"q{i}", "n_results": 1, "cached": False})
            gate.wait(10)
            # The rest from concurrent threads, as prime's sub-agents emit (graph.py `Send`).
            workers = [
                threading.Thread(
                    target=events.emit,
                    args=(ws.run_id, "search", {"task_id": f"t{i}", "query": f"q{i}", "n_results": 1, "cached": False}),
                )
                for i in range(3, 6)
            ]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()
            record = ws.to_record(request, status="completed", langsmith_trace_id="trace-1")
            events.write_run_artifacts(record)
            events.emit(ws.run_id, "run.finished", {"status": "completed", "langsmith_run_url": None})
            return record

        return run

    monkeypatch.setattr(runs, "RUNNERS", {"prime": fake_runner("prime"), "baseline": fake_runner("baseline")})
    try:
        with TestClient(main.app) as client:
            state = SimpleNamespace(client=client, gate=gate, calls=calls)
            try:
                yield state
            finally:
                gate.set()
                for entry in client.app.state.registry.entries():
                    if entry.future is not None:
                        entry.future.result(timeout=10)
    finally:
        events.set_runs_root("runs")


def _start(api, **body) -> str:  # noqa: ANN001, ANN003
    response = api.client.post("/run", json={"question": QUESTION, **body})
    assert response.status_code == 200, response.text
    return response.json()["run_id"]


def _wait_done(api, run_id: str) -> None:  # noqa: ANN001
    api.client.app.state.registry.get(run_id).future.result(timeout=10)


def _wait_for_events(run_id: str, count: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if len(list(events.replay(run_id))) >= count:
            return
        time.sleep(0.02)
    raise AssertionError(f"{run_id} never reached {count} events")


def _read_stream(client: TestClient, run_id: str, headers: dict | None = None) -> list[dict]:
    frames: list[dict] = []
    current: dict[str, str] = {}
    with client.stream("GET", f"/run/{run_id}/events", headers=headers or {}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if not line:
                if current:
                    frames.append(current)
                    current = {}
                continue
            if line.startswith(":"):  # keep-alive ping
                continue
            key, _, value = line.partition(":")
            current[key] = value[1:] if value.startswith(" ") else value
    if current:
        frames.append(current)
    return [
        {"event": f.get("event"), "id": f.get("id"), "data": json.loads(f["data"]) if "data" in f else None}
        for f in frames
    ]


# --- POST /run ---------------------------------------------------------------------------------


def test_post_run_starts_a_ui_run_and_returns_its_id(api) -> None:
    api.gate.set()
    run_id = _start(api, mode="prime", depth="fast")
    _wait_done(api, run_id)
    mode, request, ws, source = api.calls[0]
    assert (mode, source, ws.run_id, request.depth) == ("prime", "ui", run_id, "fast")


def test_patient_detail_is_rejected_but_a_quoted_a1c_threshold_is_not(api) -> None:
    response = api.client.post("/run", json={"question": "Patient MRN 12345 DOB 01/01/1900, is a CGM covered?"})
    assert response.status_code == 422
    assert "patient-level detail" in response.json()["detail"]
    assert api.calls == []

    api.gate.set()
    run_id = _start(api, question="Is a CGM covered with an A1c 7.5 or higher?")
    _wait_done(api, run_id)


# --- GET /run/{id}/events ------------------------------------------------------------------------


def test_a_stream_joined_mid_run_sends_every_event_exactly_once(api) -> None:
    run_id = _start(api)
    _wait_for_events(run_id, 4)  # run.started and three searches are on disk before the client joins

    def release_once_subscribed() -> None:
        # The last events are emitted only after the stream subscribed, so they reach it
        # through the live queue (and possibly the replay too), never the replay alone.
        deadline = time.monotonic() + 5
        while run_id not in events._subscribers and time.monotonic() < deadline:
            time.sleep(0.01)
        api.gate.set()

    releaser = threading.Thread(target=release_once_subscribed)
    releaser.start()
    frames = _read_stream(api.client, run_id)
    releaser.join()
    assert [frame["id"] for frame in frames] == [str(i) for i in range(EVENTS_PER_RUN)]
    assert frames[0]["event"] == "run.started" and frames[-1]["event"] == "run.finished"


def test_a_finished_run_replays_and_last_event_id_resumes(api) -> None:
    api.gate.set()
    run_id = _start(api)
    _wait_done(api, run_id)

    assert len(_read_stream(api.client, run_id)) == EVENTS_PER_RUN
    resumed = _read_stream(api.client, run_id, headers={"Last-Event-ID": "3"})
    assert [frame["id"] for frame in resumed] == ["4", "5", "6", "7"]


def test_reconnecting_after_the_end_sends_nothing_rather_than_a_failure(api, monkeypatch) -> None:
    """A browser EventSource reconnects on its own after a close, with the last id it saw.
    It must not be told a completed run was interrupted (task 2.4 review)."""
    monkeypatch.setattr(sse, "POLL_SECONDS", 0.05)
    api.gate.set()
    run_id = _start(api)
    _wait_done(api, run_id)
    for last in (str(EVENTS_PER_RUN - 1), "99"):
        assert _read_stream(api.client, run_id, headers={"Last-Event-ID": last}) == []


def test_a_run_another_process_is_writing_streams_from_its_file(api, monkeypatch) -> None:
    """A CLI run is not in this registry and publishes nothing here: the stream follows
    its file, and a quiet second between events is not an interruption."""
    monkeypatch.setattr(sse, "POLL_SECONDS", 0.05)
    monkeypatch.setattr(sse, "STALE_SECONDS", 5.0)
    run_id = "01cli-run"

    def write(type_: str, payload: dict) -> None:  # the file only, as another process would
        events._append(run_id, {"ts": "t", "run_id": run_id, "type": type_, "seq": None, "payload": payload})

    write("run.started", {"run_id": run_id, "question": "q", "mode": "prime", "depth": "deep"})
    finisher = threading.Timer(0.4, write, args=("run.finished", {"status": "completed", "langsmith_run_url": None}))
    finisher.start()
    frames = _read_stream(api.client, run_id)
    finisher.join()
    assert [frame["event"] for frame in frames] == ["run.started", "run.finished"]
    assert frames[-1]["data"]["status"] == "completed"


def test_an_interrupted_run_ends_with_a_finish_that_is_never_written(api, monkeypatch) -> None:
    monkeypatch.setattr(sse, "POLL_SECONDS", 0.05)
    monkeypatch.setattr(sse, "STALE_SECONDS", 0.0)
    ws = Workspace(objective="an older question")
    events.write_run_artifacts(ws.to_record(RunRequest(question="an older question"), status="running"))
    events.emit(ws.run_id, "run.started", {"run_id": ws.run_id, "question": "q", "mode": "prime", "depth": "deep"})

    frames = _read_stream(api.client, ws.run_id)
    assert [frame["event"] for frame in frames] == ["run.started", "error", "run.finished"]
    assert frames[-1]["data"]["status"] == "failed" and frames[-1]["id"] is None
    assert "usage" in frames[-1]["data"]  # docs/02 §4: run.finished carries usage
    assert [record["type"] for record in events.replay(ws.run_id)] == ["run.started"]

    listing = {row["run_id"]: row for row in api.client.get("/runs").json()}
    assert listing[ws.run_id]["status"] == "interrupted"


def test_a_runner_that_dies_before_emitting_still_finishes_its_stream(api, monkeypatch) -> None:
    def broken(request, **kwargs):  # noqa: ANN001, ANN003, ANN202
        raise RuntimeError("settings unreadable")

    monkeypatch.setitem(runs.RUNNERS, "baseline", broken)
    run_id = _start(api, mode="baseline")
    _wait_done(api, run_id)

    frames = _read_stream(api.client, run_id)
    assert [frame["event"] for frame in frames] == ["error", "run.finished"]
    assert frames[-1]["data"]["status"] == "failed" and "usage" in frames[-1]["data"]
    assert api.client.get(f"/runs/{run_id}").json()["status"] == "failed"


def test_two_concurrent_runs_keep_separate_streams(api) -> None:
    api.gate.set()
    baseline, prime = _start(api, mode="baseline"), _start(api, mode="prime")
    for run_id in (baseline, prime):
        _wait_done(api, run_id)
    for run_id, mode in ((baseline, "baseline"), (prime, "prime")):
        frames = _read_stream(api.client, run_id)
        assert len(frames) == EVENTS_PER_RUN
        assert frames[0]["data"]["run_id"] == run_id and frames[0]["data"]["mode"] == mode


# --- GET /runs, /runs/{id}, /runs/{id}/events ----------------------------------------------------


def test_runs_lists_active_saved_and_interrupted_runs_newest_first(api) -> None:
    old = Workspace(objective="an older question")
    events.write_run_artifacts(old.to_record(RunRequest(question="an older question"), status="running"))
    run_id = _start(api)

    rows = api.client.get("/runs").json()
    by_id = {row["run_id"]: row for row in rows}
    assert rows[0]["run_id"] == run_id
    assert by_id[run_id]["status"] == "running" and by_id[old.run_id]["status"] == "interrupted"

    api.gate.set()
    _wait_done(api, run_id)
    assert {row["run_id"]: row for row in api.client.get("/runs").json()}[run_id]["status"] == "completed"


def test_run_record_while_starting_once_saved_and_unknown(api) -> None:
    run_id = _start(api)
    stub = api.client.get(f"/runs/{run_id}").json()
    assert stub["status"] == "running" and stub["request"]["question"] == QUESTION

    api.gate.set()
    _wait_done(api, run_id)
    saved = api.client.get(f"/runs/{run_id}").json()
    assert saved["status"] == "completed" and saved["langsmith_trace_id"] == "trace-1"
    assert [event["seq"] for event in api.client.get(f"/runs/{run_id}/events").json()] == list(range(EVENTS_PER_RUN))

    for path in ("/runs/not-a-run", "/runs/not-a-run/events", "/run/not-a-run/events", "/runs/bad%20id!"):
        assert api.client.get(path).status_code == 404, path

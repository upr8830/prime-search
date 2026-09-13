"""`POST /feedback` and `POST /ui-event` (docs/06 §3, §8; docs/05 §4), offline.

LangSmith is a recorder patched over `feedback._client`; both JSONL files live under
tmp_path.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from prime_search import events
from prime_search.api import feedback, main
from prime_search.schemas import RunRequest
from prime_search.workspace import Workspace


class RecordingClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def create_feedback(self, **kwargs):  # noqa: ANN003, ANN201
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)


@pytest.fixture
def api(tmp_path, offline_credentials, monkeypatch):
    events.set_runs_root(tmp_path / "runs")
    langsmith = RecordingClient()
    monkeypatch.setattr(feedback, "FEEDBACK_PATH", tmp_path / "data" / "feedback.jsonl")
    monkeypatch.setattr(feedback, "UI_EVENTS_PATH", tmp_path / "data" / "ui-events.jsonl")
    monkeypatch.setattr(feedback, "_client", lambda: langsmith)
    monkeypatch.setattr(feedback, "_tracing_enabled", lambda: True)
    try:
        with TestClient(main.app) as client:
            client.langsmith = langsmith
            yield client
    finally:
        events.set_runs_root("runs")


def _run(trace_id: str | None = "trace-123") -> str:
    ws = Workspace(objective="Is a CGM covered for a type 2 diabetic not on insulin?")
    request = RunRequest(question=ws.objective, mode="prime", question_id="cgm-elig-004")
    events.write_run_artifacts(ws.to_record(request, status="completed", langsmith_trace_id=trace_id))
    return ws.run_id


def _lines(path) -> list[dict]:  # noqa: ANN001
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_feedback_sends_the_three_keys_to_the_trace_and_appends_a_line(api) -> None:
    run_id = _run()
    body = {"run_id": run_id, "thumbs": "down", "comment": "cites a superseded LCD", "claim_ids_flagged": ["c1", "c2"]}
    response = api.post("/feedback", json=body)
    assert response.json() == {"ok": True, "langsmith": True}

    calls = {call["key"]: call for call in api.langsmith.calls}
    assert set(calls) == {"user_thumbs", "user_comment", "user_flagged_claims"}
    assert calls["user_thumbs"]["score"] == 0 and calls["user_thumbs"]["comment"] == "cites a superseded LCD"
    assert calls["user_flagged_claims"]["comment"] == "c1, c2"
    assert {call["run_id"] for call in api.langsmith.calls} == {"trace-123"}

    (line,) = _lines(feedback.FEEDBACK_PATH)
    assert (line["run_id"], line["question_id"], line["mode"], line["thumbs"], line["score"]) == (
        run_id, "cgm-elig-004", "prime", "down", 0,
    )
    assert line["langsmith"] == {"sent": True, "trace_id": "trace-123", "error": None}


def test_a_thumbs_up_without_a_comment_sends_only_the_thumb(api) -> None:
    api.post("/feedback", json={"run_id": _run(), "thumbs": "up"})
    assert [(call["key"], call["score"]) for call in api.langsmith.calls] == [("user_thumbs", 1)]


def test_a_langsmith_failure_still_writes_the_file(api, monkeypatch) -> None:
    monkeypatch.setattr(feedback, "_client", lambda: RecordingClient(error=ConnectionError("offline")))
    response = api.post("/feedback", json={"run_id": _run(), "thumbs": "up"})
    assert response.json() == {"ok": True, "langsmith": False}
    (line,) = _lines(feedback.FEEDBACK_PATH)
    assert "ConnectionError" in line["langsmith"]["error"]


def test_no_trace_id_or_tracing_off_means_file_only(api, monkeypatch) -> None:
    assert api.post("/feedback", json={"run_id": _run(trace_id=None), "thumbs": "up"}).json()["langsmith"] is False
    monkeypatch.setattr(feedback, "_tracing_enabled", lambda: False)
    assert api.post("/feedback", json={"run_id": _run(), "thumbs": "up"}).json()["langsmith"] is False
    assert api.langsmith.calls == []
    assert [line["langsmith"]["error"] for line in _lines(feedback.FEEDBACK_PATH)] == [
        "the run has no LangSmith trace id", "tracing is off",
    ]


def test_unknown_runs_and_patient_detail_are_rejected_before_anything_is_written(api) -> None:
    assert api.post("/feedback", json={"run_id": "not-a-run", "thumbs": "up"}).status_code == 404
    response = api.post("/feedback", json={"run_id": _run(), "thumbs": "down", "comment": "my patient Placeholder, DOB 1/1/1900"})
    assert response.status_code == 422 and "patient-level detail" in response.json()["detail"]
    assert api.post("/feedback", json={"run_id": _run(), "thumbs": "sideways"}).status_code == 422
    assert api.langsmith.calls == [] and _lines(feedback.FEEDBACK_PATH) == []


def test_ui_events_are_appended_and_unknown_types_rejected(api) -> None:
    run_id = _run()
    assert api.post("/ui-event", json={"run_id": run_id, "type": "ui.evidence_opened", "payload": {"evidence_id": "ev1"}}).json() == {
        "ok": True, "langsmith": None,
    }
    assert api.post("/ui-event", json={"type": "ui.compare_toggled", "payload": {}}).status_code == 200
    assert api.post("/ui-event", json={"type": "ui.something_else", "payload": {}}).status_code == 422
    assert [(line["run_id"], line["type"]) for line in _lines(feedback.UI_EVENTS_PATH)] == [
        (run_id, "ui.evidence_opened"), (None, "ui.compare_toggled"),
    ]

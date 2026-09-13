"""`POST /feedback` and `POST /ui-event` (docs/06 §3, §8; docs/05 §4).

Feedback goes two places: LangSmith, on the run's root trace, and a local JSONL that
`eval/searchbench/from_feedback.py` reads later (docs/05 §4). The file is written whether
or not LangSmith accepts it (tracing off, no trace id, network error), and the response
says which happened. UI events only go to their file: docs/06 §8 keeps the endpoint and
the file, with nothing reading them beyond counts.

Both files are local, not committed (`data/.gitignore`): a comment is free text.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prime_search.api.models import FeedbackIn, Ok, UiEventIn
from prime_search.config import get_settings
from prime_search.schemas import RunRecord
from prime_search.tracing import get_logger

__all__ = ["FEEDBACK_PATH", "UI_EVENTS_PATH", "record_feedback", "record_ui_event", "send_feedback"]

_log = get_logger(component="api.feedback")
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
FEEDBACK_PATH = DATA_DIR / "feedback.jsonl"
UI_EVENTS_PATH = DATA_DIR / "ui-events.jsonl"
_lock = threading.Lock()


def _client() -> Any:
    """The LangSmith client; a function so tests can substitute a recorder."""
    from langsmith import Client

    return Client()


def _tracing_enabled() -> bool:
    try:
        return get_settings().tracing_enabled
    except Exception:  # noqa: BLE001 - unreadable settings: no LangSmith, file only
        return False


def send_feedback(record: RunRecord, body: FeedbackIn) -> dict[str, Any]:
    """docs/06 §3's keys on the run's root trace. Never raises.

    `user_thumbs` scores 1 or 0 and carries the comment; `user_comment` is the comment
    alone; `user_flagged_claims` lists the flagged claim ids in its comment. The root
    run's id is its trace id, and passing it as `run_id` makes the call synchronous, so
    the response can say whether LangSmith actually has it.
    """
    trace_id = record.langsmith_trace_id
    if not trace_id:
        return {"sent": False, "trace_id": None, "error": "the run has no LangSmith trace id"}
    if not _tracing_enabled():
        return {"sent": False, "trace_id": trace_id, "error": "tracing is off"}
    try:
        client = _client()
        client.create_feedback(
            run_id=trace_id, key="user_thumbs", score=1 if body.thumbs == "up" else 0, comment=body.comment
        )
        if body.comment:
            client.create_feedback(run_id=trace_id, key="user_comment", comment=body.comment)
        if body.claim_ids_flagged:
            client.create_feedback(
                run_id=trace_id, key="user_flagged_claims", comment=", ".join(body.claim_ids_flagged)
            )
    except Exception as exc:  # noqa: BLE001 - the local file still records it
        error = f"{type(exc).__name__}: {exc}"[:300]
        _log.warning("api.feedback_langsmith_failed", run_id=record.run_id, error=error)
        return {"sent": False, "trace_id": trace_id, "error": error}
    return {"sent": True, "trace_id": trace_id, "error": None}


def record_feedback(record: RunRecord, body: FeedbackIn) -> Ok:
    """Send to LangSmith, then append one line to `data/feedback.jsonl`.

    The line carries the question and mode, so `from_feedback.py` needs no join against
    `runs/`, and records what LangSmith did with it.
    """
    langsmith = send_feedback(record, body)
    _append(
        FEEDBACK_PATH,
        {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": record.run_id,
            "question_id": record.request.question_id,
            "question": record.request.question,
            "mode": record.request.mode,
            "thumbs": body.thumbs,
            "score": 1 if body.thumbs == "up" else 0,
            "comment": body.comment,
            "claim_ids_flagged": body.claim_ids_flagged,
            "langsmith": langsmith,
        },
    )
    _log.info("api.feedback", run_id=record.run_id, thumbs=body.thumbs, langsmith=langsmith["sent"])
    return Ok(ok=True, langsmith=langsmith["sent"])


def record_ui_event(body: UiEventIn) -> Ok:
    _append(
        UI_EVENTS_PATH,
        {"ts": datetime.now(UTC).isoformat(), "run_id": body.run_id, "type": body.type, "payload": body.payload},
    )
    return Ok(ok=True)


def _append(path: Path, line: dict[str, Any]) -> None:
    """One JSON line, serialized under a lock (two UI panes post at once). A failed write
    raises: unlike an event, a dropped feedback line is a lost signal, so the caller
    should see a 500."""
    encoded = json.dumps(line, ensure_ascii=False, default=str)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")

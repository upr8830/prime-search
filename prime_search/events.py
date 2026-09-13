"""Local event stream (docs/06 §4, docs/02 §4).

One `emit()` feeds three consumers: the JSONL under `runs/<run_id>/events.jsonl`
that the UI replays, the in-process subscribers task 2.4 turns into the SSE queue,
and structlog for the four types docs/06 §4 singles out.

Built at 1.6 rather than 2.4 because docs/06 §1 makes this the *only* emit path.
Threading a callback through the sub-agent's tools would have to be unpicked when the
API arrives, and the sub-agent needs `runs/<run_id>/` for document text now
(docs/02 §5).

Nothing here raises: a full disk or a subscriber that throws must not end a run that
is otherwise fine.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from prime_search.tracing import get_logger

# docs/02 §4's table. Not enforced — an unknown type is written rather than dropped,
# so a new event never disappears silently — but it records the contract in one place.
EVENT_TYPES = (
    "run.started",
    "understanding",
    "plan",
    "task.started",
    "search",
    "fetch",
    "evidence",
    "task.done",
    "verdict",
    "critique",
    "token",
    "answer",
    "usage",
    "run.finished",
    "error",
)
# docs/06 §4: these also log at INFO.
_LOG_AT_INFO = {"error", "verdict", "critique", "run.finished"}

_log = get_logger(component="events")
# Guards the JSONL write, `seq`, and publishing together, so subscribers receive a run's
# events in `seq` order. Publishing after releasing it let two concurrent sub-agents
# publish seq 6 before seq 5, and an SSE client that had sent 6 dropped 5 for good
# (task 2.4 review). Reentrant, so a subscriber that emits does not deadlock itself.
_lock = threading.RLock()
_subscribers_lock = threading.Lock()
_subscribers: dict[str, list[Callable[[dict], None]]] = {}
# Next `seq` per events file (keyed by path, so a test's tmp root never inherits a count).
_next_seq: dict[str, int] = {}
_root = Path("runs").resolve()

__all__ = [
    "ERROR_SEVERITIES",
    "EVENT_TYPES",
    "emit",
    "emit_error",
    "jsonable",
    "replay",
    "run_dir",
    "runs_root",
    "set_runs_root",
    "subscribe",
    "write_run_artifacts",
]


def runs_root() -> Path:
    return _root


def set_runs_root(path: str | Path) -> None:
    """Point `runs/` somewhere else. Tests use this; nothing in the app does.

    Resolved immediately rather than kept relative: `Workspace._assert_readable`
    compares a document's path against this root, and a relative one rebinds to
    whatever the working directory happens to be at the time — so a process that
    changed directory mid-run would start refusing documents it had just fetched.
    """
    global _root
    _root = Path(path).resolve()


def run_dir(run_id: str) -> Path:
    """`runs/<run_id>/` (docs/02 §5), created on demand.

    The single definition of a run's directory: `events.jsonl` lands here and
    `primitives.tavily.fetch(run_dir=...)` writes `docs/<doc_id>.txt` beneath it.
    """
    directory = _root / run_id
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # read-only FS: the run still works, it is just not replayable
        _log.warning("events.run_dir_failed", run_id=run_id, error=str(exc))
    return directory


def write_run_artifacts(record: Any) -> None:
    """Write docs/02 §5's run layout: `request.json`, `state.json`, `answer.md`.

    The names are the spec's. An earlier build wrote a single `run.json`, which no
    consumer written to the spec would find — docs/01 §2 and docs/06 §7's
    `prime-search diff` both name `state.json`, and the UI's "open a past run" reads
    `answer.md`.

    Lives here because this module already owns `run_dir()`, and docs/02 §5 is the
    layout `events.jsonl` sits inside. Called at every node boundary (docs/06 §4), so
    a killed run still has a partial record; never raises, for the same reason `emit`
    does not.
    """
    try:
        directory = run_dir(record.run_id)
        (directory / "state.json").write_text(
            record.model_dump_json(indent=2), encoding="utf-8", newline="\n"
        )
        (directory / "request.json").write_text(
            record.request.model_dump_json(indent=2), encoding="utf-8", newline="\n"
        )
        if record.answer is not None:
            (directory / "answer.md").write_text(
                record.answer.body_markdown or record.answer.summary,
                encoding="utf-8",
                newline="\n",
            )
    except (OSError, ValueError, TypeError) as exc:
        _log.warning("events.record_write_failed", run_id=record.run_id, error=str(exc))


def emit(run_id: str, type: str, payload: Any) -> dict[str, Any]:
    """docs/06 §4: append to the JSONL, push to subscribers, log the loud ones.

    Returns the record so a graph node can also put it into `PrimeState.events`
    (docs/03 §1) without building a second copy.
    """
    try:
        encoded = jsonable(payload)
    except (ValueError, TypeError, RecursionError) as exc:
        # A self-referential or otherwise unencodable payload. Losing the detail is
        # acceptable; losing the run is not, and this function is called from inside
        # a tool inside an agent.
        _log.warning("events.payload_unencodable", run_id=run_id, type=type, error=str(exc))
        encoded = {"unencodable": f"{type} payload could not be serialized: {exc}"}
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "type": type,
        "seq": None,  # assigned under the write lock in _append
        "payload": encoded,
    }
    with _lock:
        _append(run_id, record)
        _publish(run_id, record)
    if type in _LOG_AT_INFO:
        _log.info(f"event.{type}", run_id=run_id, **_log_fields(record["payload"]))
    return record


# docs/02 §4. "error": the run failed or cannot go on (red in the UI). "warning": one
# step did not work and the run carried on without it - an unreadable page, a skipped
# critic, a crashed branch (a muted note in the UI).
ERROR_SEVERITIES = ("error", "warning")


def emit_error(
    run_id: str,
    message: str,
    node: str,
    *,
    severity: str = "error",
    task_id: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """docs/02 §4's `error {message, node, severity, task_id?, summary?}`.

    `message` is the engineer's detail; `summary` is the plain sentence a reader of the
    run sees (docs/07 §3). One helper so every emitter carries the same keys.
    """
    if severity not in ERROR_SEVERITIES:
        raise ValueError(f"unknown error severity {severity!r}; expected one of {ERROR_SEVERITIES}")
    payload: dict[str, Any] = {"message": message[:500], "node": node, "severity": severity}
    if task_id is not None:
        payload["task_id"] = task_id
    if summary is not None:
        payload["summary"] = summary
    return emit(run_id, "error", payload)


def subscribe(run_id: str, callback: Callable[[dict], None]) -> Callable[[], None]:
    """Register a listener and return its unsubscribe. Task 2.4's SSE queue is one."""
    with _subscribers_lock:
        _subscribers.setdefault(run_id, []).append(callback)

    def unsubscribe() -> None:
        with _subscribers_lock:
            listeners = _subscribers.get(run_id, [])
            if callback in listeners:
                listeners.remove(callback)
            if not listeners:
                _subscribers.pop(run_id, None)

    return unsubscribe


def replay(run_id: str) -> Iterator[dict[str, Any]]:
    """Past events for a run, in order (docs/02 §4: the UI replays them)."""
    path = _root / run_id / "events.jsonl"
    if not path.is_file():
        return
    # A record written before `seq` existed gets its line position, which is what
    # `_append` would have assigned, so an SSE client dedupes old and new runs alike.
    with path.open(encoding="utf-8") as handle:
        position = -1
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            position += 1
            try:
                record = json.loads(stripped)
            except ValueError:  # a torn last line from a killed process
                continue
            if record.get("seq") is None:
                record["seq"] = position
            yield record


def jsonable(payload: Any) -> Any:
    """Pydantic models to JSON-mode dicts, dates to ISO strings.

    Exposed because the API and the CLI shape their own payloads the same way.
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    if isinstance(payload, dict):
        return {str(key): jsonable(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [jsonable(value) for value in payload]
    if isinstance(payload, (date, datetime)):
        return payload.isoformat()
    return payload


def _append(run_id: str, record: dict[str, Any]) -> None:
    # json.dumps is inside the try on purpose: it was outside, guarded only for
    # OSError, so a circular reference or a RecursionError in a payload escaped emit()
    # -> escaped the tool -> escaped the agent, against this module's one promise.
    try:
        path = run_dir(run_id) / "events.jsonl"
        # Serialized: from 1.7 the graph fans sub-agents out with `Send` and they run
        # concurrently in one superstep, all emitting into this file. Append mode does
        # not make a multi-KB write atomic, and two interleaved writes produced a torn
        # line in a live run - `replay()` drops it, so the UI would have lost an event
        # silently rather than visibly.
        #
        # `seq` is assigned inside the same lock, so file order and seq order agree and
        # an SSE client that replays the file and then drains live events can drop
        # exactly the ones it has already sent (docs/02 §4, task 2.4).
        with _lock:
            record["seq"] = _take_seq(path)
            line = json.dumps(record, ensure_ascii=False, default=str)
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        _log.warning(
            "events.write_failed", run_id=run_id, type=record["type"], error=str(exc)
        )


def _take_seq(path: Path) -> int:
    """The next `seq` for this events file; the caller holds `_lock`. A run reopened by
    a new process continues after the lines already on disk, as `replay()` numbers them."""
    key = str(path)
    if key not in _next_seq:
        try:
            with path.open(encoding="utf-8") as handle:
                _next_seq[key] = sum(1 for line in handle if line.strip())
        except OSError:
            _next_seq[key] = 0
    seq = _next_seq[key]
    _next_seq[key] = seq + 1
    return seq


def _publish(run_id: str, record: dict[str, Any]) -> None:
    with _subscribers_lock:
        listeners = list(_subscribers.get(run_id, ()))
    for callback in listeners:
        try:
            callback(record)
        except Exception as exc:  # a broken UI connection is not a run failure
            _log.warning("events.subscriber_failed", run_id=run_id, error=str(exc))


def _log_fields(payload: Any) -> dict[str, Any]:
    """Scalars only, so a structlog line stays one line.

    `run_id` is dropped because `emit` passes its own — a payload carrying that key
    would otherwise raise "multiple values for keyword argument" from the logging
    call itself. `run.started`'s payload already carries one.
    """
    if not isinstance(payload, dict):
        return {"payload": str(payload)[:200]}
    return {
        key: value
        for key, value in payload.items()
        if key != "run_id" and isinstance(value, (str, int, float, bool, type(None)))
    }

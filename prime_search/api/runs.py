"""Running and finding runs for the API.

`run_prime` and `run_baseline` are synchronous and take minutes, so each `POST /run`
runs on a worker thread. The compare view starts two at once (docs/07 §3). Their events
reach SSE clients through `events.subscribe`, never through the runner's return value.

There is no database (docs/01 §2): a run is whatever is under `runs/<run_id>/`, plus the
runs this process has started and not yet written a record for.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from prime_search import events
from prime_search.agents.graph import run_prime
from prime_search.api.models import RunSummary
from prime_search.baseline import run_baseline
from prime_search.config import get_settings
from prime_search.schemas import RunRecord, RunRequest
from prime_search.tracing import get_logger
from prime_search.workspace import Workspace

__all__ = [
    "RUNNERS",
    "ActiveRun",
    "RunRegistry",
    "list_summaries",
    "load_record",
    "relative_id",
]

_log = get_logger(component="api.runs")

# Two per compare-view question, so four is two questions at once. Runs beyond that
# queue. There is no cancellation: the spec has none, and a LangGraph run cannot be
# stopped from outside short of killing the process (docs/11).
MAX_WORKERS = 4
# Looked up at call time, so tests can swap in fakes.
RUNNERS: dict[str, Callable[..., RunRecord]] = {"prime": run_prime, "baseline": run_baseline}
EXAMPLES = "examples"
# uuid7 run ids, plus whatever older or hand-made runs used. Nothing outside this set
# is ever joined onto a path, so `..` and separators cannot reach the filesystem.
_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class ActiveRun:
    run_id: str
    request: RunRequest
    started_at: datetime
    future: Future | None = None

    @property
    def done(self) -> bool:
        return self.future is not None and self.future.done()


class RunRegistry:
    """The runs this process started. Entries live as long as the process."""

    def __init__(self, max_workers: int = MAX_WORKERS) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="prime-run")
        self._runs: dict[str, ActiveRun] = {}
        self._lock = threading.Lock()

    def start(self, request: RunRequest) -> str:
        """Build the workspace here so the run id exists before the run does, which is
        what lets `POST /run` return at once (the `eval/run_eval.make_target` pattern)."""
        settings = get_settings()
        budget = request.budget_override or settings.budget(request.depth)
        ws = Workspace(objective=request.question, budget=budget)
        entry = ActiveRun(run_id=ws.run_id, request=request, started_at=ws.started_at)
        with self._lock:
            self._runs[ws.run_id] = entry
        entry.future = self._executor.submit(_execute, request, ws)
        return ws.run_id

    def get(self, run_id: str) -> ActiveRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def knows(self, run_id: str) -> bool:
        return self.get(run_id) is not None

    def is_active(self, run_id: str) -> bool:
        entry = self.get(run_id)
        return entry is not None and not entry.done

    def entries(self) -> list[ActiveRun]:
        with self._lock:
            return list(self._runs.values())

    def shutdown(self) -> None:
        # Queued runs are dropped; running ones die with the process and show as
        # `interrupted` next time (docs/11).
        self._executor.shutdown(wait=False, cancel_futures=True)


def _execute(request: RunRequest, ws: Workspace) -> None:
    """Run one request on a worker thread. Never raises.

    Both runners emit `error` and `run.finished` themselves before re-raising. One that
    dies before its `try` (building the agent, reading settings) emits nothing, and an
    SSE client would wait for a `run.finished` that never comes, so this emits both and
    saves a failed record.
    """
    try:
        RUNNERS[request.mode](request, ws=ws, source="ui")
    except Exception as exc:  # noqa: BLE001 - see docstring
        error = f"{type(exc).__name__}: {exc}"[:500]
        _log.warning("api.run_failed", run_id=ws.run_id, error=error)
        if any(record.get("type") == "run.finished" for record in events.replay(ws.run_id)):
            return
        events.emit(ws.run_id, "error", {"message": error, "node": "api"})
        events.emit(ws.run_id, "run.finished", {"status": "failed", "langsmith_run_url": None})
        events.write_run_artifacts(
            ws.to_record(request, status="failed", error=error, finished_at=datetime.now(UTC))
        )


def relative_id(run_id: str) -> str | None:
    """Where a run lives under the runs root: `<id>`, `examples/<id>`, or None.

    Lookups never go through `events.run_dir()`, which creates the directory it names.
    """
    if not _RUN_ID.match(run_id) or run_id == EXAMPLES:
        return None
    root = events.runs_root()
    if (root / run_id).is_dir():
        return run_id
    if (root / EXAMPLES / run_id).is_dir():
        return f"{EXAMPLES}/{run_id}"
    return None


def load_record(run_id: str) -> RunRecord | None:
    relative = relative_id(run_id)
    if relative is None:
        return None
    path = events.runs_root() / relative / "state.json"
    if not path.is_file():
        return None
    try:
        return RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("api.record_unreadable", run_id=run_id, error=str(exc))
        return None


def list_summaries(registry: RunRegistry) -> list[RunSummary]:
    """`GET /runs`: saved records merged with active runs, newest first.

    A record saved as `running` that no worker here is running is `interrupted`.
    Records are read as JSON rather than validated as `RunRecord`, so one run written
    by an older schema does not hide the rest.
    """
    root = events.runs_root()
    found: dict[str, RunSummary] = {}
    paths = [*root.glob("*/state.json"), *(root / EXAMPLES).glob("*/state.json")]
    for path in paths:
        summary = _summary_from_file(path, registry, example=path.parent.parent == root / EXAMPLES)
        if summary is not None:
            found.setdefault(summary.run_id, summary)
    for entry in registry.entries():
        if entry.run_id not in found:
            found[entry.run_id] = RunSummary(
                run_id=entry.run_id,
                question=entry.request.question,
                mode=entry.request.mode,
                depth=entry.request.depth,
                status="failed" if entry.done else "running",
                started_at=entry.started_at,
            )
    return sorted(found.values(), key=lambda summary: summary.started_at, reverse=True)


def _summary_from_file(path: Path, registry: RunRegistry, *, example: bool) -> RunSummary | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        request = data.get("request") or {}
        run_id = data["run_id"]
        status = data.get("status") or "running"
        if status == "running" and not registry.is_active(run_id):
            status = "interrupted"
        return RunSummary(
            run_id=run_id,
            question=request.get("question", ""),
            mode=request.get("mode", "prime"),
            depth=request.get("depth", "deep"),
            status=status,
            started_at=data["started_at"],
            usage=data.get("usage") or {},
            example=example,
        )
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        _log.warning("api.summary_unreadable", path=str(path), error=str(exc))
        return None

"""The HTTP API (docs/01 §2, docs/07 §7).

    uvicorn prime_search.api.main:app --reload --port 8000     # make dev-api

Endpoints and shapes are docs/07 §7; the event stream is docs/02 §4. No database: runs
are read from `runs/` (docs/01 §2).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse

from prime_search import events
from prime_search.api import runs, sse
from prime_search.api.models import Event, RunStarted, RunSummary
from prime_search.config import get_settings
from prime_search.phi import patient_details
from prime_search.schemas import RunRecord, RunRequest
from prime_search.tracing import configure_logging, get_logger

_log = get_logger(component="api")

# The Next.js dev server (docs/07 §1). 2.5 proxies /api through it, but a dev rewrite can
# buffer a streamed response, so the UI may need to reach the SSE endpoint directly.
UI_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    try:
        # langchain-tavily and the LangSmith SDK read credentials from os.environ.
        get_settings().export_sdk_env()
    except Exception as exc:  # noqa: BLE001 - the API still serves past runs without keys
        _log.warning("api.settings_unavailable", error=str(exc))
    app.state.registry = runs.RunRegistry()
    try:
        yield
    finally:
        app.state.registry.shutdown()


app = FastAPI(title="PRIME Search API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=UI_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _registry(request: Request) -> runs.RunRegistry:
    return request.app.state.registry


def reject_patient_details(text: str | None, field: str) -> None:
    """docs/01 §8. A1c values are allowed: coverage questions quote thresholds (docs/11)."""
    found = patient_details(text, include_lab_values=False)
    if found:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The {field} looks like it carries patient-level detail ({', '.join(found)}). "
                "PRIME Search answers questions about coverage policy, not about a patient: "
                "describe the population instead, e.g. 'a type 2 diabetic not on insulin'."
            ),
        )


def _not_found(run_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"no run {run_id!r}")


@app.post("/run", response_model=RunStarted)
def start_run(body: RunRequest, request: Request) -> RunStarted:
    """Start a run on a worker thread and return its id at once (docs/07 §3)."""
    reject_patient_details(body.question, "question")
    run_id = _registry(request).start(body)
    _log.info("api.run_started", run_id=run_id, mode=body.mode, depth=body.depth)
    return RunStarted(run_id=run_id)


@app.get(
    "/run/{run_id}/events",
    response_class=EventSourceResponse,
    responses={200: {"description": "docs/02 §4 event stream", "content": {"text/event-stream": {}}}},
)
async def stream_run(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None),
) -> EventSourceResponse:
    registry = _registry(request)
    relative = runs.relative_id(run_id)
    if relative is None:
        if not registry.knows(run_id):
            raise _not_found(run_id)
        relative = run_id  # started here, nothing emitted yet
    return EventSourceResponse(
        sse.event_stream(run_id, relative, registry, _parse_last_event_id(last_event_id)),
        ping=15,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/runs", response_model=list[RunSummary])
def list_runs(request: Request) -> list[RunSummary]:
    return runs.list_summaries(_registry(request))


@app.get("/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str, request: Request) -> RunRecord:
    record = runs.load_record(run_id)
    if record is not None:
        return record
    entry = _registry(request).get(run_id)
    if entry is None:
        raise _not_found(run_id)
    # Started, but no record written yet (the baseline writes its record at the end).
    return RunRecord(run_id=entry.run_id, request=entry.request, started_at=entry.started_at)


@app.get("/runs/{run_id}/events", response_model=list[Event])
def get_run_events(run_id: str, request: Request) -> list[dict]:
    """The replay a reconnecting UI falls back to (docs/07 §9)."""
    relative = runs.relative_id(run_id)
    if relative is None:
        if _registry(request).knows(run_id):
            return []
        raise _not_found(run_id)
    return list(events.replay(relative))


def _parse_last_event_id(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None

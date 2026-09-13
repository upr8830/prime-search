"""The HTTP API (docs/01 §2, docs/07 §7).

    uvicorn prime_search.api.main:app --reload --port 8000     # make dev-api

Endpoints and shapes are docs/07 §7; the event stream is docs/02 §4. No database: runs
are read from `runs/` (docs/01 §2).
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse

from eval.searchbench.schema import DATASET, load_records
from prime_search import events
from prime_search.api import feedback, runs, sse
from prime_search.api.models import (
    BenchQuestion,
    DocView,
    Event,
    FeedbackIn,
    Ok,
    ParagraphOut,
    RunStarted,
    RunSummary,
    UiEventIn,
)
from prime_search.config import get_settings
from prime_search.phi import patient_details
from prime_search.primitives.within import load_paragraphs
from prime_search.schemas import Document, RunRecord, RunRequest
from prime_search.tracing import configure_logging, get_logger

_log = get_logger(component="api")

# The Next.js dev server (docs/07 §1). 2.5 proxies /api through it, but a dev rewrite can
# buffer a streamed response, so the UI may need to reach the SSE endpoint directly.
UI_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
# Resolved from the repository, not the working directory uvicorn was started in.
REPO_ROOT = Path(__file__).resolve().parents[2]
LATEST_REPORT = REPO_ROOT / "reports" / "latest.json"
BENCH_DATASET = REPO_ROOT / DATASET
MAX_PARAGRAPHS = 200  # docs/07 §9: "document view paginates paragraphs at 200"
_DOC_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


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


# --- runs ----------------------------------------------------------------------------------


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


# --- documents -----------------------------------------------------------------------------


@app.get("/docs/{run_id}/{doc_id}", response_model=DocView)
def get_document(
    run_id: str,
    doc_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(MAX_PARAGRAPHS, ge=1, le=MAX_PARAGRAPHS),
) -> DocView:
    """A fetched document as paragraphs, with the evidence drawn from it (docs/07 §6).

    The document is found only as a key of the run's `documents`; `doc_id` never names a
    file on its own.
    """
    record = runs.load_record(run_id)
    if record is None:
        raise _not_found(run_id)
    document = record.documents.get(doc_id)
    if document is None or not _DOC_ID.match(doc_id):
        raise HTTPException(status_code=404, detail=f"run {run_id!r} has no document {doc_id!r}")
    evidence = [item for item in record.evidence if item.doc_id == doc_id]
    try:
        paragraphs = load_paragraphs(_readable(run_id, document))
        text_error = None
    except (OSError, ValueError) as exc:
        paragraphs, text_error = [], str(exc)
    return DocView(
        document=document,
        paragraphs=[ParagraphOut(**asdict(paragraph)) for paragraph in paragraphs[offset : offset + limit]],
        evidence=evidence,
        offset=offset,
        limit=limit,
        total=len(paragraphs),
        text_error=text_error,
    )


def _readable(run_id: str, document: Document) -> Document:
    """The document with a `text_path` this API may read.

    The run's own `docs/<doc_id>.txt` comes first: `text_path` is absolute, so a run
    copied from another machine (the committed `runs/examples/`) points at a path that
    does not exist here. Otherwise the recorded path is used only if it is under the runs
    root, so a hand-edited record cannot make the API read an arbitrary file.
    """
    if not document.is_fetched:
        return document  # load_text raises the snippet-only explanation
    relative = runs.relative_id(run_id)
    root = events.runs_root()
    local = root / relative / "docs" / f"{document.doc_id}.txt" if relative else None
    if local is not None and local.is_file():
        return document.model_copy(update={"text_path": str(local)})
    recorded = Path(document.text_path).resolve() if document.text_path else None
    if recorded is not None and recorded.is_relative_to(root) and recorded.is_file():
        return document
    raise ValueError(f"{document.doc_id}: its text is not stored with this run")


# --- bench ---------------------------------------------------------------------------------


@app.get("/bench/questions", response_model=list[BenchQuestion])
def bench_questions(split: Literal["train", "dev", "holdout"] | None = None) -> list[BenchQuestion]:
    """SearchBench questions for the preset picker (docs/07 §3). The answer key stays out."""
    try:
        records = load_records(BENCH_DATASET)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"SearchBench dataset unreadable: {exc}") from exc
    return [
        BenchQuestion(
            id=record.id,
            question=record.question,
            domain=record.domain,
            tier=record.tier,
            question_type=record.question_type,
            split=record.split,
        )
        for record in records
        if split is None or record.split == split
    ]


@app.get("/bench/summary", response_model=dict[str, Any])
def bench_summary() -> dict[str, Any]:
    """`reports/latest.json` as `eval.report` wrote it (docs/05 §3), or `{missing: true}`."""
    try:
        return json.loads(LATEST_REPORT.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"missing": True}
    except (OSError, ValueError) as exc:
        _log.warning("api.report_unreadable", path=str(LATEST_REPORT), error=str(exc))
        return {"missing": True, "error": str(exc)}


# --- feedback ------------------------------------------------------------------------------


@app.post("/feedback", response_model=Ok)
def post_feedback(body: FeedbackIn) -> Ok:
    """Thumbs, comment and flagged claims to LangSmith and `data/feedback.jsonl` (docs/05 §4).

    `langsmith` in the response says whether LangSmith has it; the file always does.
    """
    record = runs.load_record(body.run_id)
    if record is None:
        raise _not_found(body.run_id)
    reject_patient_details(body.comment, "comment")
    return feedback.record_feedback(record, body)


@app.post("/ui-event", response_model=Ok)
def post_ui_event(body: UiEventIn) -> Ok:
    """UI interactions to `data/ui-events.jsonl` (docs/06 §8)."""
    return feedback.record_ui_event(body)

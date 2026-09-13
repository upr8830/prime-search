"""Request and response shapes for the HTTP API (docs/07 §7).

API-only. `schemas.py` stays the agent and run-record contract (docs/02); these exist so
FastAPI's OpenAPI schema is fully typed, which is what task 2.5 generates
`ui/src/types.ts` from (docs/07 §8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from prime_search.schemas import Document, Evidence, Usage

__all__ = [
    "BenchQuestion",
    "DocView",
    "Event",
    "Ok",
    "ParagraphOut",
    "RunStarted",
    "RunStatus",
    "RunSummary",
]

# RunRecord's statuses plus `interrupted`: saved as running, but no process is running
# it any more (the API restarted, or the run was killed). Derived, never persisted.
RunStatus = Literal["running", "completed", "budget_exhausted", "failed", "interrupted"]


class RunStarted(BaseModel):
    run_id: str


class RunSummary(BaseModel):
    """One row of `GET /runs` (docs/07 §7), newest first."""

    run_id: str
    question: str
    mode: Literal["baseline", "prime"]
    depth: Literal["fast", "deep"]
    status: RunStatus
    started_at: datetime
    usage: Usage = Field(default_factory=Usage)
    example: bool = False  # committed under runs/examples/ for reviewers without keys


class Event(BaseModel):
    """One line of `runs/<run_id>/events.jsonl` (docs/02 §4, 06 §4)."""

    ts: str
    run_id: str
    type: str
    seq: int
    payload: Any = None


class Ok(BaseModel):
    ok: bool = True
    # Feedback only: whether it also reached LangSmith (None where not applicable).
    langsmith: bool | None = None


class ParagraphOut(BaseModel):
    """A paragraph of a fetched document; `index` is what `?p=<index>` targets (07 §6)."""

    index: int
    text: str
    char_start: int
    char_end: int
    section: str | None = None
    boilerplate: bool = False


class DocView(BaseModel):
    """`GET /docs/{run_id}/{doc_id}` (docs/07 §6–7), one page of paragraphs at a time.

    `text_error` is set, with no paragraphs, when the text cannot be shown (a snippet-only
    document, or text that no longer matches its index); the metadata and evidence still are.
    """

    document: Document
    paragraphs: list[ParagraphOut]
    evidence: list[Evidence]
    offset: int
    limit: int
    total: int
    text_error: str | None = None


class BenchQuestion(BaseModel):
    """A SearchBench question for the preset picker (docs/07 §3). Never the answer key."""

    id: str
    question: str
    domain: str
    tier: int
    question_type: str
    split: str

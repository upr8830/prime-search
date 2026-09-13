"""Request and response shapes for the HTTP API (docs/07 §7).

API-only. `schemas.py` stays the agent and run-record contract (docs/02); these exist so
FastAPI's OpenAPI schema is fully typed, which is what task 2.5 generates
`ui/src/types.ts` from (docs/07 §8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from prime_search.schemas import Usage

__all__ = ["Event", "Ok", "RunStarted", "RunStatus", "RunSummary"]

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

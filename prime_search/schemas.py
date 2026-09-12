"""Pydantic contracts (docs/02 §2). Changing a schema here means updating docs/02
in the same commit.

Task 1.2 defines only the subset `make smoke` needs to exercise the judge's
structured-output path (docs/01 §4, fallback rule 3). Task 1.4 completes the file.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Usage(BaseModel):
    searches: int = 0
    fetches: int = 0
    deep_reads: int = 0
    agents: int = 0
    rounds: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_seconds: float = 0


class TaskResult(BaseModel):
    queries_issued: list[str]
    documents_fetched: list[str]  # doc_ids
    evidence_ids: list[str]
    summary: str  # 2-3 sentences for the tree view
    unresolved: str | None  # what the agent could not find
    usage: Usage


class SearchTask(BaseModel):
    task_id: str
    branch_id: str
    round: int  # 0 = initial plan, 1.. = judge/critic re-search
    instruction: str  # for the sub-agent
    queries_hint: list[str] = []
    include_domains: list[str] = []
    time_range: str | None = None  # "year" | "month" | None
    status: Literal["pending", "running", "done", "failed"] = "pending"
    result: TaskResult | None = None


class Verdict(BaseModel):
    """Judge output (docs/02 §2.6). Also the structured-output probe in `make smoke`."""

    round: int
    sufficient: bool
    coverage: dict[str, Literal["resolved", "partial", "unresolved"]]  # branch_id -> status
    missing: list[str]  # what is still needed, in plain language
    new_tasks: list[SearchTask] = []
    reasoning: str

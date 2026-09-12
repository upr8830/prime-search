"""Pydantic contracts (docs/02 §2). Changing a schema here means updating docs/02
in the same commit.

Grown task by task: 1.2 added the judge's `Verdict` for the docs/01 §4 rule-3
probe, 1.3 adds `Document`/`Location` because `fetch` returns a Document. Task 1.4
completes the file.
"""

from __future__ import annotations

from datetime import date, datetime
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


class Document(BaseModel):
    """A fetched or snippet-only source (docs/02 §2.4).

    `doc_id` hashes the *normalized* URL (docs/03 §13) so two agents that reach the
    same page by different links share one document; `url` keeps the URL as
    retrieved, which is what a citation renders.

    `text_path` and `paragraph_count` stay `""`/`0` while the document is
    `snippet_only`: docs/02 makes both required, and a sentinel keeps the contract
    intact without widening the schema.
    """

    doc_id: str  # "doc_" + sha1(normalize_url(url))[:10]
    url: str
    title: str
    source_tier: Literal[
        "primary_policy", "official_secondary", "professional", "trade", "web", "unknown"
    ]
    publisher: str | None = None  # "CMS", "Noridian", "FDA", ...
    doc_type: str | None = None  # "LCD", "Article", "NCD", "Fact sheet", "Label", ...
    document_id_external: str | None = None  # "L33822", "A52464"
    effective_date: date | None = None
    revision_date: date | None = None
    retrieved_at: datetime
    text_path: str = ""  # runs/<run_id>/docs/<doc_id>.txt
    paragraph_count: int = 0
    fetch_method: Literal["extract", "raw_content", "snippet_only"]

    @property
    def is_fetched(self) -> bool:
        """docs/04 §3 rule 1: evidence may only come from a fetched document."""
        return self.fetch_method != "snippet_only"


class Location(BaseModel):
    """Where a passage sits in the persisted document text (docs/02 §2.4).

    `paragraph_index` is 0-based (docs/07 renders `?p=<index>`) and the offsets are
    half-open character offsets into `Document.text_path`, so
    `text[char_start:char_end]` is the paragraph verbatim. docs/04 §3's
    whitespace-normalized substring check depends on that identity holding.
    """

    section: str | None = None
    paragraph_index: int
    char_start: int
    char_end: int

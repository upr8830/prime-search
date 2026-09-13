"""Pydantic contracts (docs/02 §2). Changing a schema here means updating docs/02
in the same commit.

Every model docs/02 §2 declares, in dependency order so the forward references
resolve at class-build time. `Budget` lives in config.py (docs/01 §3) and is
imported rather than redeclared, so the routing defaults have one home.

Nullable fields default to None throughout: docs/02 writes several of them without
a default, but a partially-extracted document or a plan without a scope warning is
the normal case, not a construction error.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from prime_search.config import Budget


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


class Evidence(BaseModel):
    """A verbatim passage that supports, contradicts or contextualizes a claim
    (docs/02 §2.4, rules in docs/04 §3).

    `evidence_text` must be a verbatim substring of the paragraph `location` points
    at — never a paraphrase and never a search snippet. That check is what the
    whole evidence model rests on.
    """

    evidence_id: str
    doc_id: str
    branch_id: str
    claim_text: str  # atomic statement the passage supports
    evidence_text: str  # verbatim passage, <= 600 chars
    location: Location  # section, paragraph index, char offsets
    effective_date: date | None = None  # if the passage or document states one
    relevance: float  # 0-1
    source_quality: float  # derived from tier, see docs/04
    confidence: float  # extractor's confidence that the passage supports the claim
    stance: Literal["supports", "contradicts", "context"]


class Claim(BaseModel):
    """A node in the claim graph (docs/02 §2.5, docs/04 §4).

    `status` is the answer to "may this be stated?": docs/04 §1 makes a coverage
    claim `supported` only when some backing evidence is primary or official.
    """

    claim_id: str
    text: str
    branch_id: str
    supported_by: list[str] = []  # evidence ids
    contradicted_by: list[str] = []
    derived_from: list[str] = []  # claim ids
    status: Literal["supported", "contested", "weak", "unresolved"]
    confidence: float
    governing_date: date | None = None  # effective date of the strongest support


class CriticReport(BaseModel):
    """docs/02 §2.6. The critic emits this as fenced JSON, not a native tool call
    (docs/01 §4), so every field has to survive a round trip through text."""

    weak_claims: list[str] = []  # claim ids
    missing_interpretations: list[str] = []
    source_independence_issues: list[str] = []
    # claim ids resting on tier < primary_policy when a primary document is cited
    # elsewhere in the same answer
    secondary_when_primary_exists: list[str] = []
    outdated_sources: list[str] = []  # doc ids
    contradictions: list[str] = []  # claim ids, or one sentence for a contradiction no claim captures
    recommended_searches: list[SearchTask] = []
    completion_probability: float  # 0-1
    reasoning: str


class QueryUnderstanding(BaseModel):
    """docs/02 §2.2. `scope_warning` is set when the question asks about something
    outside Medicare coverage policy, which the answer must say plainly rather than
    answer anyway."""

    normalized_question: str
    domain: Literal["cgm", "glp1", "other"]
    question_type: Literal[
        "eligibility",
        "coding",
        "coverage_pathway",
        "change_detection",
        "contradiction",
        "out_of_scope",
        "other",
    ]
    entities: list[str] = []  # e.g. ["Medicare", "CGM", "type 2 diabetes"]
    time_sensitivity: Literal["low", "medium", "high"]
    needs_primary_sources: bool = True
    scope_warning: str | None = None


class Branch(BaseModel):
    """One line of enquiry in the plan (docs/02 §2.2). The root writes these as
    Python in a sandboxed cell (docs/03 §3)."""

    branch_id: str  # "b1"
    question: str  # sub-question
    hypothesis: str | None = None  # expected answer to confirm or refute
    rationale: str  # why this branch matters
    source_hint: Literal[
        "primary_policy", "coding_article", "fda_label", "guidance", "news", "any"
    ]
    priority: int  # 1 = highest
    depends_on: list[str] = []  # branch ids


class SearchPlan(BaseModel):
    """docs/02 §2.2. Also the structured-output fallback shape when the root emits
    no parseable code block (docs/03 §3)."""

    understanding: QueryUnderstanding
    branches: list[Branch]
    stop_criteria: str  # what "sufficient" means for this question
    budget: Budget


class Citation(BaseModel):
    """docs/02 §2.7. `label` is built from document metadata with missing pieces
    omitted, never invented (docs/04 §5)."""

    n: int  # [1], [2] ...
    evidence_id: str
    doc_id: str
    url: str
    label: str  # "LCD L33822 §Coverage Indications, rev. 2023-04-16"


class Answer(BaseModel):
    """docs/02 §2.7.

    `effective_dates`, `contradictions` and `unknowns` are separate fields rather
    than prose because they are what distinguishes this from the baseline's
    free-text answer, and the evaluators score them individually (docs/05 §2).
    """

    summary: str  # 2-4 sentence direct answer
    body_markdown: str  # with [n] citations
    claims: list[Claim] = []
    citations: list[Citation] = []
    effective_dates: list[str] = []  # "LCD L33822: revision effective 2023-04-16"
    contradictions: list[str] = []
    unknowns: list[str] = []
    confidence: float
    scope_warning: str | None = None


class RunRequest(BaseModel):
    """docs/02 §2.1. The API body, the CLI's arguments and a bench row all arrive
    as one of these."""

    question: str
    mode: Literal["baseline", "prime"] = "prime"
    depth: Literal["fast", "deep"] = "deep"
    question_id: str | None = None  # SearchBench id, if any
    budget_override: Budget | None = None
    prompt_set: Literal["base", "optimized"] = "base"


class RunRecord(BaseModel):
    """The persisted form of a run (docs/02 §2.1, §5).

    Document *text* is not inline: `Document.text_path` points at
    runs/<run_id>/docs/<doc_id>.txt, which is what keeps a record readable and a
    workspace out of the root's context wholesale (docs/02 §3).
    """

    run_id: str  # uuid7, so run directories sort chronologically
    request: RunRequest
    started_at: datetime
    finished_at: datetime | None = None
    langsmith_run_url: str | None = None
    # The root run's trace id, which `POST /feedback` sends to LangSmith (docs/05 §4).
    # The URL alone is not a reliable source: it has more than one format.
    langsmith_trace_id: str | None = None
    plan: SearchPlan | None = None
    tasks: list[SearchTask] = []
    documents: dict[str, Document] = {}  # doc_id -> Document
    evidence: list[Evidence] = []
    claims: list[Claim] = []
    verdicts: list[Verdict] = []
    critic_reports: list[CriticReport] = []
    answer: Answer | None = None
    usage: Usage = Field(default_factory=Usage)
    status: Literal["running", "completed", "budget_exhausted", "failed"] = "running"
    error: str | None = None

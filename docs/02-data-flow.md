# 02 — Data Flow and Schemas

All schemas are Pydantic v2 models in `prime_search/schemas.py`. They are the contract between graph
nodes, the API, the UI, the evaluators, and the persisted run record. Field names below are
normative.

## 1. End-to-end flow (prime mode)

```
 (1) RunRequest
      │
      ▼
 (2) QueryUnderstanding ──► (3) SearchPlan {branches[]}
                                   │  Send() fan-out, one SearchTask per branch
                                   ▼
 (4) SearchTask ──► search sub-agent ──► search()/fetch()/search_within()/extract()
                                   │
                                   ▼
 (5) Documents + Evidence ──► EvidenceStore ──► (6) ClaimGraph
                                                       │
                                                       ▼
 (7) Verdict (judge) ── insufficient ──► new SearchTasks (round ≤ max_rounds) ──┐
      │ sufficient                                                             │
      ▼                                                                        │
 (8) CriticReport ── recommended_searches & completion_probability < τ ──► SearchTasks
      │ pass                                                                   │
      ▼                                                                        │
 (9) Answer {claims[], citations[], effective_dates[], contradictions[], unknowns[]}
      │
      ▼
 (10) RunRecord persisted; LangSmith trace closed; metrics computed
```

Baseline mode: (1) → single ReAct agent with `TavilySearch` → free-text answer wrapped into an
`Answer` with `claims=[]`, `citations` parsed from URLs in the text (best effort), so both modes fit
the same UI and evaluators.

## 2. Schemas

### 2.1 Run request and record

```python
class RunRequest(BaseModel):
    question: str
    mode: Literal["baseline", "prime"] = "prime"
    depth: Literal["fast", "deep"] = "deep"
    question_id: str | None = None          # SearchBench id, if any
    budget_override: Budget | None = None
    prompt_set: Literal["base", "optimized"] = "base"

class RunRecord(BaseModel):
    run_id: str                             # uuid7
    request: RunRequest
    started_at: datetime
    finished_at: datetime | None
    langsmith_run_url: str | None
    langsmith_trace_id: str | None = None   # root trace id; feedback targets it (05 §4). None with tracing off
    plan: SearchPlan | None
    tasks: list[SearchTask]
    documents: dict[str, Document]          # doc_id -> Document (text stored on disk, not inline)
    evidence: list[Evidence]
    claims: list[Claim]
    verdicts: list[Verdict]
    critic_reports: list[CriticReport]
    answer: Answer | None
    usage: Usage
    status: Literal["running", "completed", "budget_exhausted", "failed"] = "running"
    error: str | None = None
```

Every collection field above (`tasks`, `documents`, `evidence`, `claims`,
`verdicts`, `critic_reports`, and the equivalents on `Claim`, `CriticReport`,
`Answer` and `QueryUnderstanding`) defaults to empty, and `status` starts at
`running`. A record is written once at the start of a run and again at the end
(§5), so it must be constructible before any of those exist; `Workspace.to_record`
supplies the terminal `status`, `finished_at` and `answer` as overrides.

One model in this section lives elsewhere: `Budget` is defined in
`prime_search/config.py` (01 §3), because the routing and budget defaults belong
with the settings that override them. `schemas.py` imports it.

### 2.2 Query understanding and plan

```python
class QueryUnderstanding(BaseModel):
    normalized_question: str
    domain: Literal["cgm", "glp1", "other"]
    question_type: Literal["eligibility", "coding", "coverage_pathway", "change_detection",
                           "contradiction", "out_of_scope", "other"]
    entities: list[str]                     # e.g. ["Medicare", "CGM", "type 2 diabetes", "non-insulin"]
    time_sensitivity: Literal["low", "medium", "high"]
    needs_primary_sources: bool = True
    scope_warning: str | None = None        # set for S6-type questions

class Branch(BaseModel):
    branch_id: str                          # "b1"
    question: str                           # sub-question
    hypothesis: str | None                  # optional expected answer to confirm/refute
    rationale: str                          # why this branch matters
    source_hint: Literal["primary_policy", "coding_article", "fda_label", "guidance", "news", "any"]
    priority: int                           # 1 = highest
    depends_on: list[str] = []              # branch ids

class SearchPlan(BaseModel):
    understanding: QueryUnderstanding
    branches: list[Branch]
    stop_criteria: str                      # what "sufficient" means for this question
    budget: Budget
```

### 2.3 Tasks

```python
class SearchTask(BaseModel):
    task_id: str                            # "{branch_id}-r{round}"; "-{k}" for a second judge task on a branch; "-critic{k}" for a critic task
    branch_id: str
    round: int                              # 0 = initial plan, 1.. = judge/critic re-search
    instruction: str                        # for the sub-agent
    queries_hint: list[str] = []
    include_domains: list[str] = []
    time_range: str | None = None           # "year" | "month" | None
    status: Literal["pending", "running", "done", "failed"] = "pending"
    result: TaskResult | None = None

class TaskResult(BaseModel):
    queries_issued: list[str]
    documents_fetched: list[str]            # doc_ids
    evidence_ids: list[str]
    summary: str                            # 2–3 sentences for the tree view
    unresolved: str | None                  # what the agent could not find
    usage: Usage
```

### 2.4 Documents and evidence

```python
class Document(BaseModel):
    doc_id: str                             # "doc_" + sha1(normalize_url(url))[:10]  (03 §13)
    url: str
    title: str
    source_tier: Literal["primary_policy", "official_secondary", "professional", "trade", "web", "unknown"]
    publisher: str | None = None            # "CMS", "Noridian", "FDA", ...
    doc_type: str | None = None             # "LCD", "Article", "NCD", "Fact sheet", "Label", "Press release", ...
    document_id_external: str | None = None # "L33822", "A52464"
    effective_date: date | None = None
    revision_date: date | None = None
    retrieved_at: datetime
    text_path: str = ""                     # runs/<run_id>/docs/<doc_id>.txt; "" while snippet_only
    paragraph_count: int = 0                # 0 while snippet_only
    fetch_method: Literal["extract", "raw_content", "snippet_only"]
```

A document created by `search` is `snippet_only` and has no text on disk, so
`text_path` and `paragraph_count` carry `""`/`0` until it is fetched. Use
`Document.is_fetched` (`fetch_method != "snippet_only"`) rather than testing those
sentinels; evidence may only be drawn from a fetched document (04 §3 rule 1).

Every nullable field above defaults to `None`: a partially-extracted document is
normal (a policy page with no stated effective date is a critic finding, not a
parse failure — 04 §2), so the model must be constructible without them.

```python

class Evidence(BaseModel):
    evidence_id: str
    doc_id: str
    branch_id: str
    claim_text: str                         # atomic statement the passage supports
    evidence_text: str                      # verbatim passage, ≤ 600 chars
    location: Location                      # section, paragraph index, char offsets
    effective_date: date | None             # if the passage or document states one
    relevance: float                        # 0–1
    source_quality: float                   # derived from tier, see 04
    confidence: float                       # extractor's confidence the passage supports the claim
    stance: Literal["supports", "contradicts", "context"]

class Location(BaseModel):
    section: str | None
    paragraph_index: int
    char_start: int
    char_end: int
```

### 2.5 Claims and graph

```python
class Claim(BaseModel):
    claim_id: str
    text: str
    branch_id: str
    supported_by: list[str]                 # evidence ids
    contradicted_by: list[str]
    derived_from: list[str] = []            # claim ids
    status: Literal["supported", "contested", "weak", "unresolved"]
    confidence: float
    governing_date: date | None             # effective date of the strongest supporting evidence
```

### 2.6 Verdicts and critique

```python
class Verdict(BaseModel):
    round: int                              # the search round judged, 0 = the initial one
    sufficient: bool
    coverage: dict[str, Literal["resolved", "partial", "unresolved"]]   # branch_id -> status
    missing: list[str]                      # what is still needed, in plain language
    new_tasks: list[SearchTask] = []        # only tasks the graph dispatches: empty when no round or budget is left
    reasoning: str

class CriticReport(BaseModel):
    weak_claims: list[str]                  # claim ids
    missing_interpretations: list[str]
    source_independence_issues: list[str]
    secondary_when_primary_exists: list[str]   # claim ids relying on tier ≥ official_secondary when a primary doc is cited elsewhere
    outdated_sources: list[str]             # doc ids
    contradictions: list[str]               # claim ids, or one sentence for a contradiction no claim captures
    recommended_searches: list[SearchTask]  # dispatched only on the critic's first run, below 0.7, with budget left
    completion_probability: float           # 0–1
    reasoning: str
```

### 2.7 Answer

```python
class Citation(BaseModel):
    n: int                                  # [1], [2]...
    evidence_id: str
    doc_id: str
    url: str
    label: str                              # "LCD L33822 §Coverage Indications, rev. 2023-04-16"

class Answer(BaseModel):
    summary: str                            # 2–4 sentence direct answer
    body_markdown: str                      # with [n] citations
    claims: list[Claim]
    citations: list[Citation]
    effective_dates: list[str]              # "LCD L33822: revision effective 2023-04-16"
    contradictions: list[str]               # one line each: which sources disagree and which governs (not claim ids)
    unknowns: list[str]
    confidence: float
    scope_warning: str | None
```

### 2.8 Usage

```python
class Usage(BaseModel):
    searches: int = 0
    fetches: int = 0
    deep_reads: int = 0
    agents: int = 0                       # sub-agents dispatched over the whole run (the budget caps each round)
    rounds: int = 0                       # search rounds completed, the initial one included
    input_tokens: int = 0
    output_tokens: int = 0
    wall_seconds: float = 0
```

## 3. Workspace (root RLM variables)

The root operates on a `Workspace` object exposed inside the sandboxed REPL:

```python
ws.objective: str
ws.understanding: QueryUnderstanding | None
ws.plan: SearchPlan | None
ws.tasks: list[SearchTask]
ws.documents: dict[str, Document]
ws.evidence: list[Evidence]
ws.claims: list[Claim]
ws.contradictions: list[str]
ws.unknowns: list[str]
ws.verdicts: list[Verdict]                # one per judge run; persisted as RunRecord.verdicts
ws.critic_reports: list[CriticReport]     # one per critic run; persisted as RunRecord.critic_reports
ws.search_tree: dict                      # branch_id -> {tasks, evidence_ids, status}
ws.budget_remaining() -> Budget
# helpers
ws.evidence_for(branch_id) -> list[Evidence]
ws.docs_by_tier(tier) -> list[Document]
ws.dates() -> list[tuple[doc_id, effective_date]]
```

Documents are never placed in the root's context wholesale. The root inspects `ws.documents[id].title`,
paragraph counts, and calls `search_within` to see specific paragraphs. This is the proposal's
"large results remain in variables" property.

## 4. Event stream (SSE) contract

`GET /run/{run_id}/events` streams `text/event-stream`. Each event: `event: <type>`, `data: <json>`.

| Event | Payload | UI use |
|---|---|---|
| `run.started` | `{run_id, mode, depth, question}` | header |
| `understanding` | `QueryUnderstanding` | chip row |
| `plan` | `SearchPlan` + `code` (the root's plan cell; `null` from a fallback rung) | search tree skeleton, Plan tab (07 §4) |
| `task.started` | `{task_id, branch_id, round, instruction}` | tree node spinner |
| `search` | `{task_id, query, n_results, cached}` | tree node child |
| `fetch` | `{task_id, doc_id, url, title, tier, effective_date}` | tree node child, doc list |
| `evidence` | `Evidence` | evidence panel, count badge |
| `task.done` | `{task_id, result: TaskResult}` | tree node summary |
| `verdict` | `Verdict` | round separator, "insufficient → 3 new tasks" |
| `critique` | `CriticReport` | critic panel |
| `token` | `{text}` | streaming answer (synthesis only) |
| `answer` | `Answer` | final answer panel |
| `usage` | `Usage` | cost/latency footer |
| `run.finished` | `{status, langsmith_run_url, usage}` | footer link, final totals |
| `error` | `{message, node}` | toast |

Baseline mode emits `run.started`, `search` (per tool call), `token`, `answer`, `usage`,
`run.finished` so the two panes share one renderer.

Events are also appended to `runs/<run_id>/events.jsonl` with timestamps; the UI replays them when
re-opening a past run. Each line is `{ts, run_id, type, seq, payload}`, where `seq` counts from 0 per run and
is assigned under the same lock as the write, so file order and `seq` order agree. The SSE stream sends it as
`id: <seq>`, and a client reconnecting with `Last-Event-ID` resumes after that event. Lines written before
`seq` existed get their line position on replay.

## 5. Persisted run layout

```
runs/<run_id>/
  request.json
  state.json          RunRecord (without document text)
  events.jsonl
  docs/<doc_id>.txt   fetched document text
  answer.md
  metrics.json        bench scores: {experiment_name, experiment_url, question_id, split, scores, composite, evaluated_at, evaluator_git_sha}
```

## 6. Evaluation data flow

```
data/searchbench/searchbench_v0.jsonl
   │  eval/searchbench/sync.py
   ▼
LangSmith dataset "searchbench-v0" (splits: train/dev/holdout)
   │  eval/run_eval.py  → langsmith.evaluate(target=run_prime|run_baseline, evaluators=[...])
   ▼
LangSmith experiment (one per mode × prompt_set × split)  +  reports/bench/<experiment>.json
   │  eval/report.py
   ▼
reports/final-report.md   (baseline vs prime vs prime+gepa table, per-tier breakdown, examples)
```

GEPA reads the same dataset (train split), calls the graph through `eval/gepa/adapter.py`, receives
score + textual feedback per example from the evaluators, and writes candidate prompts to
`prompts/optimized/`.

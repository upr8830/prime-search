# 03 — Agent Architecture

Native LangGraph implementation of the PRIME Search pattern. No dependency on Prime Agent. The
"recursive language model" idea is implemented as: a root node that acts by writing Python against a
workspace, and sub-agents that are independent LangGraph subgraphs with their own context, fanned
out with `Send`.

## 1. Graph

```
START
  │
  ▼
understand ──► plan ──► dispatch ──(Send × N)──► search_agent ──► collect
                                                                    │
                                                                    ▼
                                                                  judge ──insufficient (round<max)──► dispatch
                                                                    │ sufficient | round==max
                                                                    ▼
                                                                  critic ──needs_more (once)──► dispatch
                                                                    │ pass
                                                                    ▼
                                                               synthesize ──► END
```

State (`PrimeState`, a `TypedDict` with reducers):

```python
class PrimeState(TypedDict):
    run_id: str
    request: RunRequest
    ws: Workspace                         # single object; nodes mutate and return it
    pending_tasks: list[SearchTask]       # consumed by dispatch
    task_results: Annotated[list[TaskResult], operator.add]
    round: int
    critic_rounds: int
    deadline: float
    events: Annotated[list[dict], operator.add]
```

`dispatch` returns `[Send("search_agent", {"task": t, "run_id": ..., "budget": slice}) for t in pending]`.
`collect` merges `task_results` into `ws` and clears `pending_tasks`.

Budget enforcement: `dispatch` truncates `pending_tasks` to what the remaining budget allows
(`max_agents`, `max_searches` divided across tasks). Every node checks `time.time() < deadline`;
if not, it returns a state that routes straight to `synthesize`.

## 2. Node: `understand`

Model: judge model (Kimi-K2.6), structured output `QueryUnderstanding`, temperature 0.

Prompt `prompts/understand.md` — classifies domain, question type, entities, time sensitivity, and
sets `scope_warning` when the question is outside CMS/CGM/GLP-1 (S6). Includes a short glossary
(NCD/LCD/article/Part B/Part D) so the classifier uses the right vocabulary.

Baseline has no equivalent; this node's output is the first thing the UI shows.

## 3. Node: `plan` (root RLM, planning phase)

Model: root model (Nemotron 3 Super). Output: a fenced Python block that constructs `ws.plan`.

The root is given:

- the objective and `QueryUnderstanding`;
- the workspace API (as a docstring);
- a compact "search strategy card" for the domain (the seed of what the roadmap calls procedural
  memory), e.g. for CGM: *"Coverage criteria live in the DME MAC LCD (L33822); codes and frequency
  live in the companion article (A52464); the April 2023 revision changed the insulin requirement;
  always confirm the current revision date."*
- the planning contract: 3–7 branches; each has a sub-question, optional hypothesis, source hint,
  priority; a `stop_criteria` string; and a rule that change-detection questions must include a
  branch with `time_range="year"`.

Code-as-action: the model responds with

```python
ws.plan = SearchPlan(
    understanding=ws.understanding,
    branches=[
        Branch(branch_id="b1", question="What are the current LCD coverage criteria for therapeutic CGM?",
               hypothesis="Insulin use OR problematic hypoglycemia after the 2023 revision",
               rationale="...", source_hint="primary_policy", priority=1),
        ...
    ],
    stop_criteria="Each criterion cited to LCD text with revision date; documentation requirements cited; codes cited to article.",
    budget=ws.budget,
)
```

The harness extracts the block, executes it in the sandbox, validates `ws.plan`, and on failure asks
once for a corrected block. If the model does not return a block at all, the harness falls back to
`with_structured_output(SearchPlan)` on the judge model — the run continues and the deviation is
logged as an event and a LangSmith tag `fallback:plan_structured`.

Why code-as-action for the root: it works with reasoning models regardless of native tool-calling
support on the endpoint (see 01 §4), it makes the plan an executable object rather than prose, and it
is the same mechanism the root uses to inspect the workspace in later rounds.

## 4. Node: `search_agent` (subgraph, one per task)

Model: sub-agent model (Kimi-K2.6), `create_agent` with tools bound. Independent context per task.

Tools (LangChain `@tool` wrappers over primitives, budget-aware):

| Tool | Behavior |
|---|---|
| `search(query, include_domains=None, time_range=None)` | Tavily search; returns up to 8 `{doc_id, url, title, snippet, tier, date_hint}`. Adds to `ws.documents` as `snippet_only` |
| `fetch(doc_id)` | Tavily extract; upgrades the document to full text; returns title, tier, detected effective/revision dates, section headings, paragraph count |
| `search_within(doc_id, query, k=5)` | BM25 over paragraphs; returns paragraph indices and text |
| `add_evidence(doc_id, paragraph_index, claim_text, stance, confidence)` | Creates an `Evidence` with location, verbatim text, and dates; validates the paragraph actually contains the text |
| `note_unresolved(text)` | Records what could not be found |

Prompt `prompts/search_agent.md` — the agent receives the task instruction, the branch hypothesis,
source hint, and remaining per-task budget. Rules:

1. Prefer primary sources for `primary_policy` and `coding_article` hints; pass `include_domains`.
2. Do not add evidence from a snippet; fetch first. Evidence must be a verbatim passage.
3. One claim per evidence item; atomic; include dates when the passage has them.
4. Look for the revision/effective date of every policy document and add it as `context` evidence.
5. If two fetched documents disagree, add both with the appropriate `stance`.
6. Finish with a 2–3 sentence summary and any unresolved items.
7. Stop when the branch's hypothesis is confirmed or refuted with primary evidence, or when the
   budget is exhausted.

Output: `TaskResult`. The subgraph never returns raw documents to the root; only ids.

## 5. Node: `collect`

Deterministic. Merges results into `ws`, builds/updates `ClaimGraph` (see 04), computes claim
status from stances and source quality, detects contradictions (same branch, opposite stance,
both confidence ≥ 0.6), increments `round`, emits events.

## 6. Node: `judge`

Model: judge model, structured output `Verdict`, temperature 0.

Input: `stop_criteria`, per-branch summary of claims with statuses and governing dates, unresolved
notes, remaining budget. Prompt `prompts/judge.md` asks for per-branch coverage status and, if
insufficient, concrete new `SearchTask`s (with `queries_hint` and `include_domains`) — at most 3 per
round. It must not create tasks for branches already `resolved`. The judge cannot exceed
`max_rounds`; the graph ignores `new_tasks` when `round == max_rounds`.

The judge is the cheap, frequent check ("is there enough?"). The critic is the expensive, single
check ("is it right?").

## 7. Node: `critic`

Model: root/critic model (Nemotron 3 Super). Output: fenced JSON parsed into `CriticReport`;
fallback to structured output on the judge model.

Input: the question, all claims with their supporting/contradicting evidence (evidence text, tier,
dates), the search trajectory (queries issued per branch), and the stop criteria.

Prompt `prompts/critic.md` — the proposal's seven questions, adapted to the domain:

- Which claims rest on a single source, or only on tier ≥ `official_secondary` when a primary
  document was fetched in the run?
- Is any policy claim missing its governing date? Is any cited revision superseded by a later one
  found in the run?
- Are there interpretations the plan missed (e.g., Part B vs Part D, LCD vs article, label
  indication vs coverage)?
- Are there contradictions the claim graph did not flag?
- What single search would most likely change the answer?
- `completion_probability` in [0, 1].

Routing: if `completion_probability < 0.7` and `critic_rounds == 0` and budget allows, dispatch
`recommended_searches` (max 3) and return to `judge` after collection. Otherwise proceed. The critic
runs at most twice.

## 8. Node: `synthesize`

Model: root model, streaming tokens, then a structured pass on the judge model to produce `Answer`
fields (claims, citations, dates, contradictions, unknowns) from the streamed body plus the claim
graph — or a single structured call if streaming structured output proves unreliable.

Prompt `prompts/synthesize.md` — rules:

- Every factual sentence carries a `[n]` citation resolving to an `Evidence`. No evidence, no claim;
  say "not found" instead.
- Sections, in order: **Answer** (2–4 sentences), **Criteria / Details** (bullets, each cited),
  **Codes and documentation** (if applicable), **Effective dates relied on**, **Contradictions and
  caveats**, **Unknowns / not verified**, **Sources** (numbered, with tier and date).
- When claims conflict, present both and state which governs and why (later effective date, primary
  over secondary).
- Carry `scope_warning` from understanding into the answer verbatim.
- Never adjudicate an individual patient; if the question implies one, answer at the policy level and
  say so.

Citations are validated post-hoc: every `[n]` must map to an evidence id; unmapped citations are
removed and logged (this feeds the citation-correctness evaluator).

## 9. Baseline agent

`prime_search/baseline.py` — exactly the starter's shape:

```python
agent = create_agent(model=ChatNebius(model="moonshotai/Kimi-K2.6", streaming=True),
                     tools=[TavilySearch()],
                     system_prompt=STARTER_SYSTEM_PROMPT)
```

`STARTER_SYSTEM_PROMPT` is the starter's three-line prompt, copied verbatim. Tool calls are captured
as `search` events; the final text is wrapped into `Answer` with URL-parsed citations. Nothing else
is added, so the comparison is fair.

## 10. Depth modes

| | fast | deep |
|---|---|---|
| plan | ≤ 2 branches | 3–7 branches |
| agents | 1 | ≤ 6 |
| rounds | 1 (no re-search) | ≤ 3 |
| critic | skipped | yes |
| target | ≤ 30 s | ≤ 3 min |

`fast` exists to show that the same graph scales down; it is CLI-only unless time allows.

## 11. Prompts — seed versions

All prompts are Markdown files with `{{placeholders}}` rendered by a tiny formatter (no Jinja). GEPA
optimizes `plan.md`, `judge.md`, and `critic.md` and writes to `prompts/optimized/`. `prompt_set`
in `RunRequest` selects the folder. Seed prompts should be written plainly and completely — GEPA
improves them from evaluator feedback, so a clear, honest seed matters more than a clever one.

Seed content checklist:

- `understand.md`: role, glossary, output schema, three worked examples (eligibility, change
  detection, out of scope).
- `plan.md`: role, workspace API docstring, strategy card per domain, planning contract, one full
  example plan (CGM eligibility), the fenced-Python output rule.
- `search_agent.md`: rules in §4, the tool descriptions, an example of a good `add_evidence` call,
  and an explicit "snippets are not evidence" line.
- `judge.md`: rubric for resolved/partial/unresolved; when to stop; the no-duplicate-task rule.
- `critic.md`: the question list in §7; the JSON schema; the instruction to be adversarial.
- `synthesize.md`: section order, citation rule, contradiction rule, patient-level rule.

## 12. Sandbox for code-as-action

`workspace.py` implements `Workspace.exec(code: str) -> ExecResult`:

- `exec` with a restricted globals dict: `ws`, the schema classes, `date`, `datetime`, and nothing
  else. Builtins reduced to a safe subset (no `open`, `__import__`, `eval`, `exec`).
- Per-cell timeout via `signal.alarm` (Unix) or a thread with join timeout.
- Stdout captured and returned to the root as the cell output (≤ 4k chars, truncated with a note).
- Any exception is returned as text; the root gets one repair turn.

The root uses this in `plan` (write the plan) and optionally in `critic`-triggered re-planning
(inspect `ws.evidence_for("b3")`, look at `ws.dates()`), which is where the RLM property — operating
over stored information rather than re-reading it through context — becomes visible in traces.

## 13. Error and edge handling

- Sub-agent exceeds its tool-call cap (default 8): tool wrapper raises `BudgetExceeded`; the agent's
  final message is requested with "summarize what you have"; `TaskResult.unresolved` is set.
- Duplicate documents across agents: `doc_id` is a hash of the normalized URL; `fetch` is idempotent
  and cached within the run.
- Empty plan (model failure twice): a default two-branch plan is used (primary policy + recent
  changes) and tagged `fallback:default_plan`.
- No evidence at all: synthesis returns an answer consisting of the scope warning/unknowns only;
  the UI shows it plainly rather than an error.

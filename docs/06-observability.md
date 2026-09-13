# 06 — Observability and Debuggability

Two layers: LangSmith for traces, experiments and feedback; a local event stream for the UI, the
build log, and offline analysis. Both are populated by the same `events.emit()` calls.

## 1. LangSmith trace structure

One root run per request, named `prime_search` or `baseline_search`. Child runs mirror the graph:

```
prime_search  [run_name]
├── understand            (llm)
├── plan                  (chain)  ── root_llm (llm) ── sandbox_exec (tool)
├── dispatch              (chain)
├── search_agent:b1       (chain)  ── search (tool) ── fetch (tool) ── search_within (tool) ── add_evidence (tool)
├── search_agent:b2       (chain)
├── collect               (chain)
├── judge                 (llm)
├── dispatch (round 1)    (chain)
├── ...
├── critic                (llm)
└── synthesize            (llm + parser)
```

Tavily calls are wrapped as tool runs with inputs (query, filters) and outputs (result count, doc
ids, cached flag) — not full content, to keep traces readable. The `fetch` run attaches document
metadata (title, tier, dates, paragraph count).

## 2. Tags and metadata

Set on the root run via `tracing_v2_enabled(project_name, tags)` and `config["metadata"]` exactly
as the starter does, so the two modes are directly comparable in the LangSmith UI.

Tags: `mode:<baseline|prime>`, `depth:<fast|deep>`, `prompt_set:<base|optimized|gepa>`,
`model:<root>`, `subagent:<model>`, `domain:<cgm|glp1|...>`, `qtype:<...>`, `source:<ui|cli|bench|gepa>`,
`fallback:<...>` when any fallback fires, `bench:<split>` when applicable.

Metadata: `run_id`, `question_id`, `question`, `git_sha`, `budget` (as dict), `models` (as dict),
`tavily_cache`.

## 3. Feedback keys

| Key | Source | Score |
|---|---|---|
| `user_thumbs` | UI | 1 / 0 |
| `user_comment` | UI | none; comment only |
| `user_flagged_claims` | UI (optional) | none; comment lists claim ids |
| evaluator keys from 05 §2 | bench | as defined |

**As built (task 2.4).** `POST /feedback {run_id, thumbs: "up"|"down", comment?, claim_ids_flagged?}` sends
`user_thumbs` (score 1/0, carrying the comment), `user_comment` (only when a comment is given) and
`user_flagged_claims` (comment = the ids, comma-separated) to the run's root trace
(`RunRecord.langsmith_trace_id`, 02 §2.1). It then appends `{ts, run_id, question_id, question, mode, thumbs,
score, comment, claim_ids_flagged, langsmith: {sent, trace_id, error}}` to `data/feedback.jsonl`. LangSmith is
skipped when the run has no trace id or tracing is off, and a LangSmith error never fails the request; the
response `{ok, langsmith}` says whether it was sent. A comment carrying patient-level detail is rejected with
422 (01 §8). `data/feedback.jsonl` and `data/ui-events.jsonl` are local, via `data/.gitignore`.

## 4. Local events and run records

`events.emit(run_id, type, payload)`:

1. appends `{ts, run_id, type, seq, payload}` to `runs/<run_id>/events.jsonl` (`seq` per run, under the write lock; 02 §4);
2. pushes to the in-process SSE queue for that run;
3. for `error`, `verdict`, `critique`, `run.finished`: also logs at INFO via structlog.

`RunRecord` is written at every node boundary (cheap; JSON of a few hundred KB max without document
text), so a crashed run still has a partial record the UI can open.

## 5. Metrics per run

`Usage` is accumulated by the primitives (searches, fetches, deep reads), the dispatcher (agents,
rounds), and the model wrapper (`models.py` reads `usage_metadata` from `AIMessage` when the Nebius
wrapper provides it; otherwise estimates with a tokenizer heuristic and tags the run `tokens:estimated`).

`usage` and `run.finished` events carry the totals; the UI shows them in the footer; the bench
reads them from `RunRecord`.

## 6. Debugging playbook (goes in README)

| Symptom | Where to look |
|---|---|
| Plan missing / default plan used | LangSmith `plan` run: root LLM output; tag `fallback:default_plan`; check `reasoning_content` handling in `models.py` |
| Sub-agent never calls tools | `search_agent:*` run: model output; verify tool binding works for the sub-agent model (`make smoke`) |
| Evidence rejected repeatedly | `add_evidence` tool runs: error text shows the verbatim-mismatch; check paragraph splitting for that document |
| Wrong governing date | `fetch` metadata; `primitives/docmeta.py` patterns; the CMS page may state `Revision Effective Date` under a different label |
| Contradiction missed | `collect` output: claim statuses; check Jaccard threshold merge in `evidence/graph.py` |
| Answer cites `[n]` that maps to nothing | `synthesize` parser log; the post-hoc validator removes and logs unmapped citations — count appears as `citations_dropped` in metrics |
| Budget exhausted early | `dispatch` events: task truncation; `Usage` in state |
| Baseline and prime differ in latency wildly | expected; compare `search_cost` too |

## 7. Comparing runs

- LangSmith: filter by `tags` (`mode:*`, `question_id`) and use the compare view on two root runs.
- Local: `uv run prime-search diff <run_id_a> <run_id_b>` prints plan branches, evidence counts per
  tier, claim statuses, citations, usage side by side. Cheap to build; useful in the build log.

## 8. Human + agent signals (transcript note)

The event stream records UI interactions too: `ui.evidence_opened`, `ui.claim_flagged`,
`ui.compare_toggled`, `ui.rerun`. These are appended to `data/ui-events.jsonl` via `POST /ui-event`.
Not used by any automated loop in this delivery; they exist so the "combine human behavior with agent
traces" story in the technical statement is backed by real data, and so the roadmap's feedback-driven
skill learning has an input. Keep the endpoint and the file; skip any analysis beyond counts. As built (task 2.4): each line is
`{ts, run_id, type, payload}`, `run_id` is optional, and any other `type` is rejected with 422.

# 05 — Evaluation Loop

Self-improvement without measurement is dangerous (proposal §16). This document defines the
benchmark, the evaluators, the human feedback path, and the GEPA optimization loop, in the order
they are built.

## 1. SearchBench

Dataset: `data/searchbench/searchbench_v0.jsonl`. Construction and validation process:
`08-synthetic-data-spec.md`. Schema per record:

```json
{
  "id": "cgm-elig-001",
  "domain": "cgm",                         // cgm | glp1 | cross | out_of_scope
  "tier": 2,                               // 1 easy, 2 medium, 3 hard, 4 adversarial
  "question_type": "eligibility",
  "question": "Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?",
  "split": "train",                        // train | dev | holdout
  "answer_key": {
    "as_of": "2026-09-12",
    "summary": "Yes, if ... (validated text)",
    "required_claims": [
      {"id": "c1", "text": "Coverage requires treatment with insulin OR a history of problematic hypoglycemia", "must": true},
      {"id": "c2", "text": "Problematic hypoglycemia is defined as recurrent level 2 or at least one level 3 event", "must": true},
      {"id": "c3", "text": "The non-insulin pathway was added by the revision effective April 16, 2023", "must": false}
    ],
    "required_evidence": [
      {"id": "e1", "document_id_external": "L33822", "doc_type": "LCD", "key_phrases": ["problematic hypoglycemia", "insulin"], "must": true}
    ],
    "governing_documents": ["L33822"],
    "expected_contradictions": [],
    "expected_scope_warning": null,
    "forbidden_claims": [
      {"id": "f1", "text": "Multiple daily injections are required", "reason": "superseded in 2023"}
    ],
    "sources": ["https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"],
    "validated_by": "ujjwal",
    "validation_notes": ""
  }
}
```

Splits: `train` (~15, GEPA), `dev` (~5, sanity during build), `holdout` (~10, final report). Tier
and domain balanced across splits as far as 30 questions allow. Synced to LangSmith by
`eval/searchbench/sync.py` (idempotent, keyed by `id`).

## 2. Evaluators

All in `eval/evaluators.py`, LangSmith `evaluate()`-compatible (`(run, example) -> {key, score, comment}`).
Deterministic ones first; LLM-judge ones use the evaluator model at temperature 0 with a rubric and
return a `comment` — the comment is what GEPA consumes as textual feedback.

| Key | Type | Definition | Range |
|---|---|---|---|
| `answer_correctness` | LLM-judge | Rubric: each `required_claim` present and correct (must-claims weighted 2×), no `forbidden_claim` asserted, summary consistent with `answer_key.summary`. Comment lists missing/incorrect/forbidden claims by id. | 0–1 |
| `evidence_recall` | deterministic | Fraction of `required_evidence` items matched: same `document_id_external` (or URL domain+doc_type when no id) and ≥ 1 `key_phrase` in `evidence_text`. Must-items weighted 2×. Comment lists unmatched ids. | 0–1 |
| `citation_correctness` | LLM-judge | Sample up to 8 cited sentences; for each, does the cited `evidence_text` support the sentence? Score = supported / sampled. Comment lists failing `[n]`. | 0–1 |
| `citation_completeness` | deterministic | Fraction of sentences in Criteria/Codes sections carrying ≥ 1 citation. | 0–1 |
| `currency` | deterministic + judge | For questions with `governing_documents`: were they cited, and does `Answer.effective_dates` include the governing date? For change-detection: judge whether changes are ordered with dates. | 0–1 |
| `contradiction_handling` | LLM-judge | Only on records with `expected_contradictions`: does the answer surface them and state which governs? | 0–1 |
| `scope_handling` | deterministic | Only on `out_of_scope` records: `Answer.scope_warning` present and no fabricated payer-specific criteria (judge check). | 0–1 |
| `primary_source_ratio` | deterministic | Share of citations with tier ≥ `official_secondary`. | 0–1 |
| `search_cost` | deterministic | `usage.searches + usage.fetches`. | int |
| `latency_s` | deterministic | `usage.wall_seconds`. | float |
| `tokens` | deterministic | input + output. | int |
| `search_efficiency` | derived | `answer_correctness / max(1, searches + fetches)` × 10 | float |

Composite for GEPA (single scalar, but feedback text is the important part):

```
score = 0.40·answer_correctness + 0.20·evidence_recall + 0.20·citation_correctness
      + 0.10·currency + 0.10·contradiction_or_scope_handling (whichever applies, else answer_correctness)
      − 0.002·max(0, searches+fetches − 15)        # mild cost pressure beyond 15 calls
```

Evaluator noise control: LLM-judge evaluators run with a fixed rubric prompt, temperature 0, and the
`must` structure so the judge is mostly checking presence rather than free-form grading. The final
report runs the holdout twice and reports mean ± spread.

## 3. Bench runner

`eval/run_eval.py`:

```
uv run python -m eval.run_eval --mode baseline --split holdout
uv run python -m eval.run_eval --mode prime --split holdout --prompt-set base
uv run python -m eval.run_eval --mode prime --split holdout --prompt-set optimized
uv run python -m eval.report            # merges the latest experiment per config into reports/final-report.md
```

Each invocation creates a LangSmith experiment named `<mode>-<prompt_set>-<split>-<yyyymmdd-hhmm>`
with metadata `{git_sha, models, budget}`. Tavily cache on by default for bench so re-runs are
comparable and cheap; the report states whether cache was used.

`reports/final-report.md` layout: headline table (configs × metrics), per-tier table, per-domain
table, three worked examples (one easy, one contradiction, one out-of-scope) showing baseline vs
prime answers side by side, and a cost/latency section.

## 4. Human feedback loop

The UI's thumbs up/down and comment on any run:

1. `POST /feedback {run_id, thumbs, comment, claim_ids_flagged?}`.
2. API writes `langsmith.Client().create_feedback(run_id=<trace root>, key="user_thumbs",
   score=1|0, comment=...)` and appends to `data/feedback.jsonl`.
3. `eval/searchbench/from_feedback.py` (manual step) lists thumbs-down runs on questions not yet in
   SearchBench and drafts new records (question, run's answer as a starting point for the key) into
   `data/searchbench/candidates.jsonl` for human validation.

This closes the proposal's "production signals → evaluate → refine" loop at demo scale, and it is
the hook for the transcript's point about combining human signals with agent traces. What is
*not* built: automatic ingestion into training or prompt updates. Human validation stays in the loop.

## 5. GEPA prompt optimization

Library: `gepa` (standalone). Targets: `plan.md`, `judge.md`, `critic.md` — the three prompts that
shape *what gets searched* and *when to stop*; `search_agent.md` and `synthesize.md` are frozen to
keep the search space small and the run affordable. Seeds are the base prompts.

Adapter (`eval/gepa/adapter.py`):

- `evaluate(batch, candidate)`: for each SearchBench record in the batch, run the PRIME graph with
  the candidate prompt texts injected (via `prompt_set="gepa"` and an in-memory prompt override),
  compute the composite score and assemble feedback text from the evaluators' comments plus a compact
  trajectory summary (branches planned, tasks per round, judge verdicts, critic findings).
- `make_reflective_dataset(...)`: returns, per prompt component, the inputs it saw, its output, and
  the feedback — so GEPA's reflection step can propose targeted edits ("the plan omitted a
  coding-article branch on 3/5 coding questions").

Run configuration (`eval/gepa/run_gepa.py`):

- Train split (~15), dev split (~5) for Pareto selection. Holdout never touched.
- Budget: `max_metric_calls ≈ 120` (≈ 8 candidate evaluations over the train set). Tavily cache
  on; per-run budget reduced to `max_searches=20, max_agents=4` during optimization to bound cost.
- Reflection model: the critic/root model. Task model: the graph as configured.
- Output: `prompts/optimized/{plan,judge,critic}.md` plus `reports/gepa-run.json` (candidate
  scores, Pareto front, accepted edits).

Report: after optimization, `make bench` with `--prompt-set optimized` on holdout; the final
report shows base vs optimized on holdout with the per-metric deltas and the diff of each prompt.

Guardrails:

- Never optimize on holdout. The runner refuses `--split holdout` for GEPA.
- Accept an optimized prompt only if holdout `answer_correctness` improves and
  `citation_correctness` does not drop by more than 0.03; otherwise ship base prompts and report the
  negative result honestly.
- The optimized prompts are committed as artifacts with the diff visible in the PR.

## 6. What "the loop" looks like in the technical statement

```
question ──► PRIME run ──► LangSmith trace ──► evaluators (SearchBench keys)
    ▲                                              │
    │                                              ▼
    └── GEPA rewrites plan/judge/critic ◄── score + textual feedback
                                     ▲
user thumbs/comments ────────────────┘ (via candidate records, human-validated)
```

The claim to make: the system's advantage is the accumulated search policy — decomposition,
source preference, stop criteria — and that policy is measurable and improvable without touching
the retrieval layer or the model weights.

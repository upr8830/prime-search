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
  "domain": "cgm",                         // cgm | glp1 | cross | other
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

**As built (task 2.3).** `eval/evaluators.py` implements every key above (`score_record`, `composite`,
`feedback_text`, and `EVALUATORS` for LangSmith). Rules the table leaves open:

- A metric that does not apply (no required evidence, expected contradiction, scope warning, governing
  document or citation) returns `score=None` with "not applicable: ..." and is left out of means. A failed
  run (no answer) scores 0 on quality metrics. A judge failure is `None` with `metadata.error`. The judge's
  claim, forbidden-claim and item lists are required fields, and a verdict that covers none of the expected
  claims, forbidden claims, sentences or contradictions is retried once before it counts as a judge failure. A score outside LangSmith's
  +/-99999.9999 range (a prime run's `tokens`) is sent to LangSmith as a string `value`; the local JSON keeps it.
- `evidence_recall` and `currency` resolve a key's document through `data/searchbench/sources/index.json` and
  the key's `sources`: external id (also read from MCD URLs, `lcdid=33822` -> L33822), then normalized URL,
  then host plus a compatible doc type only when the key names no id. Key phrases and dates match after NFKC,
  hyphen and whitespace folding. Index entries resolved by search (`needs_review`) are flagged in the comment
  and never supply a governing date.
- `currency` is the mean of "governing documents cited" and "governing date stated" (in `effective_dates` or
  the answer text), plus, for change detection, the judge's ordering verdict (ordered with dates 1, dated but
  not ordered 0.5, undated 0, no change with a date 1, no change without one 0.5).
- `answer_correctness` = 0.8 x must-weighted claims present + 0.2 x summary consistency (1 / 0.5 / 0); any
  asserted forbidden claim caps it at 0.25. `search_efficiency` is returned with it. The verdict is the
  majority of three independent judge calls (`ANSWER_JUDGE_VOTES`, run concurrently; user decision, docs/11):
  a required claim takes the status more than half the calls gave it, else missing; a forbidden claim is
  asserted only on a majority; the summary takes the median grade (a tie goes to the lower one). A call that
  fails is left out, and all three failing is a judge failure. Metadata sums `judge_tokens` over the calls.
- `citation_correctness` samples 8 evenly spaced cited sentences, skipping "Effective dates relied on"
  (a bibliography, not claims); each passage reaches the judge under a `Document:` line with its source's
  type, id, title, publisher and dates. A citation number with no passage is unsupported without a judge call. The baseline scores 0 on it and on `evidence_recall` by construction: its
  citations are URLs with no stored passage.
- `citation_completeness` reads the whole answer when it has no Criteria / Codes sections (the baseline,
  whatever headings it uses), where a URL, markdown link or footnote marker (`[^1]`, `[^36130e-00^]`) counts
  as a citation.
- `scope_handling` applies when `expected_scope_warning` is set; the warning counts in the field or stated in
  the text. `primary_source_ratio` takes a citation's tier from its document, else from its URL.
- `contradiction_handling` = mean over expected contradictions of 0.5 x surfaced + 0.5 x surfaced with the
  governing source stated. `scope_handling` = 0.5 x scope flagged (field or text) + 0.5 x no fabricated payer
  criteria.
- `composite`: a not-applicable component takes `answer_correctness`; the result is clamped to [0, 1]. A
  judge failure in any component leaves the composite `None` until re-scored.
  Judges use the base prompts `prompts/eval_*.md` on the evaluator model, never an optimized set.

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

**As built (task 2.3), runner.** `eval/run_eval.py --mode --split [--prompt-set --depth --ids --concurrency --no-cache --dry-run --rescore FILE]`. It refuses to run when `sync.check` reports a problem, a selected key is unvalidated, or the LangSmith dataset differs from the jsonl. The experiment prefix is `<mode>-<prompt_set|none>-<split>-<yyyymmdd-hhmm>`, and LangSmith appends a random suffix; metadata adds `tavily_cache` (False for the baseline, uncached by construction), depth, split, dataset sha, evaluator model and a subset flag. Bench runs are traced in project `prime-search-bench` with `source:bench` and `bench:<split>`. Results go to `reports/bench/<experiment>.json` (records trimmed of tasks, verdicts and critic reports) and `runs/<run_id>/metrics.json`; `--rescore` re-scores saved records with the current evaluators, spending judge calls only, and leaves the LangSmith feedback of the original pass as it was.

**As built (task 2.3), report.** `eval/report.py --split holdout|dev [--passes N]` reads only `reports/bench/*.json`, so it costs nothing to regenerate. Holdout goes to `reports/final-report.md` and any other split to `reports/<split>-report.md`. Experiments are grouped by configuration `<mode>-<prompt_set>-<depth>`, keeping the latest N passes of each; with N ≥ 2 a metric shows the mean of the per-pass means ± half their range. Subset (`--ids`) runs are never counted. Not-applicable scores are left out of means, and a metric with no value renders as `—`. A coverage line says whether all 12 keys have at least one value for every configuration, and names the gaps. The report states the Tavily cache per configuration and flags dev as a build-time check, not a result. Sections: configurations (experiment links, git sha, evaluator, dataset sha), coverage, headline, PRD §9 targets on their subsets (tier 4 contradiction handling, change-detection currency, recall, citation correctness, answer-correctness delta over the baseline), per tier, per domain, per question (with trace links), worked examples (lowest-tier, contradiction and out-of-scope records, with excerpts from each config), cost and latency (agent and judge tokens), and evaluator comments. It also writes `reports/latest.json`: `{generated_at, split, passes, sources, configs: [{config, mode, prompt_set, depth, split, experiments: [{name, url, tavily_cache, git_sha, evaluator_model, dataset_sha, started_at, rescored_at, file}], n, metrics: {key: {mean, spread, n}}, composite, per_tier, per_domain, judge_errors, failed_runs, judge_tokens, missing_keys}], prd_targets: [{config, metric, subset, value, n, target, met}]}`. The file reflects the last split reported.

## 4. Human feedback loop

The UI's thumbs up/down and comment on any run:

1. `POST /feedback {run_id, thumbs, comment, claim_ids_flagged?}`.
2. API writes `langsmith.Client().create_feedback(run_id=<trace root>, key="user_thumbs",
   score=1|0, comment=...)` and appends to `data/feedback.jsonl`. As built (task 2.4), it also sends
   `user_comment` and `user_flagged_claims`; the line shape is in 06 §3.
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

**As built (task 3.1).** `eval/gepa/adapter.py` (`PrimeAdapter`) and `eval/gepa/run_gepa.py`.

- **Scope (user decision, docs/11):** `plan.md` and `judge.md` only (the cut list's item 5), with
  `max_metric_calls` 60. `answer_correctness` is the majority of three judge calls (§2 as built).
  `--components` and `--max-metric-calls` restore the full configuration.
- **Candidates:** each is registered as an in-memory prompt set `gepa-<sha>` (`prompts.register_prompt_set`)
  and passed to `run_prime(prompt_set=...)`, so concurrent runs of different candidates never share text.
  The record's `request.prompt_set` stays `base`; the trace carries `prompt_set:gepa-<sha>`. A candidate
  that drops a placeholder of its base prompt scores 0 without running.
- **Rollout:** a deep `run_prime` on one train or dev record, budget capped at `max_searches=20,
  max_agents=4`, Tavily cache on, traced in project `prime-search-gepa` with `source:gepa`. It is scored with
  `score_record` and `composite`; a composite left empty by a judge failure is re-scored once, then counts
  as 0.
- **Feedback:** `feedback_text` plus what the component being optimized did on that run: the plan's
  branches and tasks per round, the judge's verdicts, the critic's reports.
- **Reflection:** the critic model (`critic_model()`), with `prompts/gepa_reflection.md`. That is GEPA's
  `<curr_param>`/`<side_info>` template plus PRIME's context and rules: general rules only, no example
  questions or ids, keep placeholders and the output format.
- **GEPA settings:** `reflection_minibatch_size=3`, Pareto candidate selection, round-robin components,
  `cache_evaluation=True`, `raise_on_exception=False`, checkpoints in `runs/gepa/<timestamp>`
  (`--run-dir` resumes).
- **Guardrails:** `--split` accepts only `train`; dev is the Pareto set, and holdout is refused by both the
  runner and the adapter. `--dry-run` prints the plan and the cost estimate and spends nothing.
- **Output:** `reports/gepa-run.json` holds every candidate's parents, dev scores, discovery point, changed
  components and diff against base, the Pareto front, and every rollout's run id and score. Only when the
  best candidate beats the seed on dev does the runner write `prime_search/prompts/optimized/<component>.md`
  for each changed component; an unchanged component's older file is removed. Acceptance on holdout is
  task 3.2's.

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

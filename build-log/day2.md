# Day 2 — SearchBench, judge and critic, evaluation, API, UI

Session record for Day 2 of the `docs/09` plan. Written by `/session-end 2`.

Day 2 validated SearchBench, closed the judge/critic loop, built the evaluation layer and ran it
on the dev split, then shipped the HTTP API and the side-by-side UI harness. It ended at the
**2.5 `[G]` gate**: a deep preset question streamed in both panes of the browser, and thumbs from
both panes reached LangSmith.

Tasks 2.1–2.5 are complete. Two items are **deferred by user decision** (docs/11): 2.6 (optional)
and docs/09's end-of-day holdout bench, which waits for the judge-variance decision below.
Day 3 opens on the holdout decision, then **3.1**.

## Tasks completed

| Task | Commits | Check |
|---|---|---|
| 2.1 SearchBench validation **[G]** | `f653ebc`, `4ca3450`; judge routing `11b1101` | 30/30 keys validated, `sync --check` clean, LangSmith `searchbench-v0` matches the jsonl |
| 2.2 Judge and critic | `062cacd` `8568af4` `32b6e2e` `e773291` `0190fa6`; fixes `93d3922` `fea5f4a` `fdb13f0` `4bc67e9` `f998e75` `8b96787` `398bb0d` | adv-cgm-001 (gestational diabetes), below |
| 2.3 Evaluators and bench **[G]** | `77355aa` `6dc4aa2` `9121e9a` `5d199a8` `0f365ac`; fixes `c499974` `e3f0e86` `faabb8a` `02be1a2` `6704476`; bench `a6df160`, `c741540` | dev report, all 12 metric keys populated |
| 2.4 API | `5d190cc` `813a197` `a42b25d` `c9dcb8b` `4002fe4` `712d666` `edb5dea` `a9edf0a` `6ddbff9`; fixes `31832bc`; port `342df81` | live curl check, below |
| 2.5 UI **[G]** | backend `387d616` `f90be40` `1307149` `aa6ce14`; UI `ff7e32b` `ebaf427` `df9760c` `316b53a` `0317ee2` `eb0650f` `ed6267d` `fbae0a5` `6df5f15`+`fce9fb8` `a44467b` `fea4106` `93c7a90`; docs `53aa98d`; review fixes `2f8b390` `db3b966`; recording `11734f6` | browser gate run, below |
| Housekeeping | `c2db120` `0ea02c3` `218d02a` `c32ebc3` `57c8507` | `.gitignore`, Day 1 transcript, `.env.example` judge line |
| 2.6 [opt] | not built (deferred) | the UI's depth control already offers fast |

End of day:
- `uv run pytest tests/ -q` → **625 passed, 12 deselected** (the 12 are `live`-marked).
- `uv run ruff check prime_search/ eval/ tests/` → clean.
- In `ui/`: `pnpm test` → **13 passed**; `pnpm exec tsc --noEmit` and `pnpm lint` → clean.

## Gates passed

**2.1 `[G]` — SearchBench validated.** All 30 answer keys reviewed and validated by the user
(`glp1-path-005` corrected; `oos-002` rewritten at policy level; `oos-003` brought in line with
08 §4–5). Synced to LangSmith as `searchbench-v0` (UUIDv5 example ids, refuses unvalidated keys).

**2.3 `[G]` — dev-split report with every metric key populated.** `reports/dev-report.md`:
"All 12 metric keys populated: yes — baseline-none-deep ✓; prime-base-deep ✓", 0 judge errors,
0 failed runs, both configs re-scored with the evaluators at `02be1a2`.

| config | answer correctness | evidence recall | citation correctness | currency | composite | avg tokens |
|---|---|---|---|---|---|---|
| baseline | 0.87 | 0.00 | 0.00 | 0.20 | 0.50 | 8.7k |
| prime base | 0.68 | 0.62 | 0.60 | 0.97 | 0.68 | 442k |

Experiments: [baseline-none-dev-20260913-1649-45ba5ed8](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=2de02a0d-e7b2-4e77-b66e-35b8b334ff02),
[prime-base-dev-20260913-1649-5273555d](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=4b381e35-dfce-4f8e-a65c-e3e69b14e84b).
Dev is n = 5, a build-time check, not a result: the answer-correctness judge moved single rows by
0.3–0.5 on re-scoring (open issue below).

**2.5 `[G]` — side-by-side run in the browser, thumbs in LangSmith.** Driven with Claude in
Chrome on `http://localhost:3000`, recording in [`build-log/day2-ui-gate.gif`](day2-ui-gate.gif).

- Preset `cgm-elig-001`, depth deep: "Is a therapeutic CGM covered under Medicare for a type 2
  diabetic who is not on insulin?"
- Starter `01a09c80-7356-7eca-bc2d-3356055e2ebb`: 1 search, completed in 10 s, 7.3k tokens.
  [Trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a09c80-75e2-7c22-bacf-7d80f56f2fe9/run/01a09c80-75e2-7c22-bacf-7d80f56f2fe9).
  Thumbs up → LangSmith `user_thumbs 1.0`.
- PRIME `01a09c80-7357-79a7-a19b-b3f39d2f2743`: understanding → 5 branches → round 0 judge
  sufficient → critic 45% with a recommended search → critic task `b1-r1-critic1` → round 1 judge
  sufficient, critic 80% → answer. Completed in 179 s; footer 312k tokens matches the record
  (311,644). [Trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a09c80-7375-7723-b1f9-159ea5137dc8/run/01a09c80-7375-7723-b1f9-159ea5137dc8).
  Thumbs down with a comment and flagged claim `c1` → LangSmith `user_thumbs 0.0`,
  `user_comment`, `user_flagged_claims "c1"`; both lines in `data/feedback.jsonl`, the flag in
  `data/ui-events.jsonl`. Its Plan tab shows the root's plan code (2,713 characters).
- **Caveat:** this run's judge rounds used Kimi-K2.6, because `.env` overrode the judge (found and
  removed afterwards; docs/11). The gate checks the UI end to end, which this does not change.
- Replay review of past runs also passed: citation cards opening the document view at the
  highlighted paragraph, Evidence/Claims/Critic/Plan tabs, `/runs`, `/bench`, and an interrupted
  run's banner.

## Checks without a gate

**2.2 — judge round or critic recommendation, and a non-empty Contradictions section.**
adv-cgm-001 (gestational diabetes), run `01a09b5b-7a6b-7603-b110-35762dba7768`: 2 verdicts,
1 critique, 2 contradiction lines in the answer.
[Trace](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a09b5b-7a83-7853-b670-eca3a528a31e/run/01a09b5b-7a83-7853-b670-eca3a528a31e).
Earlier live runs of the same question drove the budget, deep-read and secondary-source decisions.

**2.4 — curl a run, stream it, fetch its record, post feedback (verify in LangSmith).** On
127.0.0.1:8765 (port 8000 is held by Windows HTTP.sys): a baseline and a prime fast run streamed to
`run.finished`; `Last-Event-ID: 3` resumed at id 4; records carried `langsmith_trace_id`; the
document view paged 275 paragraphs; feedback returned `{ok: true, langsmith: true}` and all three
keys appeared on the trace; patient detail got 422; bench endpoints served no answer keys.

## What live runs found that the tests did not

**Evaluators (dev bench):**
- The evaluator model replied natively without `claims`; a defaulted list graded correct answers 0.2. Lists are now required and empty verdicts retried.
- LangSmith rejects scores above ±99,999.9999 and dropped whole ingest batches over prime token counts; such scores now go as a string `value`.
- `citation_correctness` sampled the "Effective dates" bibliography and hid each passage's document from the judge. Both fixed.
- Kimi-K2.6 spent the provider's default 8,192 output tokens reasoning and returned nothing; the evaluator role now asks for 32k.
- DailyMed labels did not match fda.gov label targets; aliased.

**API and UI:**
- A keyless run failed inside `trace_run`, which now yields a null handle.
- `emit` published after releasing its lock, so concurrent sub-agents could deliver seq 6 before 5 and the stream dropped 5 for good.
- EventSource sends a server `error` frame to `onerror` too, so one sub-agent error looked like a dropped stream.
- The baseline emitted `run.finished` before writing its record, so an immediate thumbs click could 404.

**Config:**
- One `PRIME_BUDGET_DEEP__*` key rebuilt the deep budget from base defaults: 150k tokens, 10 reads. Fixed with `DeepBudget` and `FastBudget`.
- The `.env` copy of the example routing block pinned the judge to Kimi.

**Process:** two check chains let failures through, pytest behind `| tail` and `tsc` behind a
pipe. Three commits needed follow-up fixes (`387d616`/`f90be40` → `1307149`, `6df5f15` →
`fce9fb8`). Checks now test each exit code explicitly.

## Decisions made today

Full text, one dated line each, in `docs/11-assumptions-and-approach.md` (70 new lines today).
In short:

- **2.1**
  - 30 keys validated by the user.
  - `glp1-path-005` rewritten from CMS pages.
  - `oos-002` rewritten at policy level; history not rewritten (synthetic record).
  - `oos-003` aligned with 08 §4–5.
  - `domain` values `cgm | glp1 | cross | other`.
  - Sync uses UUIDv5 ids and refuses unvalidated keys.
  - Canonical-URL governing documents resolve deterministically.
- **Models:** judge routed to DeepSeek-V4-Flash; extractor and evaluator stay on Kimi-K2.6. Evaluator output cap 32k.
- **2.2 routing and rounds**
  - `max_agents` is per round.
  - `max_rounds` counts every search round.
  - `collect` pairs results by task id.
  - A failed judge records insufficient and proceeds.
  - The judge runs at fast depth but adds no tasks; the critic is skipped at fast.
  - No round with under 30 s left.
  - Judge tokens are charged.
  - Every router sends an expired deadline to synthesis.
- **2.2 critic and answer**
  - The critic ladder is fenced JSON → repair → structured → skipped.
  - Critic tasks are named `-critic{k}`, with at most 2 critic runs.
  - Critic findings feed synthesis.
  - `Answer.contradictions` holds readable lines.
- **2.2 budgets and planning**
  - Deep budget is 400k tokens and 30 deep reads.
  - Over budget, the judge and critic review once and start no search.
  - Every deep coverage question gets a secondary-source branch.
- **2.3 scoring rules**
  - "Not applicable", "failed run" and "judge failure" stay distinct.
  - Documents resolve via the sources index and key URLs.
  - The baseline is scored with the same evaluators (0 by construction where it has no passages).
  - Formulas authored for answer correctness, contradiction handling, scope handling and composite.
- **2.3 runner and report**
  - The runner refuses unsynced or unvalidated data.
  - Bench JSON is committed with trimmed records.
  - The report is built from committed bench files.
  - The baseline streams usage (`stream_usage`).
- **2.4 API contract**
  - `RunRecord.langsmith_trace_id`.
  - Per-run event `seq`, which the SSE stream sends as `id:`.
  - The null trace handle when tracing is off.
  - The shared patient-detail guard allows A1c values.
- **2.4 API runtime**
  - A 4-worker pool, no cancellation.
  - `interrupted` is a derived status.
  - The document view pages at 200 and reads the run's own text.
  - Feedback `thumbs` is up/down, mapping to three LangSmith keys.
  - Feedback files stay local.
  - CORS allows the UI dev origin.
  - The API port is `PRIME_API_PORT`, default 8765.
- **2.5 backend:** the plan event carries `code`; a final `usage` is emitted, and `run.finished` carries `usage`.
- **2.5 UI**
  - The UI reads the API origin from the same variables as the API.
  - SSE goes direct; REST goes via the rewrite.
  - Generated types live at `ui/src/types/api.ts`.
  - One reducer absorbs the stream's quirks.
  - "opt" prompts are disabled until GEPA.
  - Feedback opens at `run.finished`.
  - Dependencies added: react-query, react-markdown and remark-gfm, vitest.
- **Housekeeping**
  - Day 1 transcript committed unredacted.
  - `OPERATOR_GUIDE.md` no longer ignored.
  - `.env.example` shows the DeepSeek judge and says to keep overrides commented.
  - 2.6 and the holdout bench deferred.

## Open issues

- **Judge variance, before any holdout number.** Re-scoring identical answers moved answer
  correctness 0.3–0.5 per row. Choose majority-of-3 judge calls or `report.py --passes N`.
- **Holdout bench not run.** docs/09's end-of-day step, deferred until the variance decision.
- **Prime answer quality on dev.**
  - Answer correctness is 0.68 against the baseline's 0.87. glp1-path-002 concluded "not covered" from an unrelated Part B exclusion article.
  - 3 of 5 dev runs hit the token budget.
  - Critic wording leaks into answers ("The reviewer flagged…").
  - Some cited passages don't support their sentence.
  - Carried from Day 2 runs: claim ids appear in answers, and the critic once made an uncited code claim.
- **Kimi judge in the 2.5 gate run** (`.env` override, now removed). Optional re-run for evidence under the approved judge.
- **Dev keys and metrics.** The two GLP-1 dev keys' governing documents are search-guessed wrong
  pages (`needs_review`). contradiction_handling, scope_handling and change-detection currency each
  rest on one dev record.
- **UI tests.** `useRunEvents` and `useRun` have no automated tests (vitest runs without a DOM);
  exercised in the browser gate. Run `pnpm build` only with the dev server stopped (shared `.next`).
- **No example runs.** `runs/examples/` is still empty, so a reviewer without keys has no sample runs to browse.
- **Local environment.** `make` is installed (winget) but not on the PATH of a shell started
  before the install; open a new terminal. Port 8000 is unusable on this machine; use 8765.

## Fallbacks in effect

- **Models:** no model fallback applied. Routing: root and critic `nvidia/nemotron-3-super-120b-a12b`;
  judge `deepseek-ai/DeepSeek-V4-Flash-0731` (a routing decision, not a fallback); sub-agent,
  extractor, evaluator and baseline `moonshotai/Kimi-K2.6`. `.env` now overrides none of them.
- **Harness fallbacks are code paths, not active overrides:** structured → fenced JSON for judge
  and evaluator, the critic ladder, and planning's structured and default rungs.
- **Budgets:** deep 400k tokens, 30 deep reads, 30 searches, 180 s. Fast 150k tokens, 3 searches,
  30 s. Tavily cache on for prime; the baseline stays uncached.

## Resume tomorrow

```bash
# Terminal 1: the API on PRIME_API_PORT (default 127.0.0.1:8765)
make dev-api            # = uv run python -m prime_search.api --reload
# Terminal 2: the UI on http://localhost:3000
make dev-ui             # = cd ui && pnpm dev

# checks
uv run pytest tests/ -q && uv run ruff check prime_search/ eval/ tests/
cd ui && pnpm test && pnpm exec tsc --noEmit && pnpm lint

# First decide judge variance (majority-of-3 vs --passes N; docs/11), then the deferred holdout bench:
make bench ARGS="--mode baseline --split holdout"
make bench ARGS="--mode prime --split holdout --prompt-set base"
uv run python -m eval.report            # holdout -> reports/final-report.md

# Day 3 starts at 3.1 (docs/09): GEPA on train/dev only, never holdout.
```

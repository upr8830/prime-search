# Day 3 — customer-facing wording, GEPA, final holdout bench, technical statement

Session record for Day 3 of the `docs/09` plan. Written by `/session-end 3`.

Day 3 opened with a customer-facing wording pass on the UI and answers, prompted by a Day 2 compare-view
screenshot. It then settled the judge-variance decision (majority-of-3 answer correctness), built and ran
GEPA (**3.1**), ran the final holdout bench (**3.2 `[G]`**, approved by the user) and wrote the technical
statement (**3.3**). Part of **3.4** is done too: the README was rebuilt, and example runs are committed for
readers without keys.

GEPA found no prompt that beat the base prompts, so the base prompts ship. On holdout, PRIME ties the starter on
answer correctness and is the only one of the two whose answers can be audited. **3.4** is not finished: the
fresh-clone test, the tag and the build-log index remain.

## Tasks completed

| Work | Commits | Check |
|---|---|---|
| Customer-facing wording (Day 2 follow-up) | `d7504d2` `7f2c31b` `d34b331` `34b7d5b` `633d053` `ebc90a6`; spec-review follow-ups `af3b9ee` `8453a5c` | Replay of run `01a09ccc…` and live deep run `01a09cf1…`, below |
| Judge variance | `169a70b` | `answer_correctness` is the majority of three concurrent judge calls; offline tests |
| 3.1 GEPA | `1dc1722` `c9cf567` `4367797` `24bfd58` `e1174f7` `f2b0171` | Smoke run `01a09d5d…`; invalid first run; valid re-run `runs/gepa/20260914-0128`; `reports/gepa-run.json` |
| 3.2 Final bench **[G]** | `70027ea` `5d234f3` `84bca86` | `reports/final-report.md`, four LangSmith experiments, below |
| 3.3 Technical statement | `4993d11` `b6d8ede` `1f656c9` `da7067f` `999b5b6` `75fa78f` `53b3ee7` `efefa05` | Figures and quotes checked against `reports/latest.json` and the bench files; screenshots in `reports/langsmith/` |
| 3.4 Packaging (partial) | `391da4f` `e13fe6c` `140380a` `c79e9d2` `7d470b2` `a921748` | README: build steps, GEPA re-run, reading order, proposed solution. `runs/examples/`: six runs, checked in the UI with no keys |

End of day:

- `uv run pytest tests/ -q` → **682 passed, 12 deselected** (the 12 are `live`-marked).
- `uv run ruff check prime_search/ eval/ tests/` → clean.
- In `ui/`: `pnpm test` → **25 passed**; `pnpm exec tsc --noEmit` and `pnpm lint` → clean.

## Gates passed

**3.2 `[G]` — the report has the headline table and three worked examples.**
[`reports/final-report.md`](../reports/final-report.md), generated with
`uv run python -m eval.report --split holdout --passes 2`. The user approved the gate.

The bench is holdout × {starter baseline, PRIME with base prompts}, two passes each. PRIME + GEPA is the base
prompts and was not run separately. 40 runs, 0 judge errors, all 12 metric keys populated. Failed runs: 1 for the
baseline (an empty answer), 0 for PRIME.

| holdout, mean ± half-range | baseline | PRIME |
|---|---|---|
| answer correctness | 0.64 ± 0.05 | 0.66 ± 0.09 |
| citation correctness | 0.00 | 0.63 ± 0.09 |
| currency | 0.31 ± 0.04 | 0.94 ± 0.01 |
| evidence recall | 0.00 | 0.74 ± 0.11 |
| contradiction handling | 0.25 ± 0.25 | 1.00 |
| composite | 0.36 ± 0.03 | 0.69 ± 0.08 |
| per question | 1 search, 17 s, 12k tokens | 25 calls, 194 s, 455k tokens |

- Worked examples: Easy `cgm-elig-003`, Contradiction `adv-cgm-002`, Out of scope `oos-002`.
- PRD targets (docs/00 §9): PRIME meets only tier-4 contradiction handling (n = 1).
- Experiments:
  - [baseline pass 1](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=8a382e68-e6c4-4087-a8c9-25627b52e46d)
  - [baseline pass 2](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=9c3640fd-6379-48d1-826a-64067c85b6e2)
  - [PRIME pass 1](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=74673468-7163-421b-a7c1-10f29b529bc6)
  - [PRIME pass 2](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=5fbbad9a-4a93-476c-9ceb-5078e6613966)
  - Screenshots are in [`reports/langsmith/`](../reports/langsmith/README.md), because the links need workspace access.
- The spec review confirmed every number. Its labelling fixes landed in `84bca86`: failed runs count empty answers
  across both passes, and sections drawn from the latest pass are labelled.

## Checks without a gate

- **Customer-facing wording.**
  - The replay of `01a09ccc…` shows a green "completed" badge and a generic limit note, with no red banners and a
    muted "skipped: couldn't read a page from facebook.com" under b5-r0 and b5-r1.
  - Live deep run `01a09cf1…` shows the note "Research limit reached (processing)" and one skipped line. The failed
    Facebook page was not fetched a second time, and the Unknowns section has no jargon.
- **3.1 GEPA smoke check.** Run `01a09d5d…` on cgm-elig-002 read the plan and judge prompts from the candidate set,
  counted 3 judge votes and one metric call, and built the reflective dataset.
- **3.1 GEPA result.** The base prompts scored 0.751 on dev, against 0.752 in the invalid first run. One plan.md
  proposal scored 0.707, so no optimized prompts were written. 16 metric calls, about $11–13; the invalid first run
  added about $8–10.
- **Examples without keys.** The API ran with no `.env`, no key variables and only `runs/examples/`, and the UI
  worked against it:
  - `/runs` lists the six example runs.
  - The PRIME run page renders its answer and search tree.
  - A CMS document shows its text; a supplier-site document says its text is not stored.

## What live runs found that the tests did not

- **GEPA 0.1.4 integration**, all caught before or during paid runs:
  - It reads `adapter.propose_new_texts` directly and swallows the AttributeError, so no candidate was ever
    proposed. The offline spec review caught this before any spend.
  - Its default logger writes `run_log.txt` as cp1252 on Windows, which crashed both proposals and two rollouts.
  - It passes an empty adapter state after the seed's dev evaluation, which wiped those rollouts from the report.
- **Model behaviour:**
  - A sub-agent ignored the plain-language prompt rule ("I exhausted my tool-call budget"), so notes are now
    cleaned in code.
  - The starter model returned empty content once: 967 output tokens, `finish_reason=stop`, no reasoning text.
- **Limits:** they are checked between steps, so runs finish over budget. 19 of 20 holdout PRIME runs hit a limit,
  15 of them the 180-second time limit.
- **External services:**
  - LangSmith rate-limited the account, so the PRIME pass-2 experiment shows 8 of 10 runs and feedback on 3 rows.
    The bench file is complete.
  - A Tavily extract of LCD L33822 stored CMS's "JavaScript disabled" page instead of the policy text. It is
    visible in an example run's document view.

## Decisions made today

The full text is in `docs/11-assumptions-and-approach.md`: 21 dated lines, all 2026-09-13.

- **Customer-facing wording, parts 1–8:**
  - Plain-language limit and stop notes.
  - Warning-level `error` events, and a failed page is never fetched again.
  - `run.finished.limits_reached`; limit-reached runs show as completed with a quiet note.
  - Muted notices, with retrieval misses shown in the search tree.
  - Frozen prompts edited before the holdout bench.
  - A code guard for notes (`plain_notes`), a plain deadline note and plain judge wording, and a per-page fetch
    lock.
  - Repeated warnings merged per task only.
- **Judge variance:** `answer_correctness` is the majority of three judge calls, for the bench and GEPA alike.
- **3.1:**
  - GEPA candidates run as in-memory prompt sets.
  - Option B: plan and judge only, then cut to 10 metric calls.
  - Spec-review fixes before any spend.
  - The first run was invalid (encoding); logger and adapter-state fixes followed.
  - Result: no improvement, and the base prompts ship.
- **3.2:**
  - Scope is baseline and prime-base only.
  - The result, and corrections to it (limit breakdown; failed runs include empty answers).
- **3.3:**
  - Screenshots instead of public LangSmith links.
  - The author's revision of the statement exceeds two pages (logged at session end).
- **R8:** example runs in `runs/examples/` keep fetched text for .gov sources only, with paths made run-relative.

## Open issues

- **Answer quality against the PRD targets:**
  - Citation correctness is 0.63 against a target of 0.85: about one cited sentence in three is unsupported.
  - Evidence recall is 0.74 (target 0.75), and currency on change questions is 0.69 (target 0.80).
  - Answer correctness is a tie with the starter.
- **Latency and variance.**
  - Most PRIME runs end at a limit.
  - Single questions swing between passes: adv-cgm-002 scored a composite of 0.90, then 0.60.
- **GEPA** made one proposal at 10 metric calls. A larger budget is untested.
- **TECHNICAL_STATEMENT.md after the author's revision:**
  - It is 1,454 prose words, beyond the two-page target.
  - Unsourced: "20–45 minutes of clinical-reviewer time per manual lookup".
  - Stronger than the data: GEPA "rejected a change that would have hurt the metric a payer cares about most" (it
    rejected on the dev composite).
  - Not verified this session: the CMS-0057-F timelines (72 hours expedited, 7 calendar days standard).
- **LangSmith:** the account is rate limited, and the PRIME pass-2 experiment is incomplete in LangSmith.
- **Example data:** the LCD L33822 text in one example run is CMS's JavaScript-disabled page.
- **`.env`:** the API warns at startup that `PRIME_LOG_JSON` and `PRIME_LOG_LEVEL` match no Settings field.
- **3.4 remaining:**
  - fresh-clone test (`make setup && make smoke && make ask`);
  - verify `starter_agent.py` is absent and `.env` is ignored;
  - `build-log/` index;
  - tag `v0.1.0`.
  - 3.5, a screen recording, is optional.
- **Transcript:** the Day 3 session transcript has not been exported. The Day 1 and Day 2 transcripts are committed.
- **Carried from Day 2:**
  - `useRunEvents` and `useRun` have no automated tests.
  - The two GLP-1 dev keys' governing documents are search-guessed (`needs_review`).

## Fallbacks in effect

- **Models:** no model fallback applied.
  - Root and critic: `nvidia/nemotron-3-super-120b-a12b`.
  - Judge: `deepseek-ai/DeepSeek-V4-Flash-0731`.
  - Sub-agent, extractor, evaluator and baseline: `moonshotai/Kimi-K2.6`.
- **Evaluation:** `answer_correctness` is the majority of three judge calls, and the holdout is reported as two
  passes.
- **Prompts:** the base prompts ship. `prime_search/prompts/optimized/` does not exist.
- **Budgets:**
  - Deep: 400k tokens, 30 deep reads, 30 searches, 180 s.
  - Fast: 150k tokens, 3 searches, 30 s.
  - GEPA rollouts: 20 searches and 4 agents per round.
  - The Tavily cache is on for PRIME, the bench and GEPA; the baseline is uncached.
- **Harness fallbacks:** these are code paths, not overrides.
  - Structured output falls back to fenced JSON.
  - The critic ladder and the planning rungs.
  - GEPA uses `Utf8Logger`, and a crashed rollout is not reused.

## Resume tomorrow

```bash
# Terminal 1: the API on PRIME_API_PORT (default 127.0.0.1:8765)
make dev-api            # = uv run python -m prime_search.api --reload
# Terminal 2: the UI on http://localhost:3000
make dev-ui             # = cd ui && pnpm dev

# checks
uv run pytest tests/ -q && uv run ruff check prime_search/ eval/ tests/
cd ui && pnpm test && pnpm exec tsc --noEmit && pnpm lint

# Next: task 3.4 packaging (docs/09): fresh-clone test (make setup && make smoke && make ask),
# verify starter_agent.py is absent and .env ignored, build-log index, tag v0.1.0.
```

**Next task id: 3.4.**

# LangSmith screenshots (task 3.3)

The technical statement links to LangSmith experiments and traces, and those links need workspace access.
These screenshots show the same pages for readers without it (docs/09 §3.3).

- **When:** captured 2026-09-13.
- **Cropped:** to the page content; the account sidebar is not shown.
- **Zoom:** pages are at 75% so more metric columns fit. Wide tables are still cut at the right edge.

The reported numbers come from the committed bench files in `reports/bench/`, through
`reports/final-report.md`. LangSmith holds a copy of the same runs and feedback.

| File | What it shows |
|---|---|
| [`holdout-starter-pass1.png`](holdout-starter-pass1.png) | Experiment `baseline-none-holdout-20260914-0222-5487b5be`: the starter, holdout pass 1, 10 of 10 runs, with each question's evaluator scores and the column averages. |
| [`holdout-starter-pass2.png`](holdout-starter-pass2.png) | Experiment `baseline-none-holdout-20260914-0227-3acdec9e`: the starter, pass 2. Row 3 (adv-cgm-002) is the run that returned no answer text: its output cell holds only a trace URL, and it scores 0 (docs/11). |
| [`holdout-prime-pass1.png`](holdout-prime-pass1.png) | Experiment `prime-base-holdout-20260914-0232-1acb321c`: PRIME with base prompts, pass 1, 10 of 10 runs. |
| [`holdout-prime-pass2.png`](holdout-prime-pass2.png) | Experiment `prime-base-holdout-20260914-0250-7ded4cbf`: PRIME, pass 2. **LangSmith shows 8 of 10 runs and evaluator feedback on only 3 rows**, and the account showed a rate-limit notice at capture. The committed bench file `reports/bench/prime-base-holdout-20260914-0250-7ded4cbf.json` holds all 10 scored rows, and the report uses that file. |
| [`trace-adv-cgm-002-prime-pass1.png`](trace-adv-cgm-002-prime-pass1.png) | PRIME's pass-1 trace for the contradiction question used in the statement's before/after. See below. |
| [`trace-adv-cgm-002-starter-pass1.png`](trace-adv-cgm-002-starter-pass1.png) | The starter's pass-1 trace for the same question. See below. |

**What the two traces show:**

- **PRIME:** the waterfall of planning, search sub-agents and model calls (192 s).
  - Tags: `mode:prime`, `depth:deep`, `prompt_set:base`, `source:bench`, `bench:holdout`.
  - Metadata: `git_sha` `da7067f`, `question_id` `adv-cgm-002`, `tavily_cache` true.
- **Starter:** one model call, one `tavily_search` and a second model call (9.4 s).
  - Tags: `mode:baseline`, `source:bench`, `bench:holdout`.
  - Metadata: `tavily_cache` false.
- **Empty Output panel:** in both traces the root run's Output panel is empty. The answer is saved in the
  run record and the bench file, not as the root trace's output.

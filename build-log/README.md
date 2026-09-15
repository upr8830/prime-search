# Build log

The build followed the three-day plan in [`docs/09`](../docs/09-implementation-plan.md). There is one
summary per session, written by `/session-end` at the end of the day. Each summary lists the tasks and
commits, the gates passed with evidence, what live runs found that tests did not, the day's decisions,
open issues, the fallbacks in effect and how to resume.

**Start with the summaries.** Open a transcript only when you need to check a specific claim.

## Sessions

| Day | Summary | Tasks and gates | Result |
|---|---|---|---|
| 1 | [`day1.md`](day1.md) | 1.1–1.8; gates **1.2** (config and models) and **1.7** (end-to-end answer) | A coverage question becomes a cited answer drawn from primary CMS sources; the starter-equivalent baseline answers the same question from secondary sites with no passages. SearchBench draft keys: 47 drift flags across 23 of 30 records. 405 tests. |
| 2 | [`day2.md`](day2.md) | 2.1–2.5; gates **2.1** (SearchBench validated), **2.3** (dev report) and **2.5** (UI) | 30 answer keys validated and synced to LangSmith; judge and critic loop; evaluators and dev bench with all 12 metric keys; HTTP API; side-by-side UI with thumbs reaching LangSmith. 625 tests. |
| 3 | [`day3.md`](day3.md) | 3.1–3.3 and part of 3.4; gate **3.2** (final holdout bench) | GEPA found no prompt that beat the base prompts, so the base prompts ship. On holdout, PRIME ties the starter on answer correctness (0.66 vs 0.64) and leads on citation correctness (0.63 vs 0.00), currency (0.94 vs 0.31) and composite (0.69 vs 0.36). Technical statement written. 682 tests. |

The full holdout results are in [`reports/final-report.md`](../reports/final-report.md).

## Supporting files

| File | What it is |
|---|---|
| [`day1-trace.png`](day1-trace.png) | LangSmith waterfall of a Day 1 baseline run on the 1.7 gate question: two Tavily searches, about 24 s. |
| [`day2-ui-gate.gif`](day2-ui-gate.gif) | Recording of the 2.5 gate: a deep run in both UI panes, with thumbs sent to LangSmith (5.5 MB). |
| [`day1-transcript.md`](day1-transcript.md) | Raw Day 1 Claude Code session, exported with `/export` (21,495 lines, 1.2 MB). |
| [`day2-transcript.md`](day2-transcript.md) | Raw Day 2 session (19,093 lines, 1.1 MB). |
| [`day3-transcript.md`](day3-transcript.md) | Raw Day 3 session (20,249 lines, 1.2 MB). |

The transcripts are committed unredacted by the author's decision. In the Day 1 and Day 2 transcripts,
some lines match patient-detail patterns. They come from the synthetic `oos-002` question and the
patient-detail guard's test strings, not from patient records. The Decision log in
[`docs/11`](../docs/11-assumptions-and-approach.md) records this and every other decision the summaries
cite.

## Related

- [`docs/11-assumptions-and-approach.md`](../docs/11-assumptions-and-approach.md): the dated decision log.
- [`docs/13-claude-code-practices.md`](../docs/13-claude-code-practices.md): how the sessions were run
  (skills, hooks, spec reviews).
- [`reports/`](../reports/): bench files, dev and final reports, the GEPA run and model selection.

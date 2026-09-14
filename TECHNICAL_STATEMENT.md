# PRIME Search: turning a search call into an investigation

*Coverage-determination research on Tavily, LangGraph, and Nebius Token Factory*

## 1. Why this matters: a coverage answer is only worth what it can survive

Payer utilization management turns coverage policy into decisions, and a decision built on the wrong
research does not fail on the day it is made. It fails weeks later, as a denial that is appealed and
overturned, care that was delayed, or an improper payment a regulator finds. The problem is measured,
not hypothetical: HHS-OIG found that 13% of sampled Medicare Advantage prior-authorization denials met
Medicare coverage rules (OEI-09-18-00260, 2022). Since 2024, CMS has required MA plans to apply
traditional Medicare's NCD and LCD criteria (CMS-4201-F), and the prior-authorization rule (CMS-0057-F)
puts decisions on a clock — 72 hours for expedited requests, seven calendar days for standard ones —
with public reporting. Reviewers have less time to reach an answer that has to hold up longer.

"Is a CGM covered under Medicare for a type 2 diabetic not on insulin?" looks like one search. But the
answer spans LCD L33822 and billing article A52464, which have different revision dates. A 2023 revision
changed the insulin rule, and supplier pages misstate coverage. The tempting fix is the starter agent's
design: paraphrase the top-ranked page and cite a URL. It is fast and fluent, and it is the riskiest
option on the table, because it removes the reviewer's instinct to double-check while giving them
nothing to check. In a regulated workflow that is not a weaker product; it is a liability. The bar is an
answer that is **right, current and auditable**, and auditable is the one a search call cannot meet.

## 2. What I built: an investigation that shows its evidence

PRIME keeps the starter's stack (Tavily, LangChain, Nebius) and changes how it researches. Its design
rule: **no claim without a verbatim, dated passage a reviewer can open.**

- **Plan.** A LangGraph root (Nemotron-3 Super) writes the plan as Python. It has branches for
  criteria, codes, currency and conflicting sources, aimed at primary policy.
- **Evidence.** Parallel sub-agents (Kimi-K2.6) search and read through Tavily and record verbatim
  passages, each checked against the fetched paragraph, with document, location, effective date and
  stance.
- **Review.** A judge (DeepSeek-V4-Flash) checks each round's coverage and adds targeted tasks. A critic
  looks for weak claims, missed interpretations and secondary sources that contradict primary ones.
- **Answer.** Every claim is cited. The answer lists effective dates, names each contradiction and which
  source governs, and states what could not be verified. It answers at policy level, and the decision
  stays with the reviewer. Token, search and time budgets cap every run.

```
understand ─► plan ─► dispatch ─(Send ×N)─► search_agent ─► collect ─► judge ─┬─ insufficient ─► dispatch
                                                                           └─ sufficient ─► critic ─┬─ needs more ─► dispatch
                                                                                                    └─ pass ─► synthesize
```

In the assignment's terms, PRIME improves retrieval quality (decomposition, primary sources), source
handling and citations (evidence objects), and the evaluation loop (SearchBench's 30 person-validated
questions and 12 metrics, and GEPA). It also adds LangSmith observability and a side-by-side UI.

## 3. How I know it is better

The holdout is 10 questions never used in development, run in two passes (mean ± half-range) against the
starter reproduced exactly. Read the rows as three different people would: a reviewer asks whether the
answer is right, an auditor asks whether each cited passage supports its claim, and an appeals board asks
whether it rests on the governing document and date.

| holdout, 2 passes | starter | PRIME | PRIME + GEPA |
|---|---|---|---|
| answer correctness | 0.64 ± 0.05 | 0.66 ± 0.09 | = PRIME |
| citation correctness (cited passage supports the claim) | 0.00 | 0.63 ± 0.09 | = PRIME |
| currency (governing document and date) | 0.31 ± 0.04 | 0.94 ± 0.01 | = PRIME |
| evidence recall | 0.00 | 0.74 ± 0.11 | = PRIME |
| contradiction handling | 0.25 ± 0.25 | 1.00 | = PRIME |
| composite | 0.36 ± 0.03 | 0.69 ± 0.08 | = PRIME |
| per question: search calls, latency, tokens | 1, 17 s, 12k | 25, 194 s, 455k | = PRIME |

**Before and after (pass 1).** "I read that Medicare requires three or more insulin injections per day
before it will cover a CGM. Is that still true?" The answer key says no: the April 2023 LCD revision
removed that requirement.

- **Starter** (answer correctness 0.73, currency 0.50). "No—that is no longer true. Medicare removed the
  'three injections per day' requirement in 2023." It cites three URLs (the LCD, a YouTube webinar, a
  Dexcom page), states no governing date and misses a must-have claim. In pass 2 it returned nothing.
- **PRIME** (answer correctness 1.00, currency 1.00, evidence recall 1.00). "No. As of the April 2023
  revision—reflected in LCD L33822 (effective 2024-10-01) and Article A52464 (effective 2025-02-18)—
  Medicare no longer requires three or more insulin injections per day." It quotes the LCD ("The
  beneficiary is insulin-treated;"), names two supplier pages that state an injection-count rule, says
  the LCD and article govern, and lists what it could not verify. But 3 of 7 sampled citations did not
  support their sentence, and in pass 2 it scored a composite of 0.60.

**Honest notes.**

- **Equally right; only PRIME can be checked.** Answer correctness is a tie, inside both spreads. The
  starter would score 0.67 if its one empty answer took its other pass's score. The difference is what a
  reviewer relies on: cited verbatim passages (URL citations score 0 by construction) and the governing
  document and date (currency 0.94 against 0.31). That tie is the business case in miniature: a fluent
  answer that is right two times in three and unauditable every time is exactly what a payer must not
  deploy, and the starter's silent empty answer in pass 2 is the failure mode a reviewer never sees.
- **Targets missed.** PRIME meets only the docs/00 §9 contradiction target, on one tier-4 question. It
  misses evidence recall (0.74 against 0.75), citation correctness (0.63 against 0.85), currency on
  change questions (0.69 against 0.80) and the +0.25 answer-correctness lift. About one cited sentence
  in three is not supported by its passage. For a payer that is the next thing to fix, and it is fixable
  because it is now measured: the starter's equivalent number is unmeasurable.
- **Limits and variance.** 19 of 20 PRIME runs hit a research limit (15 of them the 180-second limit),
  and single questions swing between passes. Scores use a majority of three judge calls and two passes,
  because a single call moved answer correctness by 0.3–0.5. Latency, not cost, is the operational
  constraint; the fast/deep depth setting exists to manage it.
- **GEPA found no improvement.** Its one planner rewrite scored 0.71 on dev against the base prompts'
  0.75, so the base prompts ship and PRIME + GEPA equals PRIME. The loop did its job: it rejected a
  change that would have hurt the metric a payer cares about most.
- **Cost.** About $0.60–0.95 per scored PRIME question; the holdout bench (40 runs) cost about $15–20.
  Set against 20–45 minutes of clinical-reviewer time per manual lookup and the cost of one overturned
  denial, the economics are not close.

## 4. Decisions worth explaining

- **The evidence unit, not the document.** A verbatim, located, dated passage makes each claim auditable,
  citation correctness measurable and disagreement between sources detectable. It is also what an
  appeals file needs: the passage, the document, the revision date.
- **Answer keys from live sources, with `as_of`.** Checking my 30 draft keys against the 17 governing
  documents raised 41 flags on 21 keys: wrong dates, missing phrases, "stale" claims still in force. A
  person corrected them. A benchmark written from memory would grade against stale policy, and the
  same drift is why a customer's benchmark has to be re-validated on a schedule.
- **Code-as-action for the root.** Reasoning models on this endpoint were reported to reject native tool
  calls, so the root writes its plan as sandboxed Python, which is executable, traceable and has
  fallbacks.
- **Not built:** search memory, learned skills and an RL-trained search policy (roadmap R1, R2, R7).
  GEPA was the one learning loop, because it could be measured with evaluators I needed anyway.

## 5. Where the value sits, and what this means for Tavily

Every payer, provider and vendor can reach the same CMS pages. The index is not the asset. The asset is
the **search policy** — where criteria live versus codes, which revision governs, when a supplier page is
overstating, when to stop — made explicit, measured against a benchmark the customer owns, and improved
under a guardrail that rejects regressions. That asset compounds with every validated question a
customer adds, and none of it depends on which model or index sits underneath.

Regulated buyers do not purchase "web search for agents"; they purchase auditable answers with
provenance, one workflow at a time. This build is the shape of that engagement: Tavily as the retrieval
layer under an evidence-graph agent, a customer-validated benchmark scored before go-live, and a UI a
reviewer can use without an engineer. A new domain needs a strategy card, source-tier rules and answer
keys; the graph, evidence store, evaluators, tracing and harness stay the same.

The next steps are to:

1. Raise citation correctness to the 0.85 target.
2. Extend to commercial payer policies and multi-jurisdiction MACs (R4).
3. Score a customer-validated SearchBench before go-live.
4. Add a security layer on fetched content (R8).

The system does the research; a person makes the decision.

## Appendix

- **Repository:** <https://github.com/upr8830/prime-search>. The README gives the reading order and build
  steps, and the decision log is `docs/11`.
- **Final report:** `reports/final-report.md` (headline, PRD targets, per-question scores, three worked
  examples). GEPA: `reports/gepa-run.json`. Build record: `build-log/`.
- **LangSmith holdout experiments.** The links need workspace access; screenshots of each experiment and
  trace are in [`reports/langsmith/`](reports/langsmith/README.md):
  - starter [pass 1](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=8a382e68-e6c4-4087-a8c9-25627b52e46d),
    [pass 2](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=9c3640fd-6379-48d1-826a-64067c85b6e2);
  - PRIME [pass 1](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=74673468-7163-421b-a7c1-10f29b529bc6),
    [pass 2](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/datasets/9dc81116-8a93-480c-9da2-29cacc1e9370/compare?selectedSessions=5fbbad9a-4a93-476c-9ceb-5078e6613966).
- **Example traces:** [starter](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09db9-1185-7f83-9b7e-12fc9eef892c/run/01a09db9-1185-7f83-9b7e-12fc9eef892c?start_time=2026-09-14T02%3A22%3A26.693205%2B00%3A00),
  [PRIME](https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/01af4853-3039-4f3d-a21e-76ab951f0fbb/trace/01a09dc2-3089-7383-9c7f-24bd8a93cd69/run/01a09dc2-3089-7383-9c7f-24bd8a93cd69?start_time=2026-09-14T02%3A32%3A24.457268%2B00%3A00).
- **Cited:**
  - HHS-OIG, *Some Medicare Advantage Organization Denials of Prior Authorization Requests Raise Concerns
    About Beneficiary Access to Medically Necessary Care*, OEI-09-18-00260, April 2022
    (<https://oig.hhs.gov/reports/all/2022/some-medicare-advantage-organization-denials-of-prior-authorization-requests-raise-concerns-about-beneficiary-access-to-medically-necessary-care/>).
  - CMS, 2024 Medicare Advantage and Part D Final Rule, CMS-4201-F, fact sheet, April 2023
    (<https://www.cms.gov/newsroom/fact-sheets/2024-medicare-advantage-and-part-d-final-rule-cms-4201-f>).
  - CMS, Interoperability and Prior Authorization Final Rule, CMS-0057-F, January 2024
    (<https://www.cms.gov/newsroom/fact-sheets/cms-interoperability-and-prior-authorization-final-rule-cms-0057-f>).
    <!-- verify URL and the 72-hour / 7-day timeframes before submitting; delete this comment after -->

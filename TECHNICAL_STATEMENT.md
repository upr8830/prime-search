# PRIME Search: turning a search call into an investigation

*Coverage-determination research on Tavily, LangGraph, and Nebius Token Factory*

## 1. The problem: guideline decisions where a wrong answer costs patients and payers

Payer utilization management turns coverage guidelines into decisions. A wrong decision has two costs.
A patient who meets the criteria is denied care or has it delayed. A payer that misapplies the criteria
pays improperly, or faces appeals, overturned decisions and regulatory exposure. The problem is
documented. HHS-OIG found that 13% of sampled Medicare Advantage prior-authorization denials met Medicare
coverage rules (OEI-09-18-00260, 2022). Since 2024, CMS requires MA plans to apply traditional Medicare's
NCD and LCD criteria (CMS-4201-F). The research behind a decision has to be right, current and auditable.

Coverage research makes that hard. "Is a CGM covered under Medicare for a type 2 diabetic who is not on
insulin?" looks like one search. But the answer spans LCD L33822 and its billing article A52464, which
differ in content and revision dates. The 2023 revision changed the insulin requirement, and supplier
pages overstate or understate coverage. GLP-1 questions add Part D's weight-loss exclusion and FDA
labels. The starter agent paraphrases the top-ranked page, cites a URL and never says that two sources
disagree. A reviewer gets a fluent answer they cannot audit.

## 2. What I built: an investigation that shows its evidence

PRIME keeps the starter's stack (Tavily, LangChain, Nebius) and changes how it researches. Its design
rule: **no claim without a verbatim, dated passage a reviewer can open.**

- **Plan.** A LangGraph root (Nemotron-3 Super) writes the plan as Python over a workspace. The plan
  has branches for criteria, codes, currency and conflicting sources, aimed at primary policy.
- **Evidence.** Parallel sub-agents (Kimi-K2.6) search and read through Tavily and record evidence.
  Each item is a verbatim passage checked against the fetched paragraph, with its document, location,
  effective date and stance. Snippets are never evidence.
- **Review.** After each round a judge (DeepSeek-V4-Flash) checks whether the evidence answers every
  branch, and adds targeted tasks if not. A critic then looks for weak claims, missed interpretations
  and secondary sources that contradict the primary ones.
- **Answer.** Every claim is cited. The answer lists the effective dates relied on, names each
  contradiction and which source governs, and says what could not be verified. It answers at policy
  level and never decides an individual case; the decision stays with the reviewer.
- **Bounds.** Token, search and time budgets cap every run. Documents stay in workspace variables,
  not in the model's context.

```
understand ─► plan ─► dispatch ─(Send ×N)─► search_agent ─► collect ─► judge ─┬─ insufficient ─► dispatch
                                                                           └─ sufficient ─► critic ─┬─ needs more ─► dispatch
                                                                                                    └─ pass ─► synthesize
```

In the assignment's terms, PRIME improves retrieval quality (decomposition and primary-source targeting),
source handling and citations (evidence objects), and the evaluation loop: SearchBench, 30 questions with
person-validated answer keys, train, dev and holdout splits and 12 metrics, plus GEPA. It also adds
LangSmith observability and a side-by-side UI.

## 3. How I know it is better

The holdout is 10 questions never used in development, run in two passes (mean ± half-range) against the
starter reproduced exactly.

| holdout, 2 passes | starter | PRIME | PRIME + GEPA |
|---|---|---|---|
| answer correctness | 0.64 ± 0.05 | 0.66 ± 0.09 | = PRIME |
| citation correctness (cited passage supports the claim) | 0.00 | 0.63 ± 0.09 | = PRIME |
| currency (governing document and date) | 0.31 ± 0.04 | 0.94 ± 0.01 | = PRIME |
| evidence recall | 0.00 | 0.74 ± 0.11 | = PRIME |
| contradiction handling | 0.25 ± 0.25 | 1.00 | = PRIME |
| composite | 0.36 ± 0.03 | 0.69 ± 0.08 | = PRIME |
| per question: search calls, latency, tokens | 1, 17 s, 12k | 25, 194 s, 455k | = PRIME |

**Before and after, pass 1.** The question: "I read that Medicare requires three or more insulin
injections per day before it will cover a CGM. Is that still true?" The answer key says no: the April
2023 LCD revision removed that requirement.

- **Starter** (answer correctness 0.73, currency 0.50). "No—that is no longer true. Medicare removed the
  'three injections per day' requirement in 2023." It lists the current criteria and cites three URLs:
  the LCD, a YouTube webinar and a Dexcom page. No passage stands behind any sentence, it states no
  governing date, and it misses a must-have claim. In pass 2 it returned no answer at all.
- **PRIME** (answer correctness 1.00, currency 1.00, evidence recall 1.00). "No. As of the April 2023
  revision—reflected in LCD L33822 (effective 2024-10-01) and Article A52464 (effective 2025-02-18)—
  Medicare no longer requires three or more insulin injections per day." Each criterion quotes the LCD
  ("The beneficiary is insulin-treated;") with a citation. The Contradictions section names two supplier
  pages that state an injection-count rule and says the LCD and article govern. It also lists what it
  could not verify. But 3 of its 7 sampled citations did not support their sentence, and in pass 2 the
  same question scored a composite of 0.60.

**Honest notes.**

- **Equally right; only PRIME can be checked.** Answer correctness is a tie, inside both spreads. Giving
  the starter's one empty answer its other pass's score would make it 0.67. The difference is what a
  reviewer needs to rely on an answer: cited verbatim passages (the starter's URL citations score 0 by
  construction) and the governing document and date (currency 0.94 against 0.31).
- **Targets not met.** Of the docs/00 §9 targets, PRIME meets only contradiction handling, on the one
  tier-4 contradiction question. It misses evidence recall (0.74 against 0.75), citation correctness
  (0.63 against 0.85), currency on change questions (0.69 against 0.80) and the +0.25
  answer-correctness lift. Citation correctness of 0.63 means about one cited sentence in three is not
  supported by its passage. For a payer that is the next thing to fix.
- **Limits and variance.** 19 of 20 PRIME runs hit a research limit, 15 of them the 180-second limit, and
  single questions swing between passes. One judge call moved answer correctness by 0.3–0.5, so scores
  use the majority of three judge calls and two passes.
- **GEPA found no improvement.** Its one proposal rewrote the planner prompt. It improved on its train
  questions but scored worse on dev (0.71 against 0.75). The base prompts ship, so PRIME + GEPA equals
  PRIME.
- **Cost.** About $0.60–0.95 per scored PRIME question at list prices. The full holdout bench (40 runs
  with scoring) cost about $15–20.

## 4. Decisions worth explaining

- **The evidence unit, not the document.** A verbatim, located, dated passage makes each claim
  auditable and citation correctness measurable. It also lets the system detect when sources disagree.
- **Answer keys come from live sources, with `as_of`.** I drafted the 30 keys from my own knowledge and
  checked them against the 17 governing documents. That raised 41 flags on 21 keys: wrong dates, missing
  phrases, "stale" claims still in force, and sources that could not be found. A person corrected them
  during validation. A benchmark written from memory would grade against stale policy.
- **Code-as-action for the root.** Reasoning models on this endpoint were reported to reject native tool
  calls. The root therefore writes its plan as Python in a sandbox, which makes it an executable,
  traceable object with repair and default-plan fallbacks.
- **Not built:** search memory, learned skills and an RL-trained search policy (roadmap R1, R2, R7).
  GEPA was the one learning loop, because it could be measured with evaluators I needed anyway.

## 5. How this maps to an FDE engagement

For a payer this is a reference architecture: Tavily under an evidence-graph agent, with a benchmark the
customer owns and validates against its own policies. Moving it to another domain takes a new strategy
card, source-tier rules and answer keys; the graph, evidence store, evaluators, tracing and harness stay
the same.

The next steps are:

1. Raise citation correctness, the gap the holdout shows.
2. Extend to commercial payer medical policies and multi-jurisdiction MACs (R4).
3. Score a customer-validated SearchBench before go-live.
4. Add a security layer on fetched content (R8).

Throughout, the system does the research and a person makes the decision.

## Appendix

- **Repository:** <https://github.com/upr8830/prime-search>. The README gives the reading order and build
  steps, and the decision log is `docs/11`.
- **Final report:** `reports/final-report.md` (headline, PRD targets, per-question scores, three worked
  examples). GEPA: `reports/gepa-run.json`. Build record: `build-log/`.
- **LangSmith holdout experiments** (workspace access required):
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

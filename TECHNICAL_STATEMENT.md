# PRIME Search: turning a search call into an investigation

*Coverage-determination research on Tavily, LangGraph, and Nebius Token Factory*

<!-- DRAFT (task 3.3). Every ⟨3.2⟩ marker is filled from reports/final-report.md once task 3.2's
holdout bench finishes. No number below that carries a marker is a result yet. -->

## 1. The problem: guideline decisions where a wrong answer costs patients and payers

Payer utilization management turns coverage guidelines into decisions. A wrong decision has two costs.
A patient who meets the criteria is denied care or has it delayed. A payer that misapplies the criteria
pays improperly, or faces appeals, overturned decisions and regulatory exposure. The problem is
documented. HHS-OIG found that 13% of sampled Medicare Advantage prior-authorization
denials met Medicare coverage rules (OEI-09-18-00260, 2022). Since 2024, CMS requires MA plans to apply
traditional Medicare's NCD and LCD criteria (CMS-4201-F). The research behind a decision has to be
right, current and auditable.

Coverage research makes that hard. "Is a CGM covered under Medicare for a type 2 diabetic who is not on
insulin?" looks like one search. But the answer spans LCD L33822 and its billing article A52464, which
differ in content and revision dates. The 2023 revision changed the insulin requirement, and supplier
pages overstate or understate coverage. GLP-1 questions add Part D's weight-loss exclusion and FDA
labels. The starter agent paraphrases the top-ranked page, cites a URL and never says that two
sources disagree. A reviewer gets a fluent answer they cannot audit.

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

one real run (cgm-elig-001, deep): 5 branches → round 0 judge: sufficient → critic 45%, 1 recommended
search → task b1-r1-critic1 → round 1 judge: sufficient → critic 80% → cited answer; 179 s, 312k tokens
```

In the assignment's terms, PRIME improves:

- **Retrieval quality:** decomposition and primary-source targeting.
- **Source handling and citations:** evidence objects.
- **The evaluation loop:** SearchBench (30 questions with person-validated answer keys, train, dev
  and holdout splits, 12 metrics) and GEPA.

It also adds LangSmith observability and a side-by-side UI.

## 3. How I know it is better

The holdout is 10 questions never used in development, run in two passes and reported as mean ±
half-range, against the starter reproduced exactly. For a payer the first three rows matter most: is
the answer right, does each cited passage support its claim, and does the answer rest on the governing
document and date?

| metric (holdout) | baseline | PRIME | PRIME + GEPA |
|---|---|---|---|
| answer correctness | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |
| citation correctness | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |
| currency (governing document and date) | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |
| evidence recall | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |
| contradiction handling | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |
| search cost (searches + fetches) | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |
| latency (s) / tokens per question | ⟨3.2⟩ | ⟨3.2⟩ | = PRIME |

**Before / after (the holdout contradiction question, ⟨3.2⟩).**
<!-- 6–8 lines each from reports/final-report.md's contradiction worked example (adv-cgm-002): the
starter's answer, then PRIME's Contradictions section and the governing source it names. -->
- *Starter:* ⟨3.2⟩
- *PRIME:* ⟨3.2⟩

**Honest notes.**
- **Correct is not enough; it has to be verifiable.** The baseline scores 0 on evidence recall and
  citation correctness by construction, because its citations are URLs with no stored passage. On the
  5-question dev check its fluent answers beat PRIME's on answer correctness, but a reviewer still could
  not audit them. That is why the holdout comparison, not dev, is the claim.
- **Evaluator noise.** One judge call moved single-question answer correctness by 0.3–0.5. Scores
  therefore use the majority of three judge calls and two passes.
- **GEPA found no improvement.** Its one proposal rewrote the planner prompt. It did better on its 3
  train questions but worse on dev (0.707 against 0.751), including a 0.28 loss on a contradiction
  question. The base prompts ship, so PRIME + GEPA equals PRIME.
- **Cost.** A deep question takes about 440k tokens and 160 s, against the starter's 9k tokens and 12 s.
  That is roughly $0.60–0.95 per scored question at list prices, a cost to weigh against a decision
  that has to hold up on appeal.

## 4. Decisions worth explaining

- **The evidence unit, not the document.** A verbatim, located, dated passage makes each claim
  auditable and citation correctness measurable. It also lets the system detect when sources disagree.
- **Answer keys come from live sources, with `as_of`.** I drafted the 30 keys from my own knowledge and
  checked them against the 17 governing documents. That raised 41 flags on 21 keys: wrong dates,
  missing phrases, "stale" claims still in force, and sources that could not be found. A person
  corrected them during validation. A benchmark written from memory would grade against stale policy,
  which is the failure the product exists to avoid.
- **Code-as-action for the root.** Reasoning models on this endpoint were reported to reject native
  tool calls. The root therefore writes its plan as Python in a sandbox, which makes it an executable,
  traceable object, with repair and default-plan fallbacks.
- **Not built:** search memory, learned skills and an RL-trained search policy (roadmap R1, R2, R7).
  GEPA was the one learning loop, because it could be measured with evaluators I needed anyway.

## 5. How this maps to an FDE engagement

For a payer this is a reference architecture: Tavily under an evidence-graph agent, with a benchmark
the customer owns and validates against its own policies. Moving it to another domain takes a new
strategy card, source-tier rules and answer keys; the graph, evidence store, evaluators, tracing and
harness stay the same.

The next steps are commercial payer medical policies and multi-jurisdiction MACs (R4), a
customer-validated SearchBench scored before go-live, and a security layer on fetched content (R8).
Throughout, the system does the research and a person makes the decision.

## Appendix

- **Repository:** <https://github.com/upr8830/prime-search>. Specs are `docs/00`–`docs/13`, and the
  decision log is `docs/11`.
- **Build record:** `build-log/`.
- **Final report:** `reports/final-report.md` ⟨3.2⟩.
- **GEPA run:** `reports/gepa-run.json`, with traces in the LangSmith project `prime-search-gepa`.
- **LangSmith experiments:** holdout ⟨3.2⟩.
- **Cited:**
  - HHS-OIG, *Some Medicare Advantage Organization Denials of Prior Authorization Requests Raise
    Concerns About Beneficiary Access to Medically Necessary Care*, OEI-09-18-00260, April 2022
    (<https://oig.hhs.gov/reports/all/2022/some-medicare-advantage-organization-denials-of-prior-authorization-requests-raise-concerns-about-beneficiary-access-to-medically-necessary-care/>).
  - CMS, 2024 Medicare Advantage and Part D Final Rule, CMS-4201-F, fact sheet, April 2023
    (<https://www.cms.gov/newsroom/fact-sheets/2024-medicare-advantage-and-part-d-final-rule-cms-4201-f>).

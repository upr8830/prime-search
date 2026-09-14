# PRIME Search: turning a search call into an investigation

*Coverage-determination research on Tavily, LangGraph, and Nebius Token Factory*

<!-- DRAFT (task 3.3). Every ⟨3.2⟩ marker is filled from reports/final-report.md once task 3.2's
holdout bench finishes. No number below that carries a marker is a result yet. -->

## 1. The problem I chose

"Is a CGM covered under Medicare for a type 2 diabetic who is not on insulin?" looks like one search.
It is not. The answer sits in a DME MAC Local Coverage Determination (LCD L33822) and its companion
billing article (A52464), which carry different content and different revision dates. The 2023
revision relaxed the insulin requirement, so most cached knowledge is wrong. Secondary sources
(supplier pages, beneficiary guides) often overstate or understate coverage. GLP-1 questions add
Part D's statutory weight-loss exclusion, FDA labels, and 2024–2026 CMS guidance and models.

The people who need this answer are payer utilization-management teams, provider prior-auth staff and
DME and pharmacy analysts. A confident, stale or partial answer turns into denials, appeals and
rework. That makes it a good test for a search agent: the sources are public and verifiable, the
answers are time-sensitive, and they are full of contradictions. The starter agent (one Tavily search,
one model call) returns whichever page ranks first, paraphrases it, cites a URL, and never says "these
two sources disagree."

## 2. What I built

PRIME keeps the starter's stack (Tavily, LangChain, Nebius) and changes how it searches.

- **Plan.** A LangGraph root investigator (Nemotron-3 Super) plans by writing Python against a
  workspace, not by calling tools. It decomposes the question into branches and targets primary
  sources through a domain strategy card.
- **Search.** Parallel search sub-agents (Kimi-K2.6) use Tavily search, extract and in-document
  reads. Each produces evidence objects: a verbatim passage that the tool validates against the
  fetched paragraph, with document, location, effective date and stance. Snippets are never evidence.
- **Judge.** After each round a judge (DeepSeek-V4-Flash) decides whether the evidence is sufficient
  or adds targeted tasks.
- **Critic.** A critic then looks for weak claims, missed interpretations and secondary sources that
  shadow primary ones.
- **Answer.** Synthesis writes a cited answer with explicit effective dates, contradictions and
  unknowns.
- **Budget.** A budget of tokens, searches, deep reads and wall time bounds every run. Documents stay
  in workspace variables, not in the model's context.

```
understand ─► plan ─► dispatch ─(Send ×N)─► search_agent ─► collect ─► judge ─┬─ insufficient ─► dispatch
                                                                           └─ sufficient ─► critic ─┬─ needs more ─► dispatch
                                                                                                    └─ pass ─► synthesize

one real run (cgm-elig-001, deep): 5 branches → round 0 judge: sufficient → critic 45%, 1 recommended
search → task b1-r1-critic1 → round 1 judge: sufficient → critic 80% → cited answer; 179 s, 312k tokens
```

In the assignment's terms, the improvements are:

- **Retrieval quality:** decomposition and primary-source targeting.
- **Source handling and citations:** evidence objects and claim-level citations.
- **Evaluation loop:** SearchBench, 30 validated questions with train, dev and holdout splits, 12
  metrics (LLM-judged where needed), and GEPA prompt optimization.
- **Observability:** LangSmith traces with run tags and thumbs feedback.
- **Harness:** a side-by-side UI that streams the investigation next to the starter.

## 3. How I know it is better

Holdout split (10 questions never used in development), two passes, mean ± half-range. The baseline
is the starter reproduced exactly (same model, prompt and single tool).

| metric (holdout) | baseline | PRIME | PRIME + GEPA |
|---|---|---|---|
| answer correctness | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |
| evidence recall | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |
| citation correctness | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |
| currency (governing document and date) | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |
| contradiction handling | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |
| search cost (searches + fetches) | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |
| latency (s) / tokens per question | ⟨3.2⟩ | ⟨3.2⟩ | ⟨3.2⟩ |

**Before / after (a contradiction question, ⟨3.2⟩ holdout example).**
<!-- 6–8 lines each from reports/final-report.md's contradiction worked example: the starter's
answer, then PRIME's, with the Contradictions section and the governing source it names. -->
- *Starter:* ⟨3.2⟩
- *PRIME:* ⟨3.2⟩

**Honest notes.**
- **The baseline's scores.** It scores 0 on evidence recall and citation correctness by construction:
  its citations are URLs with no stored passage to check. Answer correctness is where it competes. On
  the 5-question dev check, the starter's fluent answers beat PRIME's on answer correctness. That is
  why the holdout comparison, not dev, is the claim.
- **Evaluator noise.** One judge call moved single-question answer correctness by 0.3–0.5 when an
  unchanged answer was re-scored. Answer correctness is therefore the majority of three judge calls,
  and the holdout is run twice.
- **GEPA found no improvement.** With 10 metric calls on the planner and judge prompts it made one
  proposal: a rewrite of the planner's guidance into ten rules. The rewrite beat the base prompt on its
  three train questions but scored 0.707 on dev against the base prompts' 0.751. It won three dev
  questions by 0.03–0.05, within run-to-run noise, and lost a contradiction question by 0.28. No
  prompt beat base, so the PRIME + GEPA column runs the base prompts. The base dev score reproduced
  across two independent GEPA runs (0.752, 0.751).
- **Cost.** A deep PRIME run uses about 440k tokens and 160 s, against the starter's 9k tokens and
  12 s, which is roughly $0.60–0.95 per scored question at list prices. The budget caps searches and
  rounds; it checks tokens between steps, so runs can finish over the cap.

## 4. Decisions worth explaining

- **Code-as-action for the root.** Reasoning models on the Token Factory endpoint were reported to
  return text in `reasoning_content` and reject native tool calls. The root therefore writes a fenced
  Python cell that builds the plan in a sandbox. The plan becomes an executable, traceable object,
  with a repair turn, a structured-output rung and a default plan as fallbacks.
- **The evidence unit, not the document, is the primary object.** A verbatim, located, dated passage
  makes three things possible: claim-level citations a reader can open, a citation-correctness
  evaluator, and contradiction detection between sources.
- **Answer keys come from live sources, with `as_of`.** I drafted the 30 keys from my own knowledge,
  then fetched the 17 governing documents. The drift check raised 41 flags on 21 records: dates,
  missing key phrases, "stale" claims still in force, and unresolvable sources. Human validation
  corrected them. One GLP-1 pathway key was rewritten from CMS pages, and one out-of-scope question
  was rewritten at policy level.
- **What I did not build.** Search memory, a learned skill library and an RL-trained search policy
  (roadmap R1, R2, R7). GEPA was the one learning mechanism because it produces a before/after number
  with the evaluators I needed anyway.

## 5. How this maps to an FDE engagement

The pattern is a reference architecture: Tavily under an evidence-graph agent, with a benchmark the
customer owns. To move to another domain, swap the strategy card and the source-tier rules and write
new SearchBench keys. The graph, evidence store, evaluators, tracing and harness stay the same.

The next customer step is commercial payers and multi-jurisdiction MACs (roadmap R4). That comes with
a customer-validated SearchBench, and a security layer on fetched content (R8) before any deployment.

## Appendix

- **Repository:** <https://github.com/upr8830/prime-search>. Specs are `docs/00`–`docs/13`, and the
  decision log is `docs/11`.
- **Build record:** `build-log/` (session logs and transcripts).
- **Final report:** `reports/final-report.md` ⟨3.2⟩.
- **GEPA run:** `reports/gepa-run.json` (each candidate, its diff and dev scores; traces in the
  LangSmith project `prime-search-gepa`).
- **LangSmith experiments:** holdout ⟨3.2⟩.

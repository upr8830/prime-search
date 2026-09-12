# 00 — Product Requirements Document: PRIME Search for Coverage Determination Research

Version 0.1 · September 11, 2026 · Owner: Ujjwal · Status: approved for build

## 1. Summary

PRIME Search is an agentic search system that answers complex healthcare coverage questions —
initially CMS coverage of continuous glucose monitors (CGM) and GLP-1 receptor agonists — by
running an *investigation* rather than a single web search. It decomposes the question, searches
primary sources in parallel through Tavily, extracts claim-level evidence with document location and
effective date, detects contradictions and supersession, self-critiques, and produces a cited,
auditable answer. Every run is traced in LangSmith, scored against a purpose-built benchmark
(SearchBench), and the prompts are optimized against that score with GEPA.

It is delivered as a local application with a side-by-side harness comparing the starter agent
("simple search") with PRIME Search on the same question.

## 2. Problem

Coverage determination questions look simple and are not. "Is a CGM covered for a Medicare patient
with type 2 diabetes who is not on insulin?" requires reconciling:

- the DME MAC Local Coverage Determination (LCD) and its companion billing article, which carry
  different content and different revision dates;
- whether any National Coverage Determination (NCD) exists (for CGM there is none; for GLP-1 the
  relevant rules sit in Part D statute, CMS guidance memos, and Innovation Center models);
- HCPCS coding and modifier requirements that change independently of clinical criteria;
- FDA labeling that defines the indication a payer may or may not recognize;
- recent policy changes (2023 CGM criteria expansion; 2024–2026 GLP-1 coverage changes) that
  make most cached knowledge wrong.

A single-search agent returns whichever page ranks first, paraphrases it, and cites the URL. It has
no notion of effective dates, does not know that an LCD and an article differ, cannot tell a
secondary summary from the primary policy, and never says "these two sources disagree." The result
is confident, partial, or stale guidance — which is precisely the input that produces prior-auth
denials, appeals, and rework.

## 3. Users and personas

| Persona | Job to be done | What they need from the answer |
|---|---|---|
| **UM nurse / medical policy analyst (payer)** — primary | Determine whether a request meets criteria; document the basis | Criteria as bullet points, each tied to a policy section and date; required documentation list; codes |
| **Prior-auth specialist (provider / clinic)** | Submit a request that will be approved first time | Same as above, plus "what the reviewer will look for" |
| **DME supplier / pharmacy benefits analyst** | Confirm coverage before dispensing | Codes, frequency limits, supplier requirements, effective dates |
| **Pharma market-access analyst** | Track coverage changes for a product class | What changed, when, and the source |
| **Tavily FDE** — internal | Reference architecture for regulated-industry customers | A reusable pattern: Tavily as retrieval layer under an evidence-graph agent |

## 4. Goals

G1. Answer coverage questions with **claim-level citations** (document, section, effective date),
not URL-level citations.

G2. **Surface contradictions and supersession** explicitly instead of picking one source.

G3. **Reach current policy**: questions whose answer changed in 2023–2026 must be answered from the
current source, and the answer must state the date it relies on.

G4. **Measure it**: a benchmark with validated answer keys, automated evaluators, and a report that
shows baseline vs PRIME on the same questions.

G5. **Improve it**: an optimization loop (GEPA) that raises the benchmark score by editing prompts,
with a before/after report.

G6. **Show it**: a local UI where a reviewer can run the same question through both agents, watch
the investigation unfold, inspect the evidence graph, and give feedback that flows back into the
dataset.

## 5. Non-goals (for this delivery)

- Persistent cross-run memory, learned skill library, RL training. Designed in `10-roadmap.md`.
- Any payer beyond CMS (Medicare). Commercial payers are a roadmap item.
- Any therapeutic area beyond CGM and GLP-1.
- Patient-specific determinations. The system answers policy questions; it does not adjudicate cases.
- Production hardening: auth, multi-tenancy, rate-limit management beyond a simple budget.
- A hosted deployment.

## 6. Scenarios

### S1 — Eligibility criteria (CGM)
"Is a therapeutic CGM covered under Medicare for a type 2 diabetic who is not on insulin?"
Expected: cites LCD L33822 current criteria (insulin treatment *or* documented problematic
hypoglycemia), the April 2023 revision that introduced the non-insulin path, the definition of
problematic hypoglycemia, and the visit/documentation requirements. Flags that the LCD and the
policy article carry different content.

### S2 — Coding and supply (CGM)
"What HCPCS codes apply to a therapeutic CGM receiver and supplies, and what are the frequency
limits?" Expected: cites the policy article, not the LCD; lists current codes; notes the 2023 code
transition if the sources still reference old codes.

### S3 — Coverage pathway (GLP-1)
"Does Medicare cover semaglutide, and under what circumstances?"
Expected: distinguishes Part D coverage for type 2 diabetes from the statutory exclusion of
weight-loss drugs, the 2024 guidance allowing coverage for a medically accepted non-weight-loss
indication (cardiovascular risk reduction), and the 2025–2026 changes (pricing agreement, obesity
coverage pathway, Innovation Center model). States which of these are in effect today and which
are future-dated.

### S4 — Change detection (GLP-1)
"What changed in Medicare GLP-1 coverage in 2026?" Expected: an ordered list of changes with
effective dates and primary sources; secondary news sources allowed only to point to primary ones.

### S5 — Contradiction (cross-source)
"Is CGM covered for gestational diabetes under Medicare?" Expected: an honest answer that the LCD
covers "diabetes mellitus" with specific criteria, that some secondary sources overstate coverage,
and what documentation would be needed. The answer must say when sources disagree.

### S6 — Ambiguity / out of scope
"Will Aetna cover my Ozempic?" Expected: the system states this is a commercial payer outside its
verified scope, offers what it can find with lower confidence, and does not fabricate policy.

## 7. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Accept a natural-language question and a mode (`baseline` or `prime`) | Must |
| FR-2 | Baseline mode reproduces the starter agent: one model, one Tavily search tool, same system prompt | Must |
| FR-3 | Prime mode decomposes the question into a search plan of branches (hypotheses / sub-questions) | Must |
| FR-4 | Prime mode dispatches search sub-agents in parallel; each may search, fetch, and search within documents | Must |
| FR-5 | Each sub-agent returns **evidence objects** (claim, source, location, date, quality, confidence), not summaries | Must |
| FR-6 | An evidence judge decides `sufficient` / `insufficient` and, if insufficient, emits new search tasks within budget | Must |
| FR-7 | A critic reviews claims, evidence, and trajectory before synthesis; can trigger one more search round | Must |
| FR-8 | Synthesis produces an answer with numbered claim-level citations, an "effective dates relied on" section, and a "contradictions and unknowns" section | Must |
| FR-9 | Every run has a search budget (searches, fetches, agents, tokens, wall time) that is enforced | Must |
| FR-10 | Every run streams events (plan, task started, search issued, document fetched, evidence added, verdict, critique, answer) over SSE | Must |
| FR-11 | Every run is traced in LangSmith with tags and metadata that allow filtering by mode, model, question id, and dataset split | Must |
| FR-12 | The UI runs the same question in both modes side by side and shows the search tree, evidence panel, answer, and cost/latency | Must |
| FR-13 | The UI collects thumbs up/down and an optional comment; feedback is written to LangSmith and appended to a local feedback file | Must |
| FR-14 | SearchBench dataset (≥ 30 questions across CGM and GLP-1, ≥ 3 difficulty tiers, ≥ 4 adversarial) with validated answer keys | Must |
| FR-15 | Evaluators: evidence recall, citation correctness, answer correctness, contradiction handling, search efficiency, latency, token cost | Must |
| FR-16 | `make bench` runs both modes over SearchBench and writes a comparative report | Must |
| FR-17 | GEPA optimizes the decomposition, judge, and critic prompts on a train split and reports on a held-out split | Must |
| FR-18 | Source-quality tiers: primary policy (CMS/MAC/FDA) > official secondary (CMS fact sheets, MLN) > professional (ADA, AACE, specialty societies) > trade press > general web | Must |
| FR-19 | Effective-date extraction and supersession: when two documents cover the same rule, prefer the later effective date and say so | Should |
| FR-20 | Run history: list past runs and re-open them in the UI from persisted JSON | Should |
| FR-21 | A "fast" mode (single agent, budget-capped) alongside "deep" mode | Could |
| FR-22 | CLI parity with the starter agent's streaming console output | Should |

## 8. Non-functional requirements

- Latency: baseline ≤ 20 s; prime deep mode ≤ 3 min on scenario-class questions.
- Cost: prime run ≤ 30 Tavily calls and ≤ 150k tokens by default budget.
- Determinism where possible: temperature 0 for judge/critic/extractor; recorded fixtures for tests.
- Reproducibility: `make bench` on the committed dataset reproduces the report within evaluator noise.
- No PHI. Inputs are policy questions; the system refuses to reason about an individual patient's record.
- Local-only: no data leaves the machine except to Tavily, Nebius, and LangSmith.

## 9. Success metrics

Reported in `reports/final-report.md`, baseline vs PRIME vs PRIME+GEPA:

| Metric | Target (PRIME) |
|---|---|
| Answer correctness (LLM-judge vs answer key, 0–1) | ≥ +0.25 over baseline |
| Evidence recall (required evidence items found) | ≥ 0.75 |
| Citation correctness (cited passage supports the claim) | ≥ 0.85 |
| Contradiction handling (on adversarial subset) | ≥ 0.6, baseline expected ≈ 0 |
| Currency (answers cite the current governing document on change-detection questions) | ≥ 0.8 |
| Search efficiency (correctness / Tavily calls) | reported, not targeted |
| GEPA lift on held-out split | ≥ +0.05 answer correctness, no regression on citation correctness |

## 10. Risks

| Risk | Mitigation |
|---|---|
| Reasoning models on Token Factory may not support native tool calls through the OpenAI-compatible endpoint (a May 2026 issue reported this for Nemotron) | Root uses code-as-action parsed from text, not tool calls; Day-1 smoke test; fallback routing |
| Ground truth drifts; policy state in September 2026 differs from the author's knowledge | Answer keys are built from live Tavily fetches during Day 1 and human-validated; each key records `as_of` and source URLs |
| Tavily/Nebius rate limits during GEPA rollouts | Small train split (15 questions), capped candidate count, cached Tavily responses keyed by query |
| Time | Strict phase gating in `09-implementation-plan.md`; UI polish last; roadmap items not built |
| Evaluator noise | Deterministic evaluators where possible; LLM-judge at temperature 0 with rubric; report variance across 2 runs |

## 11. Open questions

- Whether Tavily Extract returns clean text for CMS coverage database pages (they are JavaScript-heavy). Fallback: search-only mode plus Tavily `include_raw_content`.
- Whether to expose `fast` mode in the UI or CLI only. Default: CLI only.

## 12. Glossary

- **NCD** — National Coverage Determination (CMS, national). **LCD** — Local Coverage Determination (MAC, regional). **Article** — billing and coding companion to an LCD. **MAC** — Medicare Administrative Contractor; DME MACs handle CGM. **HCPCS** — procedure/supply codes. **Part B** — covers DME such as CGM. **Part D** — covers outpatient drugs such as GLP-1s. **RLM** — recursive language model: an agent that manipulates information programmatically and delegates to sub-agents. **GEPA** — Genetic-Pareto prompt optimizer that uses textual feedback from evaluation.

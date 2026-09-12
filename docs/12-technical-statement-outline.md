# 12 — Technical Statement Outline

Target: ≤ 2 pages, written on Day 3 from the final report. File: `TECHNICAL_STATEMENT.md` at repo
root. Tone: direct, engineering-first, one figure and one table.

## Title
PRIME Search: turning a search call into an investigation — coverage-determination research on
Tavily, LangGraph, and Nebius Token Factory

## 1. The problem I chose (¼ page)
- Coverage questions (CGM, GLP-1 under Medicare) look like one search and are not: LCD vs article,
  effective dates, superseded criteria, secondary sources overstating coverage, 2023–2026 changes.
- Who cares: payer UM teams, provider prior-auth staff, DME/pharmacy analysts. What goes wrong today.
- Why it is a good test for a search agent: public, verifiable, time-sensitive, contradiction-rich.

## 2. What I built (½ page)
- One-paragraph architecture: Tavily as retrieval layer; LangGraph root investigator using
  code-as-action over a workspace; parallel search sub-agents producing evidence objects with
  verbatim passages, locations, and dates; evidence judge; critic; synthesis with claim-level
  citations and explicit contradictions/unknowns; budget.
- Figure: the graph (from 03 §1) with one real run's tree.
- The three improvements in assignment terms: retrieval quality (decomposition + primary-source
  targeting), source handling and citations (evidence objects), evaluation loop (SearchBench +
  evaluators + GEPA) — plus observability (LangSmith tags/feedback) and context engineering (documents
  stay in workspace variables, not context).

## 3. How I know it is better (½ page)
- Table: baseline vs PRIME vs PRIME+GEPA on holdout — answer correctness, evidence recall, citation
  correctness, currency, contradiction handling, search cost, latency.
- One before/after example (contradiction question), 6–8 lines each.
- Honest notes: what GEPA did and did not improve; evaluator noise; cost.

## 4. Decisions worth explaining (¼ page)
- Code-as-action for the root (reasoning models and tool calls on the endpoint).
- Evidence unit as the primary object, not the document.
- Answer keys built from live sources with `as_of` — and what the validation step caught.
- What I deliberately did not build (memory, skills, RL) and why; roadmap link.

## 5. How this maps to an FDE engagement (¼ page)
- The pattern is a reference architecture: Tavily under an evidence-graph agent, with a benchmark
  the customer owns. Swap the strategy card and the source tiers, keep everything else.
- Next customer step: commercial payers (roadmap R4), customer-validated SearchBench, security
  layer on fetched content.

## Appendix (links)
- Repo, docs index, LangSmith experiments, build log, final report.

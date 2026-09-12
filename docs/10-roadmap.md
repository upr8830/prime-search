# 10 — Roadmap: designed, not built

This delivery implements the MVP tier of PRIME Search plus GEPA prompt optimization. The proposal's
remaining layers are described here so the architecture's direction is visible and so nobody builds
them by accident in the 3-day window.

## R1. Search memory (proposal §15)

Three memories, all keyed by the same trace data the system already records.

- **Episodic** — per-run record of (question type, plan, tasks, verdicts, score). Storage: the
  existing `runs/` + LangSmith. What is missing: retrieval of similar past runs at plan time
  (embedding over `normalized_question` + `question_type`) and a "here is what worked last time"
  block in `plan.md`.
- **Semantic** — durable facts about sources: "the coding article, not the LCD, holds HCPCS codes";
  "CMS coverage-database pages state revision dates under `Revision Effective Date`". Today these
  are hand-written in the strategy card inside `plan.md`. Roadmap: a `knowledge/` store the critic
  can append to, gated by human review.
- **Procedural** — reusable search strategies (see R2).

Interface sketch: `memory.recall(understanding) -> MemoryBundle` injected into `plan.md`;
`memory.record(run_record, scores)` called by the bench runner.

## R2. Learned skill library (proposal §14)

A successful trajectory becomes a named skill:

```yaml
skill: cms_lcd_criteria_lookup
applies_to: {domain: cgm, question_type: eligibility}
steps:
  - search cms.gov coverage database for the LCD by title
  - fetch LCD; extract revision date and coverage criteria section
  - fetch companion article; extract codes and documentation requirements
  - search time_range=year for revisions or proposed LCD changes
  - reconcile; cite LCD for criteria, article for codes
evidence_of_success: {runs: [...], mean_score: 0.87}
```

Mining: cluster high-scoring runs by `(domain, question_type)`, summarize their plans with the critic
model into a skill draft, human-approve, store in `skills/`. Use: `plan.md` receives the matching
skill as a suggested branch structure. Continual Harness-style refinement (targeted, evidence-backed
edits with rollback) is the natural mechanism; GEPA already provides the evaluation-driven edit loop
for prompts, and skills are prompts with structure.

## R3. Contradiction and supersession with embeddings

Replace the Jaccard claim-merge with embedding similarity (`Qwen3-Embedding-8B` on Token Factory)
and add cross-branch contradiction detection. Add a "supersession chain" view in the UI.

## R4. Commercial payers and multi-jurisdiction MACs

Add a payer taxonomy to `sources.py` (Aetna CPB, UHC medical policy, Cigna coverage policy, Anthem),
a per-payer strategy card, and SearchBench v1 with payer-comparison questions ("how do Aetna and
UHC criteria for CGM differ from Medicare?"). This is the first real customer workflow beyond the
demo and the natural FDE engagement.

## R5. Fast/standard/deep as a product surface

Expose depth as a first-class parameter with cost/latency targets (proposal §12), and add a router
that predicts required depth from `QueryUnderstanding` and past episodic data.

## R6. Human-signal analysis

Analyze `ui-events.jsonl` + feedback: which evidence users open, which claims they flag, where
they re-run with rephrasing. Feed into evaluator weights and skill mining. The transcript's
"combine human behavior with agent traces" idea, made concrete.

## R7. Phase II — RL-trained search policy (proposal §18)

Store trajectories `(question → plan → queries → fetches → evidence → answer → reward)` from bench and
production; define reward as the composite score minus cost; train a search-specialized policy with
an agentic RL framework on Token Factory fine-tuning (Nemotron / Qwen open weights). Two loops:
fast (GEPA/harness) and slow (weights). Requires SearchBench at 300+ questions and a verifier that is
mostly deterministic.

## R8. Security and enterprise

Tavily's PII/prompt-injection protections on fetched content; allow-list enforcement per customer;
audit export of the evidence graph per determination; retention policy for `runs/`.

## Sequencing

R1 → R2 (they share the trace data) → R4 (customer value) → R3 → R6 → R5 → R7 → R8 as needed by
customer engagement. R7 only after R2 shows that policy improvements are measurable.

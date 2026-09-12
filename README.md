# PRIME Search — planning package

This folder is the planning output for the Tavily (Nebius) Head of FDE take-home. It contains the
specs Claude Code builds from, not the implementation.

Start with `CLAUDE.md`, then `docs/09-implementation-plan.md`.

| File | Purpose |
|---|---|
| `CLAUDE.md` | Build conventions, constraints, model routing, doc index |
| `docs/00-prd.md` | Product requirements: problem, personas, scenarios, FRs, metrics |
| `docs/01-system-architecture.md` | Components, config, verified model IDs and fallback rule, Tavily usage |
| `docs/02-data-flow.md` | Pydantic schemas at every stage; SSE event contract; persistence |
| `docs/03-agent-architecture.md` | LangGraph graph, node-by-node design, code-as-action root, prompts |
| `docs/04-evidence-model.md` | Source tiers, document metadata, evidence rules, claim graph, citations |
| `docs/05-evaluation-loop.md` | SearchBench, evaluators, bench runner, feedback loop, GEPA |
| `docs/06-observability.md` | LangSmith tags/feedback, local events, debugging playbook |
| `docs/07-ui-spec.md` | Next.js harness: routes, compare view, components, API |
| `docs/08-synthetic-data-spec.md` | Dataset construction and validation process |
| `docs/09-implementation-plan.md` | 3-day plan with gates and cut list |
| `docs/10-roadmap.md` | Memory, skills, RL, commercial payers — designed, not built |
| `docs/11-assumptions-and-approach.md` | Assumptions, approach, risks, decision log (living) |
| `docs/12-technical-statement-outline.md` | Outline for the ≤ 2-page statement |
| `docs/13-claude-code-practices.md` | How Claude Code best practices are applied (skills, hooks, review) |
| `.claude/` | Claude Code settings, guard hooks, `/gate` `/spec-review` `/session-end` `/validate-bench` skills, spec-reviewer subagent |
| `KICKOFF_PROMPT.md` | First message to Claude Code |
| `OPERATOR_GUIDE.md` | Step-by-step for the person running the build |
| `data/searchbench/` | 30 draft questions with answer keys + validation README |

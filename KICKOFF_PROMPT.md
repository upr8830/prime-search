# Claude Code kickoff prompt — PRIME Search

Copy everything below the line into Claude Code as the first message of the build. Before sending:
put the `prime-search/` planning folder at the repo root (so `CLAUDE.md`, `docs/`, and
`data/searchbench/` exist), create `.env` with `TAVILY_API_KEY`, `NEBIUS_API_KEY`,
`LANGSMITH_API_KEY`, and keep `starter_agent.py` **outside** the repo (e.g. `~/tavily/starter_agent.py`).

---

You are building **PRIME Search**, my submission for the Tavily (Nebius) Head of Forward Deployed
Engineering take-home. The assignment: meaningfully improve a starter Tavily + LangChain search agent
in a way that creates clear business and technical value, and deliver a GitHub repo, a brief
technical statement, and a record of how it was built.

The full plan already exists in this repo. Your job is to execute it, not redesign it.

## Read first, in this order

1. `CLAUDE.md` — constraints, conventions, model routing, doc index. Everything in it is binding.
2. `docs/09-implementation-plan.md` — the 3-day task list with gates and the cut list.
3. `docs/11-assumptions-and-approach.md` — assumptions, risks, and the decision log you must append to.
4. The spec for whatever task you are on, before writing code for it.

Reference material outside the repo: the starter agent is at `~/tavily/starter_agent.py`. Read it
once so `prime_search/baseline.py` reproduces it exactly (same model `moonshotai/Kimi-K2.6`, same
three-line system prompt, one `TavilySearch` tool, same streaming). **Never copy the file into the
repo and never commit it.**

## Non-negotiables

- Stack: LangChain/LangGraph, LangSmith, `langchain-tavily`, `langchain-nebius`. No other LLM or
  search providers. Python 3.11+ with `uv`; Next.js 15 with `pnpm`.
- The root RLM and critic use **code-as-action** (fenced Python / JSON parsed from text), not native
  tool calls — see `docs/03-agent-architecture.md` §3, §7, §12 and `docs/01` §4 for why.
- Evidence objects contain **verbatim passages** validated against the fetched paragraph. No
  evidence from snippets. See `docs/04` §3.
- Every prompt is a Markdown file in `prime_search/prompts/`. Every LLM call goes through
  `prime_search/models.py`. Every Tavily call goes through `prime_search/primitives/`.
- Never run GEPA on the holdout split.
- No PHI, no patient records, not even synthetic ones.
- Do not build anything listed in `docs/10-roadmap.md`.

## How to work with me (Claude Code working rules)

These follow Claude Code's own best-practice guidance; the project config in `.claude/` enforces
part of it.

- **Explore, plan, then code, per phase.** At the start of each numbered task group (1.3, 1.6, 2.2,
  2.5, 3.1 …) switch to plan mode, read the spec sections the task cites, write a short plan (files
  to create, checks to run), show it to me in 5–10 lines, then leave plan mode and implement. For
  one-line tasks skip the plan.
- **Every task ends with a check you can run** — a pytest file, `make smoke`, a `curl`, a bench row,
  a screenshot. Run it, show the real output, iterate until it passes. Do not tell me something works;
  show me the command and its result.
- **Gates.** At every **[G]** in the plan run `/gate <task-id>`. It runs the check, runs an adversarial
  `/spec-review` in a fresh subagent, assembles the evidence, and stops. Wait for my go-ahead.
- **Ask before:** applying a model fallback, deviating from a spec, or spending on GEPA rollouts.
  Everything else, proceed.
- **Use subagents for investigation** (reading many files, library docs, tracing a bug) so the main
  context stays clean. Scope them narrowly.
- **Small commits** with `feat|fix|docs|eval|ui:` messages, at least at the end of every numbered
  task. `.claude/hooks/` will block commits that stage `.env`, `starter_agent.py`, or an API key.
- **Decision log.** Append one dated line to `docs/11-assumptions-and-approach.md` in the same
  commit whenever you deviate, choose between alternatives, or find an assumption wrong.
- **If you cannot verify something** (API behavior, model capability, a policy date) say so and add
  a smoke test or validation note rather than guessing.
- **If you have failed the same fix twice**, stop, summarize the failure and the three most likely
  causes, and propose a different approach before trying again.
- **End every session with `/session-end <day>`**, which writes the build log, checks the decision
  log, commits, pushes, and prints a handoff summary for the next fresh session.
- Each day starts as a **fresh session** (not a continuation): I will paste the handoff summary and
  tell you the day. Re-read `CLAUDE.md`, `docs/09`, and `build-log/day<N-1>.md` before starting.

## The plan

### Day 1 — Retrieval, workspace, agents, CLI

**1.1 Scaffold.** `uv init`; `pyproject.toml` with the dependencies in `docs/01` §7 and the
`prime-search` console script; `Makefile` with `setup smoke dev-api dev-ui ask bench gepa test`;
`.env.example`; `.gitignore` (`.env`, `runs/`, `.cache/`, `node_modules/`, `starter_agent.py`);
`structlog` and `pytest` config; `README.md` stub; `ui/` created with `pnpm create next-app`
(TypeScript, Tailwind, App Router) and left alone until Day 2. Check: `make setup && make test`.

**1.2 Config and models** — `docs/01` §3–4. `config.py` (`Settings`, `ModelRouting`, `Budget`),
`models.py` with one factory per role. Normalize reasoning-model output so callers always get text
in `content`. Write `make smoke` to test, for each role, the exact call shape it uses: root planning
prompt → fenced Python block present; sub-agent → tool call on a search-needing question; judge →
`with_structured_output(Verdict)` returns a valid object; plus one Tavily search, one Tavily extract
on the CGM LCD URL, and one LangSmith trace. **[G]** Smoke passes, or fallbacks are applied per the
rule in `docs/01` §4 and logged in the decision log. Show me the smoke output.

**1.3 Primitives** — `docs/01` §5, `docs/04` §1–2. `primitives/sources.py` (tiers, domain lists),
`primitives/tavily.py` (`search`, `fetch`, on-disk cache keyed by args), `primitives/docmeta.py`
(doc type, external id, effective/revision dates, section headings, paragraph offsets),
`primitives/within.py` (BM25 over paragraphs). Tests: tier classification for ~15 URLs; docmeta on
saved copies of L33822 and A52464 and one FDA label page; paragraph offset round-trip. Check:
`fetch` of L33822 yields external id, a revision date, and ≥ 20 paragraphs. If Tavily Extract returns
poor text for CMS pages, implement the raw-content fallback now and log it.

**1.4 Workspace and schemas** — `docs/02` §2–3, `docs/03` §12. All Pydantic models in
`schemas.py`. `workspace.py` with `Workspace`, helper methods, and `exec()` with restricted builtins
and a per-cell timeout. Tests: sandbox blocks `open`/`__import__`; a plan-constructing cell
round-trips; timeout fires.

**1.5 Evidence store and graph** — `docs/04` §3–5. `evidence/store.py`, `evidence/graph.py`
(claim merge, statuses, contradiction, supersession), `evidence/cite.py`. Tests: contested
detection; supersession by revision date; citation labels with missing fields omitted.

**1.6 Search sub-agent** — `docs/03` §4. Budget-aware tools (`search`, `fetch`, `search_within`,
`add_evidence`, `note_unresolved`), the subgraph, `prompts/search_agent.md`. Check: on the task
"current LCD coverage criteria for therapeutic CGM" the agent fetches L33822 and adds ≥ 3 evidence
items with verbatim passages and dates. Paste the LangSmith trace URL into the build log.

**1.7 Root, graph v0, synthesis, baseline, CLI** — `docs/03` §1–3, §8–9. `agents/root.py` (plan
via code-as-action, structured-output fallback, default-plan fallback), `agents/graph.py` with
`understand → plan → dispatch → search_agent (Send) → collect → synthesize` (judge and critic as
pass-through stubs today), `prompts/understand.md`, `prompts/plan.md` (including the CGM and GLP-1
strategy cards), `prompts/synthesize.md` with post-hoc citation validation. `baseline.py`. `cli.py`
with Rich rendering modeled on the starter. **[G]** `make ask Q="Is a therapeutic CGM covered under
Medicare for a type 2 diabetic not on insulin?"` produces a cited answer with an "Effective dates
relied on" section and a Sources list; `--mode baseline` produces the starter-style answer; both
traced in LangSmith. Show me both answers and both trace URLs.

**1.8 SearchBench sources fetch (start)** — `docs/08` §2 steps 1–2. `eval/searchbench/fetch_sources.py`;
run it; show me the diff summary against the draft keys.

End of day: `/session-end 1`.

### Day 2 — Judge, critic, evaluation, API, UI

**2.1 Validate SearchBench** — this is my task, ~1 hour, driven by `/validate-bench`. It presents
one record at a time with the live-source passages; I give corrections in plain English; you edit the
JSONL and mark records validated only when I say so. Then it syncs to LangSmith. **[G]** 30 records
with `validated_by` set and splits 15/5/10.

**2.2 Judge and critic** — `docs/03` §6–7. `agents/judge.py`, `agents/critic.py`, their prompts,
the conditional edges, round and deadline checks at every node. Check: on `adv-cgm-001` (gestational
diabetes) the run shows a judge round or critic recommendation and the answer's Contradictions
section is non-empty.

**2.3 Evaluators and bench** — `docs/05` §2–3. Deterministic evaluators first, then the LLM-judge
ones with `must`-rubrics and comments. `eval/run_eval.py`, `eval/report.py`. Run baseline and prime
on the dev split; inspect the comments; fix evaluator bugs. **[G]** Dev-split report with every
metric key populated. Show me the table.

**2.4 API** — `docs/01` §2, `docs/02` §4–5, `docs/07` §7. FastAPI endpoints, SSE via
`sse-starlette`, `events.py` (queue + JSONL), run persistence under `runs/<run_id>/`, feedback to
LangSmith and `data/feedback.jsonl`, `/ui-event`. Check with `curl`: start a run, stream events,
fetch the record, post feedback, confirm feedback in LangSmith.

**2.5 UI** — `docs/07`. Generate `ui/src/types.ts` from the OpenAPI schema. Build `useRunEvents`,
the compare view (both panes, search tree, answer with citation hover cards, evidence table, claims,
critic panel, usage footer, feedback), then `/runs`, `/runs/[id]` with the Plan tab showing the
root's plan code, `/docs/[runId]/[docId]`, `/bench`. **[G]** A side-by-side run of a preset
question works end to end in the browser and thumbs-down writes feedback to LangSmith. Show me a
screenshot or describe exactly what renders.

**2.6 [optional]** `prime-search diff`, fast depth in the UI.

End of day: `/session-end 2`. If the machine is free overnight, start `make bench` on holdout for
baseline and prime-base with cache on before closing.

### Day 3 — GEPA, report, statement, packaging

**3.1 GEPA** — `docs/05` §5. `eval/gepa/adapter.py`, `eval/gepa/run_gepa.py`, targeting
`plan.md`, `judge.md`, `critic.md`; train split for optimization, dev for Pareto selection; capped
`max_metric_calls` (~120); reduced per-run budget; Tavily cache on. **Ask me before starting the
run** with the estimated Tavily calls and token cost. Apply the acceptance guardrails; write
`prompts/optimized/` and `reports/gepa-run.json`. If GEPA does not help on holdout, ship base
prompts and report it honestly.

**3.2 Final bench** — holdout × {baseline, prime-base, prime-optimized}, two passes each →
`reports/final-report.md` with headline table, per-tier and per-domain tables, three worked examples
(eligibility, contradiction, out-of-scope), cost/latency; copy the summary JSON for `/bench`.
**[G]** Report exists. Show me the headline table.

**3.3 Technical statement** — `docs/12`. Draft `TECHNICAL_STATEMENT.md` (≤ 2 pages) from the
outline and the report; I will edit it. Include the headline table, one before/after example, and
links to the LangSmith experiments.

**3.4 Packaging.** Complete `README.md` (quickstart, architecture diagram, docs index, debugging
playbook from `docs/06` §6, known limitations). `build-log/README.md` indexing the sessions. Decision
log complete. Commit a few example runs under `runs/examples/` so a reviewer without API keys can
open them in the UI. Fresh-clone test: `make setup && make smoke && make ask`. Confirm
`starter_agent.py` is absent and `.env` is ignored. Tag `v0.1.0`.

**3.5 [optional]** 3–5 minute screen recording of the UI.

## Cut list if behind (in this order)

1. Fast depth in UI · 2. `/bench` page · 3. `prime-search diff` · 4. second holdout pass ·
5. GEPA on `critic.md` (optimize plan + judge only) · 6. paragraph highlighting in document view.

Never cut: baseline parity, verbatim evidence objects, citations, the judge, SearchBench validation,
the bench report, the decision log.

## Start now

Run `/context` to confirm `CLAUDE.md` loaded and `/hooks` to confirm the two guard hooks are active
(if the hook schema in `.claude/settings.json` is out of date for your version, fix it first and
tell me). Then do the reading list in plan mode, give me your Day 1 phase summary, and start task
1.1. If anything in the specs is contradictory or blocked by the environment, tell me before building
around it.

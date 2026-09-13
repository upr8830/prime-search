# PRIME Search

Agentic coverage-determination search. Ask whether a treatment is covered under Medicare and get an
answer built from **primary sources** — CMS coverage determinations (LCD/NCD), CMS articles, FDA
labels — where every claim carries a verbatim passage, the document it came from, and the effective
or revision date that makes it current.

Built for the Tavily (Nebius) Head of Forward Deployed Engineering take-home: an improvement on a
starter Tavily + LangChain search agent, kept in the repo as `--mode baseline` so the two can be
compared side by side on the same question.

> **Status: Day 1 of 3 — in progress.** `make smoke` works; `make ask` lands at task 1.7.
> The full quickstart below is the target interface; see `docs/09-implementation-plan.md` for
> what is actually built.

## Quickstart

```bash
cp .env.example .env     # add TAVILY_API_KEY, NEBIUS_API_KEY, LANGSMITH_API_KEY
make setup               # uv sync --all-groups
make smoke               # verify each model role, Tavily, and LangSmith tracing
make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
```

Prerequisites: [`uv`](https://docs.astral.sh/uv/), GNU `make`, Python 3.11–3.13. The UI additionally
needs Node 20+ and `pnpm`.

## Commands

| Command | What it does |
|---|---|
| `make setup` | Install the Python environment (`uv sync --all-groups`) |
| `make smoke` | Per-role model check, one Tavily search, one Tavily extract, one LangSmith trace |
| `make test` | `pytest tests/ -x -q` — offline; tests needing keys are marked `live` and skipped |
| `make ask Q="…"` | One investigation, cited answer to the console. `ARGS="--mode baseline"`, `ARGS="--depth fast"` |
| `make bench` | Run the SearchBench evaluation. `ARGS="--mode prime --split dev"` |
| `make gepa` | GEPA prompt optimization (train/dev splits only, never holdout) |
| `make dev-api` | FastAPI + SSE on `localhost:8765` (`PRIME_API_PORT`) |
| `make dev-ui` | Next.js harness on `localhost:3000` |

## API

`make dev-api` (or `uv run python -m prime_search.api --reload`) serves the endpoints in
`docs/07-ui-spec.md` §7 on `localhost:8765`, with the schema at `/openapi.json`. Set `PRIME_API_PORT` (and
`PRIME_API_HOST`) in the shell or `.env` to move it. A quick check from Git Bash:

```bash
RUN=$(curl -s -X POST localhost:8765/run -H 'content-type: application/json' \
  -d '{"question":"Does Medicare cover a CGM for a type 2 diabetic not on insulin?","mode":"baseline"}' \
  | uv run python -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
curl -sN localhost:8765/run/$RUN/events     # SSE until run.finished
curl -s localhost:8765/runs/$RUN            # the RunRecord
curl -s -X POST localhost:8765/feedback -H 'content-type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"thumbs\":\"up\",\"comment\":\"clear answer\"}"
```

Feedback reaches LangSmith when tracing is on, and is always appended to `data/feedback.jsonl`, which stays
local.

## UI

The side-by-side harness (`docs/07-ui-spec.md`) runs against the API above:

```bash
uv run python -m prime_search.api          # terminal 1: the API on PRIME_API_PORT (default 8765)
cd ui && pnpm install && pnpm dev          # terminal 2: http://localhost:3000
```

The UI reads `PRIME_API_HOST` / `PRIME_API_PORT` from the shell or the repo-root `.env`, the same variables
the API reads. `/` compares the starter and PRIME on one question; `/runs`, `/runs/<id>`, `/docs/...` and
`/bench` replay past runs and the latest bench report. In `ui/`: `pnpm test` (vitest), `pnpm lint`,
`pnpm exec tsc --noEmit`, and `pnpm gen:types` to regenerate `src/types/api.ts` from a running API.

## How it works

A LangGraph pipeline — `understand → plan → dispatch → search sub-agents → collect → judge →
critic → synthesize` — where the root planner and the critic emit **code-as-action** (fenced Python
and JSON parsed from text) rather than native tool calls, because reasoning models on the Nebius
endpoint may reject tool calls. Retrieval is Tavily search plus Tavily extract, with BM25 over the
paragraphs of fetched documents so evidence can be quoted exactly and validated against the
paragraph it came from. Architecture: `docs/01-system-architecture.md`; agents: `docs/03`.

## Docs index

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
| `.claude/` | Settings, guard hooks, `/gate` `/spec-review` `/session-end` `/validate-bench` skills, spec-reviewer subagent |
| `build-log/` | One file per build session |
| `data/searchbench/` | 30 questions with answer keys + validation README |

## Data and scope

Questions are about **policy**, not patients: no PHI, no patient records, not even synthetic ones.
The benchmark answer keys in `data/searchbench/` start as drafts and are validated against live
primary sources before use (`docs/08`).

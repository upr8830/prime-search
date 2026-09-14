# PRIME Search

Agentic coverage-determination research. Ask whether a service or drug is covered under Medicare and get
an answer built from **primary sources**: CMS coverage determinations (LCD/NCD), CMS articles and FDA
labels. Every claim carries a verbatim passage, the document it came from, and the effective or revision
date that makes it current. The answer names contradictions between sources and says what could not be
verified. It answers at policy level and never decides an individual case.

Built for the Tavily (Nebius) Head of Forward Deployed Engineering take-home, as an improvement on a
starter Tavily + LangChain search agent. The starter is kept in the repo as `--mode baseline`, so the two
can be compared side by side on the same question. The proposed solution is described in
[`TECHNICAL_STATEMENT.md`](TECHNICAL_STATEMENT.md).

> **Status: Day 3.** The investigation pipeline, CLI, API, UI harness, SearchBench evaluators and GEPA
> runner are built. GEPA found no prompt that beat the base prompts on dev (`reports/gepa-run.json`). The
> final holdout bench has run, with results in `reports/final-report.md`. `docs/09-implementation-plan.md` and
> `build-log/` record what is done.

## The proposed solution

**The proposed solution is [`TECHNICAL_STATEMENT.md`](TECHNICAL_STATEMENT.md). Read it first.** It sets out
the problem, the design, the holdout evidence and the decisions behind them. In brief:

- **The problem.** Payer utilization management turns coverage policy into decisions. A decision built on
  wrong or stale research harms the patient who met the criteria, and exposes the payer to appeals,
  overturned denials and improper payments. A single search returns a fluent answer a reviewer cannot
  audit.
- **The solution.** PRIME keeps the starter's stack (Tavily, LangChain and LangGraph, Nebius) and turns
  the search call into an investigation:
  - it plans branches aimed at primary policy;
  - parallel sub-agents record verbatim, dated passages checked against the fetched document;
  - a judge and a critic review the evidence;
  - the answer cites every claim and states effective dates, contradictions and what could not be
    verified.

  It answers at policy level, and the decision stays with the reviewer.
- **The evidence.** On the 10-question holdout, run twice, answer correctness is a tie: 0.66 for PRIME
  against 0.64 for the starter. Only PRIME's answers can be audited:

  | holdout | PRIME | starter |
  |---|---|---|
  | citation correctness | 0.63 | 0.00 |
  | currency (governing document and date) | 0.94 | 0.31 |
  | evidence recall | 0.74 | 0.00 |
  | composite | 0.69 | 0.36 |

  GEPA found no prompt that beat the base prompts, so the base prompts ship. The full results are in
  [`reports/final-report.md`](reports/final-report.md).
- **What comes next.** Raise citation correctness first: about one cited sentence in three is not yet
  supported by its passage.

**Try it without API keys.** [`runs/examples/`](runs/examples/) contains pre-recorded runs of the three
worked-example questions, the starter and PRIME from holdout pass 1. They can be viewed in the UI without
API keys: start the API and the UI (steps 8 and 9 below) and open `/runs`.

Fetched document text is included only for .gov sources such as CMS. Other documents in those runs show
that their text is not stored.

**Check your environment.** With your keys in `.env`, `make setup && make smoke` installs everything and
verifies each model role, Tavily and LangSmith.

---

## Where to start: reading order

Read in this order. Each stage builds on the one before, and you can stop after any stage. Paths are from
the repo root.

**Stage 1: the case**

1. [`TECHNICAL_STATEMENT.md`](TECHNICAL_STATEMENT.md) — the proposed solution: the problem, what was
   built, how we know it is better, and the decisions behind it.
2. [`reports/final-report.md`](reports/final-report.md) — the holdout results behind the statement: the
   headline table, PRD targets, per-question scores and three worked examples, from task 3.2's two holdout
   passes. [`reports/dev-report.md`](reports/dev-report.md) shows the same layout for the 5-question dev check.

**Stage 2: the problem and the approach**

3. [`docs/00-prd.md`](docs/00-prd.md) — who needs this, the scenarios (eligibility, coding, change,
   contradiction, out of scope) and the success metrics.
4. [`docs/11-assumptions-and-approach.md`](docs/11-assumptions-and-approach.md) §1–3 — assumptions, the
   reasoning chain, rejected alternatives and risks. §4, the dated decision log, is a reference: read an
   entry when a later doc points to it.

**Stage 3: how it works**

5. [`docs/01-system-architecture.md`](docs/01-system-architecture.md) — components, configuration, model
   routing and fallbacks, and how Tavily is used. [`reports/model-selection.md`](reports/model-selection.md)
   is the evidence for the model choices.
6. [`docs/03-agent-architecture.md`](docs/03-agent-architecture.md) — the LangGraph graph node by node:
   planning as code, search sub-agents, judge, critic and synthesis.
7. [`docs/04-evidence-model.md`](docs/04-evidence-model.md) — source tiers, how a verbatim passage becomes
   evidence, claims, contradictions and citations. This is the core of "accurate and auditable".
8. [`docs/02-data-flow.md`](docs/02-data-flow.md) — the schemas at every stage and the event stream. Keep
   it open while reading code.

**Stage 4: how it is measured**

9. [`docs/08-synthetic-data-spec.md`](docs/08-synthetic-data-spec.md), then
   [`data/searchbench/README.md`](data/searchbench/README.md) and
   [`reports/searchbench-drift.md`](reports/searchbench-drift.md) — how the 30 questions and answer keys
   were built, checked against live sources and validated.
10. [`docs/05-evaluation-loop.md`](docs/05-evaluation-loop.md) — the evaluators, bench runner, report and
    GEPA, each with its "as built" notes. [`reports/gepa-run.json`](reports/gepa-run.json) is the GEPA
    result.
11. [`docs/06-observability.md`](docs/06-observability.md) — LangSmith tags and feedback, local event
    logs, and the debugging playbook.

**Stage 5: try it**

12. [`docs/07-ui-spec.md`](docs/07-ui-spec.md) — the side-by-side harness. Then follow
    [Build and run it](#build-and-run-it-step-by-step) below and ask a question in the UI.

**Stage 6: how it was built and what comes next**

13. [`docs/09-implementation-plan.md`](docs/09-implementation-plan.md) — the three-day plan, its gates and
    the cut list.
14. [`build-log/`](build-log/) — `day1.md`, `day2.md`, … record each session: gates passed, what live runs
    found that tests did not, and open issues. The `*-transcript.md` files are the raw sessions.
15. [`docs/13-claude-code-practices.md`](docs/13-claude-code-practices.md) and
    [`CLAUDE.md`](CLAUDE.md) — how the build was run with Claude Code: conventions, hooks, spec reviews.
16. [`docs/10-roadmap.md`](docs/10-roadmap.md) — what was designed but deliberately not built: memory,
    skills, RL and commercial payers.

[`docs/12-technical-statement-outline.md`](docs/12-technical-statement-outline.md) is the outline the
statement was written from; read it only to compare the two.

**Shorter paths:**

| Role | Read |
|---|---|
| Reviewer | 1, 2, 7, 10, then run the UI (12) |
| Payer or policy stakeholder | 1, 3, 7, 9 |
| Engineer building on it | 1, 5–8, 10, 11, then `CLAUDE.md` before changing code |

---

## Build and run it, step by step

### 1. Install the prerequisites

| Tool | Version | Used for |
|---|---|---|
| [`uv`](https://docs.astral.sh/uv/) | current | Python environment and every `uv run` command |
| Python | 3.11–3.13 | installed by `uv` if missing |
| GNU `make` | any | the task runner (optional: every target is a one-line `uv run ...` shown below) |
| Node.js | 20+ | the UI harness only |
| [`pnpm`](https://pnpm.io/installation) | current | the UI harness only |
| Git | any | cloning; on Windows, Git Bash is the shell these commands assume |

On **Windows**: install GNU `make` (for example through winget), or use the `uv run` commands directly.
Open a new terminal after installing, so `make` is on `PATH`.

### 2. Get API keys

| Key | Where | Required |
|---|---|---|
| `TAVILY_API_KEY` | <https://app.tavily.com> (starts with `tvly-`) | yes |
| `NEBIUS_API_KEY` | <https://studio.nebius.com>, Token Factory API key | yes |
| `LANGSMITH_API_KEY` | <https://smith.langchain.com> (starts with `lsv2_`) | for traces, the bench and feedback |

Without keys you can still run the offline test suite (step 5) and browse the UI's replay pages.

### 3. Clone and configure

```bash
git clone https://github.com/upr8830/prime-search.git
cd prime-search
cp .env.example .env        # then fill in the three keys
```

`.env` is git-ignored, and the repo's hooks refuse a commit that stages it. Settings read `.env` from the
repo root, so run every command from there. Optional overrides (model routing, budgets, API port, Tavily
cache) are documented in `.env.example`. Leave the model routing commented out unless you mean to change
it.

### 4. Install

```bash
make setup                  # = uv sync --all-groups   (runtime, dev and the gepa group)
```

### 5. Check the build offline

```bash
make test                   # = uv run pytest tests/ -x -q   (tests needing keys are marked live and skipped)
uv run ruff check prime_search/ eval/ tests/
```

### 6. Check the keys and models

```bash
make smoke                  # = uv run prime-search smoke
```

Smoke probes each model role with the call shape it uses in production, then runs one Tavily search, one
Tavily extract on the CGM LCD, and one LangSmith trace. Each role prints `PASS`, or `FALLBACK` with the
model it would switch to. A fallback is a finding, not a fix. Apply one only by setting
`PRIME_MODELS__<ROLE>` deliberately and noting it in `docs/11`.

### 7. Ask a question from the command line

```bash
make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
make ask Q="..." ARGS="--mode baseline"     # the starter agent, for comparison
make ask Q="..." ARGS="--depth fast"        # smaller budget, no critic
```

A deep run takes about 3 minutes and 300–500k tokens. The investigation streams to the console:
understanding, plan, branches, judge rounds, critic, then the cited answer. Every run is saved under
`runs/<run_id>/` (`state.json`, `events.jsonl`, fetched document text) and traced to LangSmith.

### 8. Start the API

```bash
make dev-api                # = uv run python -m prime_search.api --reload   → http://127.0.0.1:8765
```

The port is `PRIME_API_PORT`, default 8765. Port 8000 is often held by Windows HTTP.sys. The endpoints are
in `docs/07-ui-spec.md` §7, and the schema is at `/openapi.json`. A quick check from Git Bash:

```bash
RUN=$(curl -s -X POST localhost:8765/run -H 'content-type: application/json' \
  -d '{"question":"Does Medicare cover a CGM for a type 2 diabetic not on insulin?","mode":"baseline"}' \
  | uv run python -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
curl -sN localhost:8765/run/$RUN/events     # SSE until run.finished
curl -s localhost:8765/runs/$RUN            # the RunRecord
curl -s -X POST localhost:8765/feedback -H 'content-type: application/json' \
  -d "{\"run_id\":\"$RUN\",\"thumbs\":\"up\",\"comment\":\"clear answer\"}"
```

Feedback reaches LangSmith when tracing is on, and is always appended to `data/feedback.jsonl`, which
stays local.

### 9. Start the UI harness

In a second terminal, with the API running:

```bash
cd ui
pnpm install                # first time only
pnpm dev                    # = make dev-ui   → http://localhost:3000
```

| Page | What it shows |
|---|---|
| `/` | The starter and PRIME side by side on one question: live search tree, answer, evidence, claims, critic, plan |
| `/runs`, `/runs/<id>` | Past runs, replayed from their event logs |
| `/docs/<run>/<doc>` | A fetched document, with the cited paragraph highlighted |
| `/bench` | The latest bench report (`reports/latest.json`) |

The UI reads `PRIME_API_HOST` and `PRIME_API_PORT` from the shell or the repo-root `.env`, the same variables
as the API. In `ui/`, run `pnpm test` (vitest), `pnpm lint` and `pnpm exec tsc --noEmit`. Run
`pnpm gen:types` against a running API to regenerate `src/types/api.ts`. Run `pnpm build` only with the dev
server stopped, because they share `.next`.

### 10. Run the benchmark (SearchBench)

SearchBench is 30 policy questions (`data/searchbench/searchbench_v0.jsonl`), split into train (15), dev
(5) and holdout (10). Every answer key has been validated by a person against live primary sources. The
runner refuses to score keys nobody validated, or a LangSmith dataset that differs from the committed file.

```bash
# a. validate the keys offline, then push the dataset to LangSmith (first time, or after editing keys)
uv run python -m eval.searchbench.sync --check
uv run python -m eval.searchbench.sync

# b. see the plan and estimate without spending anything
make bench ARGS="--mode prime --split dev --dry-run"

# c. dev check (5 questions: a build-time check, not a result)
make bench ARGS="--mode baseline --split dev"
make bench ARGS="--mode prime --split dev --prompt-set base --concurrency 3"
uv run python -m eval.report --split dev                  # → reports/dev-report.md

# d. final holdout bench: two passes per configuration
make bench ARGS="--mode baseline --split holdout --concurrency 3"      # pass 1
make bench ARGS="--mode baseline --split holdout --concurrency 3"      # pass 2
make bench ARGS="--mode prime --split holdout --prompt-set base --concurrency 3"   # pass 1
make bench ARGS="--mode prime --split holdout --prompt-set base --concurrency 3"   # pass 2
uv run python -m eval.report --split holdout --passes 2   # → reports/final-report.md, reports/latest.json
```

Each `make bench` is one LangSmith experiment (project `prime-search-bench`), written to
`reports/bench/<experiment>.json`. `eval.report` reads only those files, so it costs nothing to rerun.
`--rescore reports/bench/<file>.json` re-scores saved runs with the current evaluators and spends judge calls
only.

**Cost guide**, from measured runs: a PRIME deep question is about $0.60–0.95 including scoring (answer
correctness uses three judge calls). The run itself takes about 3–4 minutes (194 s mean on holdout) and
scoring adds 1–2 minutes. A baseline question is about $0.10. A holdout pass
of PRIME is therefore about $8–10. The Tavily cache (`PRIME_TAVILY_CACHE`, on by default) makes reruns
cheaper and comparable.

---

## Run another GEPA optimization

GEPA (`eval/gepa/`, docs/05 §5) rewrites the prompts that decide what gets searched and when to stop:
`plan.md`, `judge.md`, and `critic.md` if you ask for it. It runs the real PRIME graph on SearchBench
**train** questions, uses the evaluators' comments as feedback, and selects candidates on **dev**.
The **holdout split is never used**: the runner refuses any split but train, and the adapter refuses
holdout records. Prompts it writes are only a proposal until they pass the holdout acceptance check in
step 6.

### 1. Preconditions

- Steps 1–6 above pass, and `uv run python -m eval.searchbench.sync --check` is clean.
- The Tavily cache is on (the default). The runner refuses to start without it.
- Keep the previous result. The runner overwrites `reports/gepa-run.json`, so copy it first if it is
  uncommitted:
  ```bash
  cp reports/gepa-run.json reports/gepa-run.$(date +%Y%m%d-%H%M).json
  ```

### 2. Dry run: plan and cost, no spend

```bash
make gepa ARGS="--dry-run"
```

It prints the components, split sizes, per-run budget (deep, 20 searches, 4 agents per round), the Tavily
cache state, the estimated cost and time, and how far the last iteration can run past the cap.

### 3. Choose the size of the run

| Option | Default | Meaning |
|---|---|---|
| `--components` | `plan,judge` | prompts to optimize, from `plan`, `judge` and `critic` |
| `--max-metric-calls` | `10` | the budget in scored deep runs; the last iteration can finish past it |
| `--minibatch` | `3` | train questions per reflection step |
| `--concurrency` | `3` | runs at a time |
| `--seed` | `0` | GEPA's sampling seed |
| `--run-dir` | `runs/gepa/<timestamp>` | checkpoint directory; pass an existing one to resume |

How far a budget goes:
- **10 metric calls (the default):** the base prompts' dev evaluation takes 5 and one proposal takes 6
  (3 parent and 3 child train runs), so about one proposal.
- **60:** several proposals, about $36–57 plus overshoot.
- **120 on all three prompts (docs/05 §5's original configuration):** about $75–130 and 3–4 h.

Run `--dry-run` with the same options first to see the estimate.

### 4. Run it

```bash
make gepa                                                         # defaults: plan + judge, 10 metric calls
make gepa ARGS="--max-metric-calls 60"                            # a longer search
make gepa ARGS="--components plan,judge,critic --max-metric-calls 120"
```

Or, without `make`: `uv run python -m eval.gepa.run_gepa [options]`. Progress prints to the console and to
`runs/gepa/<timestamp>/run_log.txt` (UTF-8). Every rollout is traced in the LangSmith project
`prime-search-gepa` with the tags `source:gepa`, `gepa:<split>` and `candidate:gepa-<sha>`.

If it stops partway (a crash, or Ctrl+C), resume from the checkpoint. Paid runs are not repeated:

```bash
make gepa ARGS="--run-dir runs/gepa/<timestamp>"
```

To resume with more budget, pass a higher `--max-metric-calls`. The count includes calls already spent.

### 5. Read the result

`reports/gepa-run.json` contains:
- `seed_dev_score` and `best_dev_score`, and `improved_on_dev`;
- `candidates`: each one's parent, dev scores per question, the metric call that found it, the prompts
  it changed, and a unified diff against base;
- `pareto_front`: the best candidate per dev question;
- `rollouts`: every paid run's id, question, status and score (open `runs/<run_id>/state.json` for the
  full record);
- `optimized_prompts_written`.

**When no candidate beats the base prompts on dev**, nothing is written to `prime_search/prompts/optimized/`
and the base prompts stay in use. Report that as a negative result, as docs/05 §5 requires.

**When a candidate beats base on dev**, the runner writes `prime_search/prompts/optimized/<prompt>.md`
for each prompt it changed. Any other prompt falls back to base, and an older file for an unchanged prompt
is removed. Try the new prompts before the acceptance check:

```bash
make ask Q="..." ARGS="--prompt-set optimized"
```

### 6. Acceptance on holdout (docs/05 §5)

Optimized prompts ship only if, on holdout, **answer correctness improves** and **citation correctness
drops by no more than 0.03**. Run the optimized configuration twice, next to the existing baseline and base
passes, then regenerate the report:

```bash
make bench ARGS="--mode prime --split holdout --prompt-set optimized --concurrency 3"   # pass 1
make bench ARGS="--mode prime --split holdout --prompt-set optimized --concurrency 3"   # pass 2
uv run python -m eval.report --split holdout --passes 2
```

The report's **PRIME + GEPA** section shows the optimized configuration's answer and citation correctness
deltas against base, and whether the check passed. The PRD targets table adds the `gepa_lift` row (target
+0.05).

- **Accepted:** commit `prime_search/prompts/optimized/`, `reports/gepa-run.json`, the new bench files and
  the report, and add a dated line to the `docs/11` decision log.
- **Not accepted:** delete `prime_search/prompts/optimized/*.md` so the base prompts ship. Commit
  `reports/gepa-run.json` and the report with the negative result, and log it in `docs/11`.

Never optimize on holdout, and never tune prompts by hand against holdout results: either one invalidates
the holdout comparison.

---

## Commands

| Command | What it does |
|---|---|
| `make setup` | Install the Python environment (`uv sync --all-groups`) |
| `make test` | Offline tests (`pytest tests/ -x -q`); tests marked `live` are skipped |
| `make smoke` | Per-role model check, one Tavily search, one Tavily extract, one LangSmith trace |
| `make ask Q="…"` | One investigation, cited answer to the console. `ARGS="--mode baseline"`, `"--depth fast"`, `"--prompt-set optimized"` |
| `make bench ARGS="…"` | One SearchBench experiment: `--mode`, `--split`, `--prompt-set`, `--concurrency`, `--ids`, `--dry-run`, `--rescore FILE` |
| `make gepa ARGS="…"` | GEPA prompt optimization on train and dev: `--dry-run`, `--components`, `--max-metric-calls`, `--run-dir` |
| `make dev-api` | FastAPI + SSE on `127.0.0.1:8765` (`PRIME_API_PORT`) |
| `make dev-ui` | Next.js harness on `localhost:3000` |
| `uv run python -m eval.report --split holdout --passes 2` | Final report from the saved bench files |
| `uv run python -m eval.searchbench.sync [--check]` | Validate SearchBench, or push it to LangSmith |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `make: command not found` right after installing it | Open a new terminal so `PATH` refreshes, or run the `uv run` command in the recipe |
| The API will not bind to port 8000 | Windows HTTP.sys holds it. The API defaults to 8765 (`PRIME_API_PORT`) |
| `refusing to run: LangSmith searchbench-v0 differs from the jsonl` | Run `uv run python -m eval.searchbench.sync` after editing answer keys |
| `refusing to run: unvalidated keys [...]` | A key lacks `validated_by`. Validate it (`docs/08` §2) before scoring |
| A smoke role prints `FALLBACK` | That model failed its production call shape. Decide on the fallback and log it in `docs/11` |
| `UnicodeEncodeError: 'charmap'` in a long run on Windows | Fixed in the bench and GEPA runners. For other scripts, set `PYTHONIOENCODING=utf-8` |
| A run finished over its token budget | Tokens are checked between steps, so a run can finish over the cap. The UI shows "Research limit reached" |
| Pass `ARGS` with spaces | Quote the whole value: `make bench ARGS="--mode prime --split dev"` |

## How it works

A LangGraph pipeline: `understand → plan → dispatch → search sub-agents → collect → judge → critic →
synthesize`. The root planner and the critic emit **code-as-action** (fenced Python and JSON parsed from
text) rather than native tool calls, because reasoning models on the Nebius endpoint may reject tool
calls. Retrieval is Tavily search plus Tavily extract, with BM25 over the paragraphs of fetched documents,
so evidence can be quoted exactly and validated against the paragraph it came from. The architecture is in
`docs/01-system-architecture.md`, and the agents in `docs/03`.

Model routing (defaults in `prime_search/config.py`):

| Role | Model |
|---|---|
| Root planner and critic | `nvidia/nemotron-3-super-120b-a12b` |
| Judge | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| Sub-agents, extractor and evaluators | `moonshotai/Kimi-K2.6` |
| Baseline (the starter's model) | `moonshotai/Kimi-K2.6` |

## Docs index

| File | Purpose |
|---|---|
| `TECHNICAL_STATEMENT.md` | The proposed solution: problem, design, holdout results and decisions |
| `CLAUDE.md` | Build conventions, constraints, model routing |
| `docs/00-prd.md` | Product requirements: problem, personas, scenarios, FRs, metrics |
| `docs/01-system-architecture.md` | Components, config, verified model IDs and fallback rule, Tavily usage |
| `docs/02-data-flow.md` | Pydantic schemas at every stage; SSE event contract; persistence |
| `docs/03-agent-architecture.md` | LangGraph graph, node-by-node design, code-as-action root, prompts |
| `docs/04-evidence-model.md` | Source tiers, document metadata, evidence rules, claim graph, citations |
| `docs/05-evaluation-loop.md` | SearchBench, evaluators, bench runner, report, GEPA |
| `docs/06-observability.md` | LangSmith tags and feedback, local events, debugging playbook |
| `docs/07-ui-spec.md` | Next.js harness: routes, compare view, components, API |
| `docs/08-synthetic-data-spec.md` | Dataset construction and validation process |
| `docs/09-implementation-plan.md` | 3-day plan with gates and cut list |
| `docs/10-roadmap.md` | Memory, skills, RL, commercial payers: designed, not built |
| `docs/11-assumptions-and-approach.md` | Assumptions, approach, risks, decision log (living) |
| `docs/12-technical-statement-outline.md` | Outline for the technical statement |
| `docs/13-claude-code-practices.md` | How Claude Code best practices are applied (skills, hooks, review) |
| `.claude/` | Settings, guard hooks, `/gate` `/spec-review` `/session-end` `/validate-bench` skills, spec-reviewer subagent |
| `build-log/` | One file per build session, plus session transcripts |
| `data/searchbench/` | 30 questions with validated answer keys, plus the validation README |
| `reports/` | Bench files, dev and final reports, GEPA run, model selection |

## Data and scope

Questions are about **policy**, not patients: no PHI and no patient records, not even synthetic ones. The
benchmark answer keys in `data/searchbench/` started as drafts. They were validated against live primary
sources before use (`docs/08`, `reports/searchbench-drift.md`). PRIME supports a reviewer's research. A
coverage decision for an individual stays with the plan and the clinician.

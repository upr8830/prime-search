# 09 — Implementation Plan (3 days)

Each task has a spec reference and an acceptance check. Do tasks in order within a day; phases gate
each other. If a day runs long, cut from the bottom of that day, not from the next day's gate.

Legend: **[G]** = gate (must pass before the next phase), **[opt]** = cut first if behind.

## Day 1 — Retrieval, workspace, agents, CLI

### 1.1 Scaffold
- `uv init`, `pyproject.toml` with deps (01 §7), `Makefile`, `.env.example`, `README.md` stub,
  `structlog` config, `pytest` config. `ui/` created with `pnpm create next-app` (TypeScript,
  Tailwind, App Router) but left as a placeholder until Day 2.
- Check: `make setup && make test` runs (0 tests OK).

### 1.2 Config and models — 01 §3–4
- `config.py` (`Settings`, `ModelRouting`, `Budget`), `models.py` with `root_model()`,
  `subagent_model()`, `judge_model()`, `extractor_model()`, `evaluator_model()`, `baseline_model()`.
  Normalize `reasoning_content` → `content` when `content` is empty.
- `make smoke`: for each role, the exact call shape (01 §4 fallback rule) plus Tavily search +
  extract on one CMS URL plus LangSmith trace creation.
- **[G]** Smoke passes or fallbacks are applied and logged in `11` → Decision log.

### 1.3 Primitives — 01 §5, 04 §1–2
- `primitives/sources.py` tiers and domain lists; `primitives/tavily.py` (`search`, `fetch`,
  cache); `primitives/docmeta.py` (doc type, external id, dates, sections, paragraphs);
  `primitives/within.py` (BM25 over paragraphs).
- Tests: tier classification for 15 URLs; docmeta on two saved CMS pages (LCD + article) and one
  FDA label page; paragraph offsets round-trip.
- Check: `fetch` of the CGM LCD returns external id `L33822`, a revision date, and section headings.
  If Extract fails on CMS pages, implement the raw-content fallback (01 §5) now.

### 1.4 Workspace and schemas — 02 §2–3, 03 §12
- `schemas.py` complete. `workspace.py` with `Workspace`, helpers, `exec()` sandbox with restricted
  builtins and timeout.
- Tests: sandbox blocks `open`/`__import__`; a plan-constructing cell round-trips; timeout fires.

### 1.5 Evidence store and graph — 04 §3–5
- `evidence/store.py`, `evidence/graph.py` (claim merge, statuses, contradiction, supersession),
  `evidence/cite.py`.
- Tests: contested detection; supersession by revision date; citation label building with missing
  fields.

### 1.6 Search sub-agent — 03 §4
- Tools with budget accounting; `search_agent.py` subgraph; `prompts/search_agent.md`.
- Check: on task "current LCD coverage criteria for therapeutic CGM" the agent fetches L33822 and
  adds ≥ 3 evidence items with verbatim passages and dates. Record the trace URL in the build log.

### 1.7 Root plan node, graph assembly, synthesis (v0) — 03 §1–3, §8
- `agents/root.py` (plan via code-as-action with structured fallback), `agents/graph.py` with
  `understand → plan → dispatch → search_agent → collect → synthesize` (judge/critic stubbed as
  pass-through today), `prompts/understand.md`, `prompts/plan.md`, `prompts/synthesize.md`.
- `baseline.py` with the starter's exact configuration.
- `cli.py`: `prime-search ask "..." --mode prime|baseline --depth deep|fast` with Rich rendering
  modeled on the starter (tool calls, streaming answer, trace URL).
- **[G]** `make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"`
  produces a cited answer with an Effective dates section and a Sources list; the baseline produces
  its answer; both traced.

### 1.8 SearchBench sources fetch — 08 §2 steps 1–2 [start; finish Day 2 morning]
- `eval/searchbench/fetch_sources.py`; run it; review the diff summary.

### End of day
- Export session to `build-log/day1.md`. Update decision log. Commit.

## Day 2 — Judge, critic, evaluation, API, UI

### 2.1 Validate SearchBench — 08 §2 step 3 (human, ~1 h)
- Author validates keys; sets `as_of`, `validated_by`. `sync.py` pushes to LangSmith.
- **[G]** 30 records validated; splits assigned.

### 2.2 Judge and critic — 03 §6–7, 02 §2.6
- `agents/judge.py`, `agents/critic.py`, `prompts/judge.md`, `prompts/critic.md`; wire the
  conditional edges and rounds; budget/deadline checks at every node.
- Check: on the gestational-diabetes contradiction question, the run shows a judge round or a critic
  recommendation and the answer's Contradictions section is non-empty.

### 2.3 Evaluators and bench — 05 §2–3
- `eval/evaluators.py` (deterministic first, then LLM-judge with rubric + comments),
  `eval/run_eval.py`, `eval/report.py`.
- Run `--mode baseline --split dev` and `--mode prime --split dev`; inspect comments; fix obvious
  evaluator bugs.
- **[G]** Dev-split report generated with all metric keys populated.

### 2.4 API — 01 §2, 02 §4–5, 07 §7
- `api/main.py`: all endpoints; `events.py` with SSE queue + JSONL; run persistence; feedback to
  LangSmith + file; `/ui-event`.
- Check: `curl` a run, stream its events, fetch its record, post feedback (verify in LangSmith).

### 2.5 UI — 07
- Types from OpenAPI; `useRunEvents`; compare view with both panes; search tree; answer with
  citation hover; evidence table; claims; critic; usage footer; feedback.
- Then `/runs`, `/runs/[id]` (with Plan tab), `/docs/...`, `/bench`.
- **[G]** Side-by-side run of a preset question works end to end in the browser; thumbs write to
  LangSmith.

### 2.6 [opt] `prime-search diff`, fast depth in UI.

### End of day
- Export `build-log/day2.md`. Decision log. Commit. Run `make bench` on holdout for baseline and
  prime-base overnight if the machine is available (cache on).

## Day 3 — GEPA, report, statement, packaging

### 3.1 GEPA — 05 §5
- `eval/gepa/adapter.py`, `run_gepa.py`; run on train/dev with the capped budget and 10 metric calls
  (~30–60 min wall time; work on 3.3 in parallel).
- Apply acceptance guardrails; write `prompts/optimized/` and `reports/gepa-run.json`.

### 3.2 Final bench — 05 §3
- Holdout × {baseline, prime-base, prime-optimized}, two passes each; `eval/report.py` →
  `reports/final-report.md`; copy summary JSON for `/bench`.
- **[G]** Report exists with the headline table and three worked examples.

### 3.3 Technical statement — 12
- Write `TECHNICAL_STATEMENT.md` (≤ 2 pages) from the outline; include the headline table and one
  before/after example; link to LangSmith experiments (public sharing links if allowed, else
  screenshots in `reports/`).

### 3.4 Packaging
- `README.md` complete (quickstart, architecture diagram, docs index, debugging playbook, known
  limitations). `build-log/` complete with an index. `docs/11` decision log complete.
- Verify `starter_agent.py` is absent and `.env` ignored. Fresh-clone test: `make setup && make smoke
  && make ask`.
- Tag `v0.1.0`.

### 3.5 [opt] Screen recording of the UI (3–5 min) for the build record.

## Cut list (in order, if behind)

1. Fast depth in UI
2. `/bench` page (report stays as Markdown)
3. `prime-search diff`
4. Second holdout pass (report single pass with a note)
5. GEPA on `critic.md` (optimize plan + judge only)
6. Document view paragraph highlighting (link to URL instead)

Never cut: baseline parity, evidence objects with verbatim passages, citations, judge, SearchBench
validation, the bench report, the decision log.

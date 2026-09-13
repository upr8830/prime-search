# 01 — System Architecture

## 1. Component view

```
                          ┌──────────────────────────────┐
                          │  Next.js UI (localhost:3000) │
                          │  side-by-side harness        │
                          └──────────────┬───────────────┘
                                         │ HTTP + SSE
                          ┌──────────────▼───────────────┐
                          │  FastAPI (localhost:8765)     │
                          │  /run  /runs/{id}  /feedback  │
                          │  /bench/summary               │
                          └───────┬──────────────┬────────┘
                                  │              │
                   ┌──────────────▼───┐   ┌──────▼─────────────┐
                   │ baseline.py      │   │ agents/graph.py     │
                   │ (starter-equiv)  │   │ PRIME LangGraph     │
                   └──────┬───────────┘   └──────┬─────────────┘
                          │                      │
             ┌────────────┴──────────────────────┴─────────────┐
             │ primitives/  search() fetch() search_within()   │
             │              extract()      (Tavily-backed)     │
             └────────────┬──────────────────────┬─────────────┘
                          │                      │
                   ┌──────▼──────┐        ┌──────▼──────────────┐
                   │ Tavily API  │        │ Nebius Token Factory │
                   │ Search      │        │ (langchain-nebius)   │
                   │ Extract     │        └──────────────────────┘
                   └─────────────┘
                                  ┌──────────────────────┐
             all runs ───────────►│ LangSmith             │◄──── feedback, datasets, evals
                                  └──────────────────────┘
             eval/  ──► SearchBench ──► evaluators ──► reports/
             eval/gepa ──► optimized prompts ──► prompts/optimized/
```

Three layers, deliberately separated (proposal §4):

1. **Retrieval layer** — Tavily. Answers "what documents match this query?". Wrapped in
   `primitives/` so the agent never sees the raw SDK and every call is budgeted and traced.
2. **Search intelligence layer** — the LangGraph PRIME graph. Answers "what should I search next,
   what counts as evidence, am I done?".
3. **Learning layer** — LangSmith traces + SearchBench + GEPA. Answers "is it getting better, and
   how do I make it better?".

## 2. Runtime processes

| Process | Command | Port | Notes |
|---|---|---|---|
| API | `uv run python -m prime_search.api --reload` (`make dev-api`) | 8765 (`PRIME_API_PORT`) | Runs both agents; streams SSE |
| UI | `pnpm dev` in `ui/` | 3000 | Proxies `/api/*` to the API port via `next.config.js` rewrites |
| CLI | `uv run prime-search ask "..."` | — | Same graph, console rendering like the starter |
| Bench | `uv run python -m eval.run_eval` | — | Batch; uses LangSmith `evaluate()` |
| GEPA | `uv run python -m eval.gepa.run_gepa` | — | Long-running; writes `prompts/optimized/` |

No database. Runs persist to `runs/<run_id>/{state.json, events.jsonl, answer.md}`. Feedback appends
to `data/feedback.jsonl` and is sent to LangSmith. As built (task 2.4), runs execute on a 4-worker thread
pool inside the API process, so a restart leaves in-flight runs `interrupted` (07 §7), and CORS allows the UI
dev origins.

## 3. Configuration

`prime_search/config.py` (pydantic-settings, reads `.env`):

```python
class ModelRouting(BaseModel):
    root: str = "nvidia/nemotron-3-super-120b-a12b"
    critic: str = "nvidia/nemotron-3-super-120b-a12b"
    subagent: str = "moonshotai/Kimi-K2.6"
    judge: str = "deepseek-ai/DeepSeek-V4-Flash-0731"
    extractor: str = "moonshotai/Kimi-K2.6"
    evaluator: str = "moonshotai/Kimi-K2.6"
    baseline: str = "moonshotai/Kimi-K2.6"      # starter default; do not change

class Budget(BaseModel):
    max_searches: int = 30
    max_fetches: int = 20
    max_deep_reads: int = 10          # search_within calls
    max_agents: int = 6               # sub-agents per round
    max_rounds: int = 3               # all search rounds, the initial one included; the critic may add one
    max_tokens: int = 150_000
    max_seconds: int = 180

class DeepBudget(Budget):   # defaults on the class, so one PRIME_BUDGET_DEEP__* override keeps the rest (11)
    max_tokens: int = 400_000
    max_deep_reads: int = 30

class FastBudget(Budget):
    max_searches: int = 3; max_fetches: int = 2; max_agents: int = 1; max_rounds: int = 1; max_seconds: int = 30

class Settings(BaseSettings):
    tavily_api_key: str
    nebius_api_key: str
    langsmith_api_key: str | None = None
    langsmith_project: str = "prime-search"
    models: ModelRouting = ModelRouting()
    budget_deep: DeepBudget = DeepBudget()  # max_tokens=400_000, max_deep_reads=30; round 0 alone spends ~175-195k tokens and 10 reads (11, 2026-09-13)
    budget_fast: FastBudget = FastBudget()  # max_searches=3, max_fetches=2, max_agents=1, max_rounds=1, max_seconds=30
    tavily_cache: bool = True         # cache search/extract by args (used in bench + GEPA)
    tavily_cache_dir: str = ".cache/tavily"

class ServerSettings(BaseSettings):   # separate: the API starts without model or search keys
    api_host: str = "127.0.0.1"        # PRIME_API_HOST
    api_port: int = 8765               # PRIME_API_PORT; not 8000, which HTTP.sys can hold on Windows (11)
```

`.env.example` lists `TAVILY_API_KEY`, `NEBIUS_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`,
and optional `PRIME_MODELS__ROOT=` style overrides, plus `PRIME_API_HOST` / `PRIME_API_PORT` for the API.

## 4. Model routing — verified IDs and the fallback rule

Model IDs verified against Nebius Token Factory documentation on September 11, 2026:

| ID | Role | Notes |
|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | root, critic | 120B hybrid MoE, 12B active, long context, positioned for tool calling and multi-agent planning. Reasoning model: responses may arrive in `reasoning_content` with empty `content`, and a May 2026 GitHub issue on `nebius/api` reported that reasoning models rejected native tool calls through the OpenAI-compatible endpoint. |
| `deepseek-ai/DeepSeek-R1-0528` | optional root alternative | Reasoning model, same caveat. Selectable via `PRIME_MODELS__ROOT`. |
| `deepseek-ai/DeepSeek-V4-Flash-0731` | judge | Switched from Kimi-K2.6 on 2026-09-13: Kimi-K2.6 was the only candidate to fail native `with_structured_output(Verdict)` (2/3; 17/20 separately), V4-Flash went 3/3 at 1.6s median (`reports/model-selection.md`). Fallback `Qwen/Qwen3-30B-A3B-Instruct-2507`. |
| `moonshotai/Kimi-K2.6` | sub-agents, extractor, evaluators, baseline | Starter default; native tool calling assumed working because the starter relies on it. The baseline builds it with `stream_usage=True` (2026-09-13) so streamed replies report token usage - measurement only; model, prompt and tool unchanged. |
| `deepseek-ai/DeepSeek-V3.2` | fallback for non-root roles | Non-reasoning, tool calling documented as working. |

**Design consequence.** The root RLM and the critic do not depend on native tool calling. They emit
fenced Python (root) or fenced JSON (critic) in plain text, which the harness parses. This makes the
reasoning-model roles robust to the tool-call limitation. The `ChatNebius` wrapper must be checked
for how it surfaces `reasoning_content`; `models.py` normalizes so that callers always get text in
`content`. If `langchain-nebius` drops `reasoning_content`, wrap the OpenAI-compatible endpoint via
`ChatOpenAI(base_url=...)` **only** as a last resort and record the decision — the assignment's
stack requirement is Nebius as provider, and `langchain-nebius` is the preferred path.

**Fallback rule (Day 1, `make smoke`):**

1. Root: send a planning prompt; expect a fenced Python block in `content` (or in
   `reasoning_content` + `content` after normalization). Fail → `moonshotai/Kimi-K2.6`.
2. Sub-agent: bind Tavily search tool; expect a tool call on a search-needing question. Fail →
   `deepseek-ai/DeepSeek-V3.2`.
3. Judge/extractor: `with_structured_output(Verdict)`; expect a valid object. Fail → fenced-JSON
   mode with the same model, then fallback model.
4. Record outcomes in `docs/11-assumptions-and-approach.md` → Decision log.

## 5. Tavily usage

| Primitive | Tavily call | Parameters that matter |
|---|---|---|
| `search(query, filters)` | `TavilySearch` | `max_results=8`, `search_depth="advanced"`, `include_domains` when the task targets primary sources (`cms.gov`, `*.cms.gov`, MAC domains, `fda.gov`), `include_raw_content=False` (fetch separately), `time_range` when the task is change-detection |
| `fetch(url)` | `TavilyExtract` | `extract_depth="advanced"`; result cached; stored as `Document` with text and metadata |
| `search_within(doc_id, query)` | none (local) | BM25-lite over paragraphs of a fetched document; returns paragraph ids and text |
| `extract(doc_id, schema)` | LLM (extractor model) | Evidence extraction over selected paragraphs; returns `Evidence[]` |

Search-only fallback: if Extract is unavailable for a domain, `fetch()` re-issues `search` with
`include_raw_content=True` restricted to that URL's domain and uses the raw content.

Domain allow-list for "primary" source filtering lives in `prime_search/primitives/sources.py` and is
shared with the evidence model's source-tier logic.

## 6. LangSmith

- Project: `prime-search` (runs), `prime-search-bench` (evaluation runs), `prime-search-gepa`
  (optimizer rollouts). Configurable.
- Tracing enabled programmatically via `tracing_v2_enabled(project_name, tags)` as in the starter, so
  it is independent of env load order.
- Datasets: `searchbench-v0` with splits `train`, `dev`, `holdout`, tagged by `domain` and `tier`.
- Feedback keys: `user_thumbs`, `user_comment`, plus evaluator keys (see `06-observability.md`).

## 7. Repository and packaging

- `pyproject.toml` with `[project.scripts] prime-search = "prime_search.cli:app"`.
- Dependencies (pin majors): `langchain>=1.0`, `langgraph>=1.0`, `langchain-core>=1.0`,
  `langchain-nebius>=0.1`, `langchain-tavily>=0.2`, `langsmith>=0.12`, `fastapi`, `uvicorn`,
  `sse-starlette`, `pydantic>=2`, `pydantic-settings`, `structlog`, `typer`, `rich`,
  `rank-bm25`, `gepa`, `pytest`, `pytest-asyncio`.
- UI: Next.js 15 App Router, TypeScript, Tailwind, `@tanstack/react-query`, a small SSE hook. No UI
  component library beyond headless primitives; see `07-ui-spec.md`.

## 8. Security and data handling

- API keys only from env. Never logged. `tracing.py` redacts anything matching `tvly-`/`lsv2_`.
- The REPL sandbox for the root RLM exposes only the primitives and workspace helpers; no `os`,
  `subprocess`, network, or file I/O. Executed with a restricted globals dict and a per-cell timeout.
- No PHI: the API rejects inputs that look like patient records (simple heuristic: MRN/DOB patterns)
  with a clear message. This is a demo guard, not a compliance control, and is described as such.

## 9. Failure handling

- Tavily error → primitive returns an empty result with `error` set; the sub-agent sees it and may
  retry once with a reformulated query; the budget still counts the call.
- Model output unparseable → one repair attempt with the same model ("return only the fenced
  block"); then the node returns a structured failure and the graph proceeds (judge can mark the
  branch `unresolved`).
- Budget exhausted → graph jumps to synthesis with whatever evidence exists; answer's "unknowns"
  section states the budget was hit. *As built (2026-09-13, user decision):* an exhausted budget
  starts no further search round, but the judge and critic still run once so the answer carries
  their coverage gaps and contradictions (~20k tokens); only the deadline skips them.
- Wall-clock exceeded → same as above, via a checked deadline at every node boundary.

## 10. Repository layout (target)

```
prime-search/
  CLAUDE.md                       short: constraints, commands, conventions
  .claude/                        Claude Code settings, hooks, skills, subagents
  README.md · pyproject.toml · .env.example · Makefile
  prime_search/
    config.py                     settings, model routing, budgets
    models.py                     ChatNebius factories per role (only place ChatNebius is built)
    baseline.py                   starter-equivalent simple agent
    primitives/                   Tavily-backed search primitives + source tiers + docmeta + BM25
    workspace.py                  per-run workspace state + sandboxed REPL
    schemas.py                    Pydantic contracts (see 02)
    evidence/  store.py graph.py cite.py
    agents/    root.py search_agent.py judge.py critic.py synthesizer.py graph.py
    prompts/   *.md  (+ optimized/ written by GEPA)
    tracing.py · events.py · cli.py
    api/main.py                   FastAPI
  eval/
    searchbench/  sync.py fetch_sources.py from_feedback.py
    evaluators.py · run_eval.py · report.py
    gepa/  adapter.py run_gepa.py
  data/searchbench/               questions + validated keys + sources/
  ui/                             Next.js app
  docs/ · build-log/ · reports/ · runs/examples/
```

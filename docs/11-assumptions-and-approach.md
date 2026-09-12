# 11 — Assumptions, Approach, and Decision Log

Living document. Claude Code appends to the Decision log whenever it deviates from a spec, chooses
between alternatives, or finds an assumption wrong. This file is part of the build record.

## 1. Assumptions

### About the assignment
- A1. "Meaningfully improve it" is interpreted as: keep the starter's stack and purpose (a Tavily +
  LangChain research agent on Nebius) and change *how it searches*, with measurable evidence. The
  starter is the baseline, not a scaffold to extend line by line; the starter's own docstring says
  the sample code need not be followed.
- A2. The reviewers are Tavily/Nebius engineers and product people. They will read the technical
  statement first, run the UI second, and read code third. Traces and the bench report are the proof.
- A3. Multiple "example directions" can be addressed by one coherent design; breadth of directions
  is not rewarded over coherence.
- A4. The build record can be Claude Code session exports in Markdown plus this decision log; no
  third-party trace platform is required.
- A5. Deliverable timeline: 2–3 days of work (Sept 12–14, 2026).

### About the domain
- A6. CMS (Medicare) is the payer. The governing documents for CGM are the DME MAC LCD
  (`L33822 Glucose Monitors`) and its companion article (`A52464`); there is no NCD for CGM. For
  GLP-1s the governing material is Part D statute (weight-loss exclusion), CMS guidance memos on
  medically accepted indications, FDA labels, and 2025–2026 CMS actions on obesity coverage and the
  Innovation Center model. **Each of these is verified during SearchBench source fetch; the answer
  keys carry `as_of`.**
- A7. Policy state on September 12, 2026 may differ from the author's knowledge (cutoff mid-2026).
  Draft answer keys are expected to be partly wrong; the validation step exists for this reason.
- A8. All sources are public web pages reachable by Tavily. CMS coverage-database pages are
  JavaScript-heavy; Tavily Extract may or may not return clean text. Fallback defined in 01 §5.
- A9. No PHI is involved. Questions are about policy; the system does not adjudicate individuals.
- A10. Practitioners phrase questions ambiguously; the benchmark preserves that ambiguity.

### About the stack
- A11. `langchain-nebius` exposes Token Factory models through `ChatNebius` with streaming and
  tool binding, as the starter demonstrates for Kimi-K2.6.
- A12. `nvidia/nemotron-3-super-120b-a12b` is available on Token Factory (announced March 2026) and
  is a reasoning model. A May 2026 issue on `nebius/api` reported that reasoning models returned
  content in `reasoning_content` and rejected native tool calls via the OpenAI-compatible endpoint.
  This may be fixed by September; the design does not depend on it being fixed.
- A13. `deepseek-ai/DeepSeek-R1-0528` is available as an alternative root model with the same
  caveat.
- A14. `moonshotai/Kimi-K2.6` supports tool calling and structured output well enough for
  sub-agents, judge, extractor, and evaluators. `deepseek-ai/DeepSeek-V3.2` is the fallback.
- A15. LangSmith `evaluate()` and feedback APIs work as of `langsmith>=0.12`. The GEPA standalone
  library can optimize arbitrary text components through a custom adapter.
- A16. Tavily rate limits and Token Factory quotas are sufficient for ~150 prime runs over three
  days with caching. If not, GEPA budget shrinks first.
- A17. Local machine runs Python 3.11+ and Node 20+; no Docker required.

### About scope
- A18. Memory, skill library, RL, commercial payers, other therapeutic areas: out. See 10.
- A19. UI is a test harness; visual polish is the last priority.
- A20. Fast depth is CLI-only unless time allows.

## 2. Approach

### 2.1 Reasoning chain
1. The assignment asks for improvement with clear value. The transcript's advice: pick a real
   problem, keep Tavily as the retrieval tool, replace the plain-LLM agent with a recursive
   language model that decomposes and delegates, and make observability + evaluation the backbone.
2. The PRIME Search proposal formalizes that: search as an investigation program over minimal
   primitives, evidence objects instead of documents, a judge and a critic, a budget, a benchmark,
   and a learning loop.
3. Coverage-determination research is a domain where the single-search failure modes (stale
   criteria, LCD/article confusion, secondary sources overstating coverage) are concrete, public,
   and verifiable — and it is the author's domain.
4. Three days allow the MVP tier (proposal §19) plus one learning mechanism. GEPA was chosen over
   memory/skills because it produces a measurable before/after number with the least new
   infrastructure, and it uses the evaluators that must be built anyway.
5. Native LangGraph rather than Prime Agent: the assignment mandates LangChain; the RLM properties
   that matter (workspace variables, code-as-action, independent sub-agent contexts, async fan-out)
   are implementable with LangGraph state, a sandboxed REPL, subgraphs, and `Send`.

### 2.2 Key design choices and rejected alternatives
| Choice | Alternative rejected | Why |
|---|---|---|
| Code-as-action for the root | Native tool calls | Robust to reasoning-model tool-call limitations on the endpoint; makes the plan an executable object; visible in traces |
| Evidence objects with verbatim passages validated by the tool | Summaries from sub-agents | Enables claim-level citations, citation-correctness evaluation, contradiction detection |
| Judge (cheap, per round) + critic (expensive, once or twice) | Single reflection step | Separates "enough?" from "right?"; keeps cost bounded |
| Deterministic evaluators where possible; LLM-judge with `must` rubric elsewhere | Free-form LLM grading | Lower noise; comments usable as GEPA feedback |
| GEPA on plan/judge/critic only | All prompts | Search space and cost; these three shape the search policy |
| Next.js + FastAPI | Streamlit | User preference; SSE-driven tree view is natural in React |
| Baseline re-implemented verbatim | Improved baseline | Honest comparison; `starter_agent.py` excluded per assignment |
| Answer keys from live fetch + human validation | Author-written keys | Policy drift; provenance |
| Jaccard claim merge | Embeddings | Time; roadmap R3 |

### 2.3 How value is demonstrated
- Bench report: baseline vs PRIME vs PRIME+GEPA on holdout, per tier and domain.
- Three worked examples in the report and in the statement: an eligibility question (currency), a
  contradiction question (surfacing disagreement), an out-of-scope question (not fabricating).
- The UI: a reviewer can watch the investigation and open any evidence passage.
- The traces: LangSmith experiments linked from the report.

## 3. Risks and mitigations

| # | Risk | Likelihood | Mitigation | Trigger to act |
|---|---|---|---|---|
| R1 | Nemotron tool/structured output unreliable via `ChatNebius` | Med | Code-as-action; `make smoke`; fallback to Kimi for root | Smoke fails |
| R2 | Tavily Extract returns poor text for CMS pages | Med | Raw-content fallback; MAC mirror pages; docmeta regex tolerant | `fetch` yields < 20 paragraphs on L33822 |
| R3 | Ground-truth drift | High (by design) | Validation step; `as_of` | Always |
| R4 | GEPA cost/time overrun | Med | Cache; capped metric calls; optimize two prompts instead of three | > 3 h wall time |
| R5 | Evaluator noise hides the effect | Med | `must` rubrics; two holdout passes; report spread | Spread > effect |
| R6 | Time | High | Cut list in 09; gates | Any gate slips > 3 h |
| R7 | Sub-agent budget abuse (loops) | Low | Tool-call cap; `BudgetExceeded`; deadline checks | Trace shows > 8 tool calls |
| R8 | Reviewer cannot run it | Med | Fresh-clone test; `make smoke`; cached example runs committed under `runs/examples/` | Day 3 |

## 4. Decision log

Format: `YYYY-MM-DD — <decision> — <reason> — <spec affected>`

- 2026-09-11 — Primary use case: CMS coverage research for CGM and GLP-1 — author's domain; public, verifiable sources; clear single-search failure modes — 00
- 2026-09-11 — Scope: MVP tier + GEPA; memory/skills/RL to roadmap — 3-day window; GEPA yields a measurable number — 00, 05, 10
- 2026-09-11 — Models: Nemotron 3 Super root/critic, Kimi-K2.6 sub-agents/judge, DeepSeek-R1 optional root, DeepSeek-V3.2 fallback — user preference; verified IDs; tool-call caveat noted — 01
- 2026-09-11 — Native LangGraph RLM, no Prime Agent dependency — LangChain mandated; smaller surface — 03
- 2026-09-11 — Root uses code-as-action, not native tool calls — reasoning-model endpoint limitation reported May 2026 — 01, 03
- 2026-09-11 — UI: Next.js + FastAPI, local — user preference — 07
- 2026-09-11 — Answer keys built from live fetch and human-validated with `as_of` — knowledge cutoff vs Sept 2026 policy state — 08
- 2026-09-11 — Baseline re-implements the starter verbatim; `starter_agent.py` never committed — assignment requirement; fair comparison — 03
- 2026-09-11 — Human feedback loop stops at candidate records; no automatic prompt or data updates — safety; time — 05
- (Claude Code appends below during the build)
- 2026-09-12 — Makefile is the only task runner; GNU make 4.4.1 installed on Windows (winget ezwinports.make) and recipes kept single-line and shell-agnostic — every 09 check is phrased `make ...` and the reviewer runs macOS/Linux; a PowerShell mirror would drift over three days — 09 §1.1
- 2026-09-12 — `pyproject.toml` written by hand instead of `uv init`; hatchling with `packages = ["prime_search", "eval"]` — 01 §10 is a src-less two-package layout and `uv init` defaults create `src/` and miss `eval/`, which `python -m eval.run_eval` needs — 01 §7, §10
- 2026-09-12 — Python 3.13.5 (system interpreter), `requires-python = ">=3.11,<3.14"` — A17 allows 3.11+; all 83 packages incl. gepa 0.1.4 resolved on 3.13, so no 3.12 pin was needed; upper bound keeps a reviewer off an unverified wheel set — 11 A17
- 2026-09-12 — pytest/pytest-asyncio in `[dependency-groups] dev`, gepa in its own `gepa` group, `make setup` = `uv sync --all-groups`; `uvicorn[standard]` for a working `--reload` — 01 §7 gives one flat list; isolating a Day-3-only dependency keeps it from blocking the Day-1 gate while still resolving it today — 01 §7
- 2026-09-12 — 1.1 ships `tests/test_scaffold.py` (version, console-script entry point, secret redaction) rather than zero tests — pytest exits 5 on empty collection so "0 tests OK" would fail the stated check; a passing assertion is evidence, `|| true` is suppression — 09 §1.1
- 2026-09-12 — structlog configured in `prime_search/tracing.py`, logging to stderr with the redaction processor last before rendering; JSON automatically when stderr is not a TTY — 01 §10 has no `logging.py` and 01 §8 assigns tvly-/lsv2_ redaction to `tracing.py`; stdout is reserved for CLI answers and SSE — 01 §8, §10
- 2026-09-12 — `make smoke` = `uv run prime-search smoke` (a CLI subcommand) — keeps the file set inside the 01 §10 layout, which lists `cli.py` and no smoke module — 01 §10, 09 §1.2
- 2026-09-12 — `.gitignore` `runs/` → `runs/*` plus `!runs/examples/` — git cannot re-include a path under an excluded directory, so the original line would have silently swallowed the example runs R8 requires committing — 11 R8, 01 §10
- 2026-09-12 — Console-visible CLI strings are ASCII only — the Windows default codepage rendered an em dash in the Typer help as a replacement character — 03 §9
- 2026-09-12 — `ui/` generated with `create-next-app@15` (pinned, not `@latest`) — 01 §7 and 07 specify Next.js 15 App Router; the current generator would have installed a later major — 01 §7, 07
- 2026-09-12 — `ui/pnpm-workspace.yaml` sets `allowBuilds: unrs-resolver: true` — pnpm 12 aborts the install rather than running dependency build scripts, and this native resolver backs eslint-config-next; without it `pnpm install` fails outright — 09 §1.1
- 2026-09-12 — Settings uses `env_prefix="PRIME_"` with `AliasChoices("PRIME_X", "X")` on the four credential fields, and `export_sdk_env()` pushes them back to `os.environ` via setdefault — 01 §3 requires unprefixed keys in `.env.example` AND `PRIME_MODELS__ROOT` overrides, which one prefix cannot do; pydantic-settings skips the prefix for aliased fields. The langsmith and Tavily clients read `os.environ` directly, so a `.env`-only key would otherwise be invisible to them — 01 §3, §6
- 2026-09-12 — ASSUMPTION WRONG: 01 §6's `tracing_v2_enabled(project_name, tags)` exists in langchain-core 1.6 but its tracer never populates `latest_run`, so `get_run_url()` always raises "No traced run found." Replaced with `tracing.trace_run()`, an explicit langsmith `RunTree` parent under `tracing_context(enabled=True)`; verified 1 nested child run and a working URL. This is strictly better for the UI: the trace URL exists before the run ends — 01 §6
- 2026-09-12 — SMOKE RESULT: no model fallback needed. All five roles passed on the specified models: Nemotron 3 Super root and critic both emit fenced Python, Kimi-K2.6 sub-agent emits native tool calls, judge and extractor return a valid Verdict. The 01 §4 / 11 A12 tool-call caveat did not bite — 01 §4, 11 A12, R1
- 2026-09-12 — Judge/extractor structured output goes through `models.structured()`, a two-rung ladder: native `with_structured_output` retried up to 3x, then fenced JSON from the same model — measured Kimi-K2.6 returning None on 3 of 20 identical calls (15%), and a judge runs on every question. This is 01 §4 rule 3 step 2, not a model switch; `last_mode` records which rung answered — 01 §4
- 2026-09-12 — `with_structured_output(method="json_schema")` is unusable on langchain-nebius 0.1.3: AttributeError 'NoneType' object has no attribute 'chat' on all 6 attempts. Default `function_calling` works. Do not try to switch methods to fix flakiness — 01 §4
- 2026-09-12 — `temperature=0.0` for every role except baseline, which keeps the provider default to stay starter-equivalent; `max_retries=2`, `timeout=120` — no sampling parameters are specified anywhere in the specs, and bench re-runs must be comparable — 01 §4, 00 FR-16
- 2026-09-12 — SMOKE RESULT: R2 does not bite. Tavily Extract on the CGM LCD returned 79,345 chars / 492 non-empty lines, so the 01 §5 raw-content fallback is not needed for CMS pages yet. Still implement it at 1.3 as specified, since one good response is not a guarantee — 11 R2, 01 §5
- 2026-09-12 — Smoke logic lives in `prime_search/smoke.py` with `prime-search smoke` as the interface, refining the earlier "CLI subcommand" line — 150 lines of probes do not belong in `cli.py`, and §10's tree already omits `tests/`, so it is a target layout rather than an exhaustive one — 01 §10, 09 §1.2
- 2026-09-12 — Tavily tool constructors landed in `primitives/tavily.py` at 1.2 rather than 1.3 — 1.2's smoke must call Tavily, and CLAUDE.md requires every Tavily call to go through `primitives/`; 1.3 builds search/fetch/cache on top rather than replacing it — 01 §5, 09 §1.2
- 2026-09-12 — Prompts are loaded through `prompts/__init__.py` (`load`/`render`, with a `prompts/optimized/` preference for `prompt_set="optimized"`); placeholder substitution is a plain replace, not `str.format`, because the prompts contain literal braces in code examples — 05 §5, CLAUDE.md
- 2026-09-12 — SPEC-REVIEW FIX: removed `baseline` from `FALLBACKS` entirely and made `fallback_model("baseline")` raise — the earlier table gave baseline a DeepSeek-V3.2 fallback, contradicting 01 §3's "starter default; do not change" and the baseline-parity constraint the whole comparison rests on. A silently switched baseline would invalidate every bench row — 01 §3, §4, CLAUDE.md
- 2026-09-12 — `FALLBACKS["critic"]` corrected from Kimi-K2.6 to DeepSeek-V3.2 — 01 §4's table makes V3.2 the fallback "for non-root roles" and rule 1 names Kimi only for root; the earlier Kimi choice was an inference with no spec basis, and a test had pinned the inference instead of the spec — 01 §4
- 2026-09-12 — SPEC-REVIEW FIX: the critic now has its own smoke probe using fenced JSON (`prompts/smoke_critic.md`), not root's fenced-Python probe — 01 §4 says root emits fenced Python and critic fenced JSON, so one shared probe could pass a model that produces only one of the two — 01 §4, 09 §1.2
- 2026-09-12 — SPEC-REVIEW FIX: `make smoke` now probes all seven ModelRouting roles, adding `evaluator` and `baseline` (10 checks total) — 09 §1.2 says "for each role"; with only five probed, a `PRIME_MODELS__EVALUATOR` override or a baseline change would pass the gate untested — 09 §1.2
- 2026-09-12 — 01 §4 rule 3's third rung ("then fallback model") is deliberately NOT automatic: exhausting native + fenced JSON raises and a human decides — KICKOFF_PROMPT requires asking before applying a model fallback, and silently switching the judge mid-bench would make two runs incomparable. Recording the conflict explicitly rather than implying conformance — 01 §4, KICKOFF_PROMPT
- 2026-09-12 — `StructuredCaller` default attempts 3 -> 2, and an exception now breaks to the fenced rung instead of consuming retries — 01 §9 allows "one repair attempt with the same model"; the earlier loop retried a bad API key three times before surfacing anything — 01 §9
- 2026-09-12 — SPEC-REVIEW FIX: the rule-3 fenced-JSON instruction moved out of `models.py` into `prompts/fenced_json.md` — it is production prompt text for the judge and extractor, and CLAUDE.md requires every prompt to be a `.md` under `prime_search/prompts/` so review and GEPA can see it — CLAUDE.md
- 2026-09-12 — Reasoning normalization extended to the streaming path (`_convert_chunk_to_generation_chunk`) — 01 §4 promises callers *always* get text in `content`, and 1.7 streams the answer to the console and over SSE; only the invoke path was covered — 01 §4, 09 §1.7
- 2026-09-12 — Tavily tool constructors take the API key from `Settings` instead of the ambient environment — a tool built before `export_sdk_env()` ran would have failed with a confusing "did not find tavily_api_key", and the parameter choices were untestable offline — 01 §5
- 2026-09-12 — `schemas.py` landed at 1.2 rather than 1.4 — 01 §4 rule 3's smoke probe needs `Verdict`; the file is a field-for-field subset of 02 §2.3/§2.6 and 1.4 completes it — 09 §1.2, §1.4, 02

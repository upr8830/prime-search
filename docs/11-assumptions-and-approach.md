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
- 2026-09-12 — MAC, professional, trade and web hostnames are researched, not specified — 04 §1 names organizations (Noridian, CGS, Palmetto, NGS, WPS, Novitas, First Coast) and no hostname anywhere in the specs; kept as a `RULES` data table so a wrong host is a one-line fix plus a test row — 04 §1, 01 §5
- 2026-09-12 — Tier matching is longest-host-suffix then longest-path-prefix, not host-only — `cms.gov` serves `primary_policy` (/medicare-coverage-database) and `official_secondary` (newsroom, MLN, files), and 04 §1 makes fda.gov primary only for labels/approvals; host-only matching would score a CMS press release 1.0 — 04 §1
- 2026-09-12 — Added `TIER_RANK` as the total order — `web` and `unknown` both score 0.3, so 05's `primary_source_ratio` ("tier >= official_secondary") cannot be expressed by quality alone — 04 §1, 05 §2
- 2026-09-12 — `refine_tier` rules invented: promote only when an official host's own text proves the page IS the rule (LCD/Article/NCD/FDA record with its external id), demote fact sheets and press releases served from a primary path, never below the URL tier — 04 §1 requires post-fetch refinement and defines no algorithm — 04 §1
- 2026-09-12 — Unlisted `.gov` hosts stay `unknown` (0.3); no blanket `*.gov` rule — tier gates whether a coverage claim counts as supported, and an unlisted `.gov` could be a state agency. Strict, and it moves `primary_source_ratio` — 04 §1
- 2026-09-12 — `doc_id = "doc_" + sha1(normalize_url(url))[:10]`, reconciling 02 §2.4's `sha1(url)` shorthand with 03 §13's "hash of the normalized URL". Normalization forces https, drops `www.`, lowercases parameter NAMES (the CMS coverage database emits both `articleId` and `articleid` for one page), drops tracking/nav params, and keeps `ver` because a different LCD version is a different document for 04 §4's supersession edges — 02 §2.4, 03 §13
- 2026-09-12 — ASSUMPTION WRONG: the CMS header metadata block is JavaScript-rendered and absent from the Tavily extract on BOTH L33822 and A52464 — neither extract contains "Original Effective Date" at all. Dates are therefore aggregated over the whole document (latest non-future revision, earliest original) instead of read from a fixed position, and both CMS pages legitimately have `revision_date` and NO `effective_date` — 04 §2
- 2026-09-12 — A date label inside a markdown table HEADER is not adjacent to its value and is skipped — CMS's "Associated Documents" table reads `| Updated On | Effective Dates | Status |` over `| 10/09/2024 | 10/01/2024 - N/A | ... |`, so the nearest date after "Effective Dates" is the Updated On cell. Reading it gave L33822 a spurious effective_date of 2024-10-09. Data rows are kept, because CMS writes "Revision Effective Date: 10/01/2024" inside one cell — 04 §2
- 2026-09-12 — ASSUMPTION WRONG: 04 §2's canonical section names are not headings on the live pages — "COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY" occurs 21 times inside L33822's table cells. Heading detection is whole-line markdown/HTML/bold markers plus the canonical names only when they own a line; site-chrome headings are excluded from `sections` so they cannot reach a citation via `Location.section` — 04 §2, §5
- 2026-09-12 — Date labels extended with `Revised` and `Updated` (weak) and with month-year parsing ("Revised: 5/2026" -> 2026-05-01) — FDA/DailyMed labels use neither a label 04 §2 lists nor a full date; weak kinds never outrank a real Revision Effective Date. 04 §2 says "patterns like", so the list is illustrative — 04 §2
- 2026-09-12 — FDA external-id patterns (`NDA|BLA|ANDA \d{6}`, `K/P/DEN\d{6}`, SPL `setid`, `ApplNo`) and the `510(k)`/`Approval`/`Label` doc types are inventions — no spec gives an FDA id pattern, yet 09 §1.3 requires an FDA fixture; 02 §2.4's doc_type list is open-ended — 09 §1.3, 02 §2.4
- 2026-09-12 — Paragraph indices are 0-based and offsets are half-open character offsets into the persisted normalized text, written with `newline="\n"` — 04 §3 validates evidence as a substring of its paragraph, so `text[char_start:char_end] == paragraph.text` is load-bearing, and Windows' default newline translation would shift every offset — 04 §3, 07
- 2026-09-12 — `normalize_text` folds curly quotes, NBSP and U+2010 once before persisting, and preserves leading indentation — an agent retyping ASCII still satisfies 04 §3's substring check, while DailyMed's nested list continuations stay verbatim — 04 §3
- 2026-09-12 — `snippet_only` documents carry `text_path=""` and `paragraph_count=0` — 02 §2.4 makes both required; a sentinel keeps the contract without widening the schema — 02 §2.4
- 2026-09-12 — `fetch` accepts a URL or a doc_id, reconciling 01 §5's `fetch(url)` with 03 §4's `fetch(doc_id)`; ids resolve against the caller's `ws.documents` — 01 §5, 03 §4
- 2026-09-12 — Cache key is `sha1({v, op, canonical args})` at `.cache/tavily/<sha1>.json`, query casefolded and domain lists sorted so equivalent calls share an entry; the entry stores its own args and a mismatch is a miss. The API key is never part of the key — 04 §6, 01 §3
- 2026-09-12 — The raw-content fallback triggers on error OR fewer than 20 paragraphs, keeps whichever text has more, and reports in `error` when it did not help — this makes R2's trigger executable rather than theoretical; a document left under the threshold with `error=None` would hide exactly the failure R2 exists to surface — 11 R2, 01 §5
- 2026-09-12 — `search_within` indexes oversized paragraphs as overlapping 2000-char windows carrying the parent's `paragraph_index` — 04 §2 forbids splitting tables, and L33822's revision-history table is 16k chars while A52464's ICD-10 table is 52k; windowing keeps a deep read citable without pushing 50 KB into an agent's context — 04 §2, 03 §4
- 2026-09-12 — Relevance in `search_within` is query-token overlap, not `score > 0` — `BM25Okapi` returns negative scores for terms appearing in more than half the corpus (measured -0.134). k1/b/epsilon are pinned because a library default change would silently re-rank every deep read — 03 §4
- 2026-09-12 — Boilerplate paragraphs (site banners, "skip to main content", AMA/AHA/CDT license blocks) are excluded from the BM25 index but keep their indices and offsets, so `?p=<index>` and `Location` stay valid — 03 §4, 07
- 2026-09-12 — `Document` and `Location` landed at 1.3 rather than 1.4, field-for-field from 02 §2.4, because `fetch` returns a `Document` — same pattern as `Verdict` arriving early for 1.2 — 09 §1.3, §1.4
- 2026-09-12 — docmeta fixtures live in `tests/fixtures/docs/` with a `SOURCES.md` and a `refresh.py`; `data/searchbench/sources/` stays task 1.8. The FDA label fixture is the DailyMed SPL for Ozempic, not the Drugs@FDA PDF: Tavily Extract cannot read that PDF (raises instead of returning results), and GLP-1 questions cite a drug label — 09 §1.3, 08 §2
- 2026-09-12 — CONFIRMED DRIFT: L33822's current revision is 10/01/2024 (R16); the draft answer keys still expect 2023-04-16 (R12). The live test asserts a valid date rather than a specific one, and task 2.1 must correct the keys — 08 §2, 11 A7, R3
- 2026-09-12 — SPEC-REVIEW FIX: `fda.gov` restored to `PRIMARY_DOMAINS`, and FDA `Label`/`Approval`/`510(k)` doc types now promote to `primary_policy` on FDA hosts without requiring an external id — 01 §5 names fda.gov in the primary include-domain list, and 04 §1 calls FDA labels primary, but a label page often states no application number, so the id requirement left every FDA label both unreachable by a primary-filtered search and un-promotable after fetch. An include-domain list says where to look; the tier says how much a document weighs — 01 §5, 04 §1
- 2026-09-12 — SPEC-REVIEW FIX: `fetch` now reports an error when the raw-content fallback improves a thin extract but leaves it under `MIN_PARAGRAPHS` — clearing `error` because the fallback helped at all hid exactly the R2 case it exists to surface (6 paragraphs -> 11 came back error-free) — 11 R2
- 2026-09-12 — SPEC-REVIEW FIX: the cached `fetch` path returns section headings from the sidecar instead of `[]` — 03 §4 says fetch returns section headings, and the idempotent path must return the same shape as the first call — 03 §4
- 2026-09-12 — SPEC-REVIEW FIX: `load_paragraphs` now runs before the BM25 index cache and verifies the sidecar's `text_sha1` — the paragraph-count drift guard sat behind the cache, so an already-indexed document was served with a stale count, and the recorded sha1 was written but never read, leaving a text rewritten without its sidecar undetectable whenever the count happened to match. Both leave every evidence offset pointing at the wrong words — 04 §3
- 2026-09-12 — SPEC-REVIEW FIX: `parse_date_token` iterates all matches of each pattern rather than abandoning a pattern after its first — "Chapter 15, 2024 revised April 16, 2023" matched the month-name shape on "Chapter 15, 2024" and returned None; `_MONTH_YEAR_NUM` gained a lookbehind so "Pub 100-02/2024" is a manual reference, not February 2024 — 04 §2
- 2026-09-12 — SPEC-REVIEW FIX: weak date labels (`Revised`, `Updated`) search a 24-char window instead of 140 — "Revised to add code A4239 effective 07/01/2018" in a revision-history cell booked that date as the document's revision. CMS's `Notice Period Start/End Date` header fields were added as known labels so they terminate a preceding empty label's window — 04 §2
- 2026-09-12 — `fetch` writes text to `.cache/tavily/docs/` when called outside a run (tests, fixtures, `fetch_sources.py`) instead of 04 §6's `runs/<run_id>/docs/` — `text_path` must always name a real file for 04 §3 to validate evidence against, and the cache directory is already gitignored — 04 §6
- 2026-09-12 — docs/02 §2.4 updated in place to record the `snippet_only` sentinel (`text_path=""`, `paragraph_count=0`), `is_fetched`, and `= None` on every nullable field — CLAUDE.md requires a schema change to update docs/02 in the same commit, and the sentinel had been logged here but never written into the contract itself — 02 §2.4
- 2026-09-12 — `Workspace` is a dataclass, not a Pydantic model — 03 §1 threads one mutable object through the graph and nodes mutate it in place; `RunRecord` is the serialized form and `to_record()` the bridge, so validation belongs there — 02 §3, 03 §1
- 2026-09-12 — `Workspace` carries `budget`, `usage`, `run_id` and `started_at` beyond the 02 §3 list — 03 §3's own example cell writes `budget=ws.budget`, so the attribute must exist alongside `budget_remaining()`; usage is what makes `budget_remaining()` computable, and the run id and start time are what `RunRecord` needs and nothing else holds — 02 §3, §2.1, 03 §3
- 2026-09-12 — `ws.search_tree` is a derived property rather than a stored dict — deriving it from `tasks` and `evidence` makes it impossible for the tree to disagree with them; nothing in the specs writes to it. A branch holding evidence but no task this round reports `resolved` rather than staying `pending` forever — 02 §3
- 2026-09-12 — `ws.dates()` returns `revision_date or effective_date` and only for fetched documents — 02 §3 types it on `effective_date` alone, but both CMS flagship pages carry a revision date and no effective date (measured 2026-09-12), so the literal reading returns nothing for exactly the documents 03 §12 cites as the helper's purpose; an unfetched document has no dates to report — 02 §3, 04 §2
- 2026-09-12 — `docs_by_tier` gained an `at_least` keyword beyond 02 §3's signature — 04 §1's consumer rule and 05's `primary_source_ratio` both ask "official or better", and forcing every caller to re-derive that from `TIER_RANK` invites drift — 02 §3, 05 §2
- 2026-09-12 — `search_within` is a `Workspace` method, not a cell global — 03 §12 says the namespace holds `ws`, the schema classes, `date`, `datetime` "and nothing else", 01 §8 says "the primitives and workspace helpers", and 02 §3 has the root calling `search_within`. A method satisfies all three and keeps deep-read accounting on the object owning the budget. `search`/`fetch` stay out of the cell: 03 §4 gives those to the sub-agents — 03 §12, 01 §8, 02 §3
- 2026-09-12 — `search_within` resolves `text_path` and refuses anything outside the run's document directories, and refuses once `max_deep_reads` is spent — 01 §8 says the sandbox does no file I/O; because `Document` is in the cell namespace, a cell could otherwise register a document of its own and read any path it named. Mediated access to this run's fetched text is the intent — 01 §8, 01 §3
- 2026-09-12 — `Budget` is injected into the cell namespace alongside the schema classes, despite 03 §12's "nothing else" — 03 §3's own plan cell constructs a plan whose `budget` field is a `Budget`, so the name is reachable either way; making it explicit avoids a confusing NameError on a legitimate cell — 03 §12, 03 §3
- 2026-09-12 — Per-cell timeout defaults to 5s, enforced by a `sys.settrace` line hook with a thread join as backstop, not `signal.alarm` — 03 §12 allows "signal.alarm (Unix) or a thread with join timeout" and `signal.alarm` does not exist on Windows; a join alone only abandons the cell, and a pure-Python busy loop holds the GIL tightly enough to hang interpreter shutdown, which `while True: pass` demonstrably did. No timeout value is specified anywhere — 03 §12
- 2026-09-12 — The cell owns its own `print` bound to the cell buffer instead of `contextlib.redirect_stdout` — a global redirect swaps `sys.stdout`/`stderr` process-wide, so for the duration of every cell all other threads' output (structlog on stderr, a streaming answer on stdout) would be captured into that cell's 4k buffer — 03 §12, 01 §8
- 2026-09-12 — The sandbox builtins allowlist is this build's: 03 §12 names only the four denials (`open`, `__import__`, `eval`, `exec`). It includes `__build_class__` (a `class` statement compiles to it) and the common exception names, because a cell writing a defensive `try/except` otherwise fails with an unexplainable NameError. `getattr`/`type` are included and make the denial list bypassable by attribute traversal: this is a guard against a model's mistakes, not a security boundary — 03 §12
- 2026-09-12 — Each cell gets a fresh namespace; only `ws` carries between cells — a failed cell leaves no half-bound locals for the repair turn (03 §12) to trip over, and `ws` is the state the design intends to persist — 03 §12
- 2026-09-12 — `run_id` is a hand-rolled RFC 9562 uuid7 rather than a dependency — `uuid.uuid7()` lands in the 3.14 stdlib and this build targets 3.11-3.13; time ordering is the point, so `runs/` sorts chronologically. Not monotonic within a millisecond, which run directories do not need — 02 §2.1
- 2026-09-12 — Collection fields and `RunRecord.status` in `schemas.py` carry defaults 02 §2 does not show, and docs/02 §2.1 was updated in the same commit to record it — a RunRecord is written at the start of a run as well as the end (02 §5), so it must be constructible before any task, document or answer exists — 02 §2.1, §5
- 2026-09-12 — ASSUMPTION WRONG: `deepseek-ai/DeepSeek-V3.2` and `deepseek-ai/DeepSeek-R1-0528` are NOT in the Nebius catalog (checked live via /v1/models, 24 models offered). 01 §4 names V3.2 as the fallback for every non-root role, so five of six `FALLBACKS` entries would have raised model-not-found the first time a role needed rescuing — a dead switch in the one mechanism meant to recover from a failing role. Replaced with the V4 line, each entry chosen on a measured result for that role's own call shape: critic -> DeepSeek-V4-Pro (3/3 fenced JSON), subagent/judge/extractor/evaluator -> DeepSeek-V4-Flash-0731 (5/5 native tool calls, 3/3 structured output). Root keeps rule 1's Kimi-K2.6, which is still offered and measured 5/5 on code-as-action. Every fallback is a different vendor line from its role's primary. No Llama 4 is offered at all — 01 §4, reports/model-selection.md
- 2026-09-12 — Added a live test asserting every routed and fallback model id exists in the Nebius catalog — the dead-fallback bug was invisible to the whole offline suite and to `make smoke`, which never exercises a fallback. This is the guard that catches the next disappearance — 01 §4
- 2026-09-12 — `get_settings()` now warns on any `PRIME_`-prefixed variable that matches no Settings field, naming the closest real one — `Settings` uses `extra="ignore"`, so `PRIME_MODELS__SUB` (the field is `subagent`) sat in a .env doing nothing while looking deliberate. Warns rather than raises: a stale variable in someone's shell should not stop a run, but it must not be invisible either. `.env.example` now states that the name after `__` is the field name exactly — 01 §3
- 2026-09-12 — MODEL SELECTION MEASURED (reports/model-selection.md, 104 calls, $0.44): root/critic stay on nemotron-3-super-120b-a12b, which won on every axis — 5/5 valid plans and 3/3 parseable critiques at the lowest cost ($0.00125/call) and lowest latency (4.4s) of any root candidate; Kimi-K3 matched its validity at 23x the cost and 5x the latency. `zai-org/GLM-5.3` fails code-as-action outright (2/5 fenced Python, 1/3 fenced JSON) and cannot hold a root or critic role. 11 A12's tool-call caveat does not reproduce on any current model: all six sub-agent candidates emitted native tool calls 5/5, including a reasoning-family model. Kimi-K2.6 was the only candidate to fail native structured output (2/3), reproducing the 15% None rate measured earlier — a judge/extractor/evaluator switch to DeepSeek-V4-Flash-0731 is recommended and NOT yet applied, pending approval — 01 §4
- 2026-09-12 — `add_evidence` locates a passage whitespace-insensitively (a squeezed-index map over the paragraph) and then stores the document's OWN bytes for that span, not the agent's typing — 04 §3 rule 2 specifies a whitespace-normalized *comparison*; canonicalizing goes one step further so `text[char_start:char_end] == evidence_text` holds exactly, which is what lets verify() and the UI's paragraph highlight be precise rather than approximate — 04 §3
- 2026-09-12 — `evidence_id` is `ev_` + sha1 of (doc_id, paragraph_index, branch_id, stance, normalized claim_text, passage), so the same finding recorded twice collapses — 02 pins only `doc_id`'s format. The key deliberately includes stance and claim_text: hashing the passage alone made a `contradicts` item over a sentence already cited as `supports` silently return the earlier item, suppressing contested detection while telling the agent its evidence was recorded — 02 §2.4, 04 §4
- 2026-09-12 — SPEC READING: 04 §4's "excluded from `supported` status unless the later document lacks the passage" is implemented as: exclude when the superseding document still CONTAINS the passage (the old document is then a stale citation for current text), keep when it does not (the old document is the only place that text exists). The predicate reads the later document's own text via within.load_text rather than inferring from what agents happened to quote — inferring would call any clause nobody re-quoted "lacking", the opposite of the truth when a revision changed one paragraph — 04 §4
- 2026-09-12 — `supersession_edges` returns older doc_id -> newest doc_id per external id, not consecutive pairs — newest-wins is the question callers ask and stays well defined for three or more revisions and for two sharing a date, where consecutive pairing produced no edge and left the older of the two looking current — 04 §4
- 2026-09-12 — A claim whose only support is superseded reports `weak`, not `unresolved` — 04 §4 reserves `unresolved` for "no supporting evidence", and excluding superseded evidence from `supported` is not the same as it not existing — 04 §4
- 2026-09-12 — `governing_date` is taken only from supporting evidence AT the top source quality, so a vendor page's date is never reported as governing while a primary source carries the claim; if no item at that quality has a date the field stays None. Ties within the tier break to the later date — the date feeds 04 §7's currency metric and a misattributed one is worse than none — 04 §4, §7
- 2026-09-12 — 04 §4's third contradiction rule implemented: where a confident contradiction carries a later effective_date than the support, that date becomes governing_date and Claim.text gains a "[contradicted by a later source effective YYYY-MM-DD]" annotation — the spec says "the later date governs and the claim's text is annotated", and without it the claim reads as current while a newer source disagrees — 04 §4
- 2026-09-12 — `Claim.derived_from` stays empty at 1.5: 04 §4 lists the edge but nothing in this task derives one claim from another; it arrives with synthesis if at all — 04 §4, 09 §1.7
- 2026-09-12 — The claim graph is derived on demand, not persisted, against 04 §6's "graph edges: inside state.json" — RunRecord has no edge field and needs none: supersession follows from `documents` and superseded evidence from `evidence`, both persisted, so a reloaded record rebuilds identically and the two cannot drift apart. Claim ids are positional (c1..cn) over the evidence order — 04 §6, 02 §2.1
- 2026-09-12 — `build_citations` emits one citation per evidence item, not per (document, section) — 02 §2.7 gives Citation a single evidence_id and 04 §7 has the evaluators check [n] against the passage it names, so collapsing two passages from one section would leave the second sentence's [n] pointing at the first sentence's quote — 02 §2.7, 04 §7
- 2026-09-12 — `citation_label` uses an ASCII hyphen where 04 §5's example shows an em dash, and falls back to "effective <date>" when only an effective_date is known — the hyphen keeps citations readable in the Windows console that renders `make ask`, and calling an original effective date a revision would misdate the policy. Neither invents information, which is 04 §5's actual rule — 04 §5
- 2026-09-12 — `effective_dates_section` omits a cited document that states no date rather than listing it as unknown — 02 §2.7 does not say to omit, but a missing policy date is a critic finding (04 §2) and belongs in the critique, not in the section a reader scans for currency — 02 §2.7, 04 §2
- 2026-09-12 — 04 §3's `extract(doc_id, paragraph_indices, schema)` extractor-model batch alternative is NOT in 1.5, which docs/09 scopes to the three deterministic files; it lands with the sub-agent tools at 1.6 where its caller exists. Until then rule 6's "relevance is set by the extractor model" is unreachable and every item uses the 0.8 agent-authored default — 04 §3, 09 §1.5, §1.6

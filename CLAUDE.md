# PRIME Search

Agentic coverage-determination search (CMS CGM / GLP-1) for the Tavily (Nebius) Head of FDE
take-home. Specs live in `docs/`; the task list is `docs/09-implementation-plan.md`; the layout is
`docs/01` §10. Read the spec section for a component before building it.

## Commands
- `make setup` · `make smoke` · `make test` · `make ask Q="..."` · `make dev-api` · `make dev-ui` · `make bench` · `make gepa`
- Python: `uv run ...` (never bare `python`/`pip`). Node: `pnpm` in `ui/`.
- Tests: `uv run pytest tests/ -x -q`; run single files while iterating.

## Hard constraints
- Stack is LangChain/LangGraph + LangSmith + `langchain-tavily` + `langchain-nebius` only. No other LLM or search providers.
- `starter_agent.py` is NEVER copied into or committed to this repo. `prime_search/baseline.py` reproduces it (model `moonshotai/Kimi-K2.6`, its three-line system prompt, one `TavilySearch` tool).
- No PHI, no patient records, not even synthetic. Questions are about policy.
- Do not build anything in `docs/10-roadmap.md`.
- Never run GEPA on the `holdout` split.

## Conventions that differ from defaults
- Every `ChatNebius` is built in `prime_search/models.py`; every prompt is a `.md` in `prime_search/prompts/`; every Tavily call goes through `prime_search/primitives/`.
- Root RLM and critic use code-as-action (fenced Python/JSON parsed from text), NOT native tool calls — reasoning models on the Nebius endpoint may reject tool calls (`docs/01` §4).
- Evidence must be a verbatim passage validated against the fetched paragraph (`docs/04` §3). Snippets are never evidence.
- Pydantic schemas in `schemas.py` are the contract; changing one means updating `docs/02` in the same commit.
- Commits: `feat|fix|docs|eval|ui: <what>`, small and frequent.

## Model routing (defaults; fallbacks in `docs/01` §4)
root/critic `nvidia/nemotron-3-super-120b-a12b` · judge `deepseek-ai/DeepSeek-V4-Flash-0731` · sub-agents/extractor/evaluators `moonshotai/Kimi-K2.6` · fallbacks per role in `models.FALLBACKS` (`DeepSeek-V3.2` is no longer offered). `make smoke` decides; never switch silently.

## Workflow rules
- Every task ends with a check you can run (test, smoke, curl, bench row). Show the output, don't assert success.
- IMPORTANT: append one dated line to the Decision log in `docs/11-assumptions-and-approach.md` whenever you deviate from a spec, choose between alternatives, or find an assumption wrong. Same commit.
- At each `[G]` gate in `docs/09`, stop and show evidence; wait for the user.
- Before declaring a gate done, run `/spec-review` (fresh-context subagent reviews the diff against the spec).
- End every session with `/session-end`.
- When compacting, always preserve: current task id, list of modified files, test/smoke commands, open decision-log entries, and any fallback decisions.

# Day 1 — retrieval, workspace, agents

Interim log. `/session-end 1` writes the full session record; this file exists now
because `docs/09` §1.6 asks for a trace URL to be recorded in the build log, and a
trace URL is worth nothing once the terminal scrolls.

## Tasks completed

| Task | Commit | Check |
|---|---|---|
| 1.1 Scaffold | `6f4afec`, `79bfad0` (ui) | `make setup && make test` → 4 passed |
| 1.2 Config and models **[G]** | `2ce22e4`, fixes `48acedc` | `make smoke` → all 10 checks passed, no fallback applied |
| 1.3 Primitives | `b1e0333`, fixes `cddc751` | `fetch(L33822)` → 275 paragraphs, rev 2024-10-01 |
| 1.4 Workspace and schemas | `a8973fd` | sandbox blocks `open`/`__import__`; plan cell round-trips; timeout fires |
| (side) Model selection | `9cdbc3e` | `reports/model-selection.md`, 104 calls, $0.44 |
| 1.5 Evidence store and graph | `c412955` | contested, supersession, citation labels → 47 tests |
| 1.6 Search sub-agent | this commit | below |

## 1.6 — LangSmith traces

The `docs/09` §1.6 Check: on the task *"current LCD coverage criteria for therapeutic
CGM"*, the agent fetches L33822 and records ≥ 3 evidence items with verbatim passages
and dates.

    uv run --env-file .env pytest tests/test_search_agent_live.py -m live -q -s

Passing run, 2026-09-12:

- <https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a09855-9111-7bf3-a959-1a6383853518/run/01a09855-9111-7bf3-a959-1a6383853518>

Recorded evidence from that run:

```
[supports] p70   2024-10-01  'The beneficiary for whom a CGM is being prescribed, to improve glycemi…'
[supports] p71   2024-10-01  'The beneficiary is insulin-treated; or,'
[context ] p145  2024-10-01  'Revision Effective Date: 10/01/2024'
```

All three verbatim (`store.verify() == []`), all three dated, one `context` date item
per `docs/03` §4 rule 4.

Earlier trace from the same check, kept because it shows the failure that led to the
`workspace.py` fix below — the agent fetched L33822, then `search_within` refused the
document it had just fetched, and it burned the budget retrying:

- <https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a09842-1378-7163-9a65-4a58d31ce5e5/run/01a09842-1378-7163-9a65-4a58d31ce5e5>

## Two findings from Day 1 worth carrying forward

**`docs/01` §4's fallback ladder pointed at models that no longer exist.** Five of six
`FALLBACKS` entries named `deepseek-ai/DeepSeek-V3.2`, absent from the live catalog, so
every fallback would have raised model-not-found the first time a role needed rescuing.
Fixed in `9cdbc3e` with V4-line replacements chosen on measured per-role results, plus a
`live` test that asserts every routed id exists in the catalog.

**The 8-call cap makes the §1.6 check marginal.** Over five runs, four recorded ≥ 3
evidence items and one recorded 2. The minimum path spends 3 calls before any evidence
exists, and L33822 states five separate criteria that rule 3 correctly wants recorded
separately. The cap is left at the spec's default — in the real graph `dispatch` fans out
up to 6 sub-agents each with their own 8 calls — but `MAX_TOOL_CALLS` is a decision worth
revisiting at 1.7 once `dispatch` divides the budget for real.

## Answer-key drift confirmed (for task 2.1)

L33822's current revision is **10/01/2024 (R16)**. The draft answer keys still expect
2023-04-16 (R12). `docs/08` §2 anticipated this; task 2.1 has to correct the keys.

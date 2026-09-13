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
| 1.6 Search sub-agent | `c743ad8`, fixes `10f90fc` | 3 verbatim evidence items on L33822 |
| 1.7 Root plan, graph, synthesis **[G]** | this commit | below |

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

## 1.7 [G] gate - both modes, both traces

`make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"`

- status `budget_exhausted` (150k token budget), 58.0s, 4 sub-agents, 12 evidence, 12 claims,
  13 documents, confidence 0.944
- trace: <https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a098ef-202b-7cb3-99ad-37f3ab54f226/run/01a098ef-202b-7cb3-99ad-37f3ab54f226>

The answer carries the "Effective dates relied on" section and a numbered Sources list with
publisher and tier, every entry `primary_policy` on cms.gov, and the answer is the conservative
one: coverage for a non-insulin type 2 beneficiary only through the problematic-hypoglycemia
pathway, with the criteria it could not fully extract listed under Unknowns rather than filled in
from memory.

Same question, `ARGS="--mode baseline"`:

- status `completed`, 24.7s, 2 searches, 0 documents, 0 evidence, 5 URL-parsed citations
- trace: <https://smith.langchain.com/o/86cf0bc5-3739-42dc-995c-3d23f39fde62/projects/p/0c5b863c-4be5-4833-b459-bde680d399c8/trace/01a098f0-5542-7682-8e02-e47fdf391b73/run/01a098f0-5542-7682-8e02-e47fdf391b73>

The baseline reaches a similar conclusion faster and cites AARP, DiaTribe, TCOYD, doko.md and
medicare.org - no primary document, no passage behind any citation, no date on any source. That
contrast is the thing the Day 2 bench measures, and it is visible in one run each.

## Seven defects the live 1.7 runs found that the tests did not

Every one of these passed a green offline suite first. They are listed because the pattern matters
more than the individual bugs: each was invisible to a test that checked the shape of a value
rather than its delivery.

1. **A console encoding error killed a finished run.** U+202F could not be encoded to cp1252; the
   exception left the token callback, left the stream, entered the `invoke` fallback, left that,
   and ended a run that had already gathered all ten of its evidence items. Token sinks are now
   wrapped and abandoned after the first failure.
2. **Concurrent sub-agents tore the event log.** 150 emits became 134 lines; `replay()` drops an
   unparseable line silently, so the 2.4 UI would have lost events invisibly. `events._append`
   now writes under the lock.
3. **Two citation formats bypassed the docs/03 §8 check.** Kimi-K2.6 wrote `【3】` in one run and
   `【1†L1-L3】` in the next; `\[(\d+)\]` matched neither, so unmapped citations were neither
   checked nor dropped and the §8 guarantee was off for those runs.
4. **The baseline streamed tool messages into its own answer.** A 4 KB Tavily JSON blob landed in
   `body_markdown` and produced ten "citations" from URLs the model had not read.
5. **Terminal events were emitted after `unsubscribe()`.** A subscriber received
   `['run.started', 'token']` and never saw the answer, the usage or the run-finished marker it
   was supposed to close on - found by the spec reviewer, reproduced as a test, then fixed.
6. **A live answer cited seven sources and listed nine.** The model lists every passage it is
   shown; the Sources section is now derived from the citations the body actually uses.
7. **The synthesis prompt printed each section twice** ("...§CODING GUIDELINES, revision effective
   2025-02-18, §CODING GUIDELINES") because `citation.label` already contained it - and a live
   answer copied that shape straight into its Sources list.

`tests/test_event_contract.py` was written in response to 5: it pins the docs/02 §4 table by
reading emitted payloads, and asserts subscriber delivery and ordering, not just payload keys.

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

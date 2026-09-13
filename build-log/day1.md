# Day 1 — retrieval, workspace, agents

Session record for Day 1 of the `docs/09` plan. Written by `/session-end 1`.

Day 1 built the retrieval and agent layers and ended at the **1.7 `[G]` gate**: a coverage
question now becomes a cited answer from primary sources, and the same question run through the
starter-equivalent baseline produces its answer, both traced.

All eight Day 1 tasks are complete. `docs/09` marks 1.8 "[start; finish Day 2 morning]"; it
finished today, so Day 2 opens on task **2.1**, the SearchBench validation gate.

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
| 1.7 Root plan, graph, synthesis **[G]** | `1fe2390`, fix `d9e9526` | both gate answers + traces, below |
| 1.8 SearchBench sources fetch | `51ff4fc` | 14 documents fetched; 47 drift flags across 23 of 30 records, below |

Suite at end of day: `make test` → **405 passed, 10 deselected** (the 10 are `live`-marked).
`uv run ruff check prime_search/ tests/` → clean.

## Gates passed

**1.2 `[G]` — config and models.** `make smoke`, all 10 probes green, no fallback applied. The
gate also produced the finding that `docs/01` §4's fallback ladder named a model the live catalog
no longer offers (see Findings below).

**1.7 `[G]` — end-to-end answer.** Evidence in the two sections below: both answers in full, both
LangSmith traces, and the run directories they wrote.

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

## Eight defects the live 1.7 runs found that the tests did not

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

8. **The trace looked empty.** The root run and LangGraph's own graph run were both named
   `prime_search`, so the trace's only visible child was an identically named row and
   `understand`/`plan`/`synthesize` sat a level below it. The graph run is now named `graph`:

   ```
   prime_search          <- root run, carries the docs/06 §2 tags and metadata
   └── graph             <- LangGraph's run for the compiled graph
       ├── understand
       ├── plan
       ├── dispatch
       │   └── _fan_out
       ├── search_agent
       │   └── search_agent:b1
       ├── collect
       ├── judge
       ├── critic
       └── synthesize
   ```

   docs/06 §1 draws the nodes directly under the root; the `graph` level is LangGraph's and
   cannot be suppressed, so the trace is one level deeper than the diagram. `search_agent:bN`
   likewise hangs under its LangGraph node run rather than sitting beside `collect`.

`tests/test_event_contract.py` was written in response to 5: it pins the docs/02 §4 table by
reading emitted payloads, and asserts subscriber delivery and ordering, not just payload keys.

## 1.8 — SearchBench source drift

`uv run --env-file .env python -m eval.searchbench.fetch_sources` (`docs/08` §2 step 2). Full
report: `reports/searchbench-drift.md`. Per-record worksheets for the task 2.1 validation pass:
`data/searchbench/review/<record_id>.md`.

**14 governing documents fetched, 47 flags across 23 of 30 records.** The dataset is untouched —
a test asserts the `.jsonl` is byte-identical after every check runs, because `docs/08` §1 makes
answer keys data with provenance and correcting them is task 2.1's job.

The finding `docs/08` §2 predicted, and then some:

- **L33822 is on 2024-10-01, A52464 on 2025-02-18**; the drafts assert 2023-04-16. Reported as a
  currency note rather than as drift, because a claim *about* the 2023 revision is still correct —
  that row is in the revision history.
- `cgm-elig-002` requires **"level 2"/"level 3" from L33822; neither phrase is in the LCD**, which
  defers the hypoglycemia definition to article A52464.
- `cgm-code-001` calls **K0553/K0554 retired; they appear 19 and 16 times** in the live A52464.
- The Wegovy label uses **MACE**, not the spelled-out phrase the key requires.
- **12 of the 14 documents have no canonical id** — they are prose descriptors like "CMS/HHS 2025
  announcements", which resolved to a CMS newsletter index. Every one is marked a search guess.

Two findings about the dataset itself, both for task 2.1:

- **Six records break `docs/08` §4–§5 authoring rules**: `oos-002` and `oos-003` carry
  `required_evidence` (forbidden for out-of-scope), `oos-003` has no `expected_scope_warning` and
  one required claim where §5 wants 2–6, and two change-detection keys date nothing.
- **`oos-002`'s question embeds a synthetic patient record** — a first name, a date of birth and
  an A1c. CLAUDE.md is unconditional ("no patient records, not even synthetic") and `docs/08` §8
  excludes patient-level inputs. The record's purpose — testing that the system declines
  individual questions — survives rephrasing at policy level. The question is redacted wherever
  this task writes it, and rewriting it is 2.1's.

### Six checks that were wrong before they were right

A drift check that reports drift where there is none is worse than no check: the human acting on
it edits a correct answer key into a wrong one. Most of these came from `/spec-review 1.8`.

1. **Flags computed against another record's document.** `_resolution_for` looked the evidence up
   in the run-wide map, so `glp1-path-001` was told "medically accepted indication" — the correct
   statutory term — was missing from a fact sheet it never names.
2. **A correct claim reported as drift.** "The non-insulin pathway was added by the revision
   effective April 16, 2023" is right; the flag said "draft expected 2023-04-16".
3. **Month-precision dates invisible.** All three date patterns required a day, so "the November
   2024 proposed rule" read as dateless and the date check skipped the highest-risk records.
4. **`forbidden_claims` silently inert for 9 of 10 records** — they are plain sentences with
   nothing quotable — while the report's legend implied the category had been evaluated.
5. **Revision-history matches read as live text.** CMS quotes what it removes, so "three or more"
   appears in an LCD that no longer requires it. Then the mirror: scoping to "anything before the
   match on this line" treated text the same row *added* as retired.
6. **Patient detail copied into two new committed files** while being flagged in a third.

`reports/searchbench-drift.md` now separates "this key is wrong" from "we could not find the
document" and from "this could not be checked automatically — verify by hand".

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

**Revisited at 1.7, and the cap is not the binding constraint.** With four sub-agents each
holding 8 calls, the gate run recorded 12 evidence items across 13 documents. What ran out
first was the *run's* 150k token budget (status `budget_exhausted` at 58s of a 180s limit),
and deep reads were at 8 of 10. `MAX_TOOL_CALLS` stays at 8; `max_tokens` and
`max_deep_reads` are the numbers to look at when the judge starts requesting second rounds
at 2.2.

## Decisions made today

The full log is `docs/11-assumptions-and-approach.md` — **184 dated entries**, 64 of them from
1.7 and 1.8. These are the ones that change how the code should be read; everything else there is
detail.

**Where the implementation deviates from a spec, deliberately**

- `dispatch` is a node **plus** a conditional edge. `docs/03` §1 draws it returning `Send`s, but in
  LangGraph only a routing function may. The node does the budget arithmetic; `_fan_out` sends.
- The `Send` payload carries `ws` and `store` beyond §1's `{task, run_id, budget}` — the sub-agent
  needs somewhere to fetch into and somewhere to record against.
- Fan-out branches return **only** `task_results` and `events`; `PrimeState.ws` has no reducer.
- One `RUN_LOCK` in `workspace.py`, shared with `search_agent.py` and `evidence/store.py`, because
  the deep-read counter is check-then-incremented across two of them.
- Synthesis **computes** `citations`, `effective_dates`, `claims` and `contradictions` from the
  claim graph and asks the model only for the prose. A fabricated revision date is the failure
  this system exists to prevent, and those fields are derivable.
- `baseline.py` uses a **raw `TavilySearch()`**, against CLAUDE.md's "every Tavily call goes
  through `primitives/`". `docs/03` §9 says "nothing else is added, so the comparison is fair";
  our cache and tier classification would make the control arm better than the thing it controls
  for. The other two CLAUDE.md conflicts in §9 resolve the other way (model from `models.py`,
  prompt from a `.md`).
- `RunRecord` is written at **every node boundary** (`docs/06` §4) rather than start and end
  (`docs/02` §2.1); the file is rewritten, so the stricter reading satisfies both.
- The LangGraph run for the compiled graph is named `graph`, so the trace is one level deeper than
  `docs/06` §1's diagram — that level is LangGraph's and cannot be suppressed.
- `render.py` is a new top-level module not in `docs/01` §10's layout.

**Where a spec was silent and something was authored**

- **`Answer.confidence`** has no derivation anywhere. Defined in `synthesizer.confidence_for`:
  mean confidence of supported claims, ×0.8 with no primary-tier document, ×0.8 with an
  unresolved branch, floor 0.05; all-contested reports 0.4; no claims reports 0.0.
- **The GLP-1 strategy card.** `docs/03` §3 requires one per domain and quotes only the CGM card.
  Written as *where to look* (Part B vs Part D, the statutory exclusion text, label indication vs
  coverage) rather than *what is true*, so it does not hand the model answers the bench measures.
  A test asserts it contains no "is covered"/"is not covered".
- `docs/03` §3's `time_range="year"` change-detection rule lands on the `SearchTask`, because
  `Branch` has no such field.

**Where an assumption turned out to be wrong**

- `docs/01` §4's fallback ladder named `deepseek-ai/DeepSeek-V3.2` for five of six roles — a model
  the live catalog no longer offers. Every fallback would have raised model-not-found the first
  time a role needed rescuing.
- `docs/01` §3 contradicted itself on prefixed vs unprefixed credentials; resolved with
  `AliasChoices`.
- `langchain-core` 1.6's `tracing_v2_enabled` never populates `latest_run`, so `get_run_url()`
  always raised. Replaced with an explicit `RunTree`.
- L33822's current revision is **10/01/2024 (R16)**, not the 2023-04-16 the draft answer keys
  expect. Task 2.1 has to correct the keys.

## Open issues

1. **`PRIME_MODELS__SUB` in `.env` is inert.** It should be `PRIME_MODELS__SUBAGENT`. The guard
   added at 1.2 fires a `RuntimeWarning` on every run. No behavioural harm today — the role falls
   back to the same model the line was trying to set — but it is silently doing nothing. **Only
   you can fix this; the tooling cannot read or write `.env`.**
2. **Judge/extractor/evaluator model switch is still unapplied.** `reports/model-selection.md`
   recommends `deepseek-ai/DeepSeek-V4-Flash-0731` for these three roles; it was not applied
   because it needs your approval. Decide before the Day 2 bench, so the numbers are measured on
   one routing.
3. **The draft answer keys are not usable yet.** 47 flags across 23 of 30 records; see the 1.8
   section and `reports/searchbench-drift.md`. Task 2.1 corrects them. Until `validated_by` and
   `as_of` are set, a bench run measures the author's memory rather than the system — the
   `AnswerKey.is_validated` property exists so the 2.6 runner can refuse.
4. **`oos-002` carries a synthetic patient record** in its question text, against CLAUDE.md's
   "not even synthetic" and `docs/08` §8. Rewrite it at policy level during 2.1; the record's
   purpose survives. It is redacted everywhere 1.8 writes it, but the dataset still holds it.
5. **Six records break `docs/08` §4–§5 authoring rules** (out-of-scope records with
   `required_evidence`, a missing scope warning, a 1-claim key, two dateless change-detection
   keys). All reported, none fixed — 1.8 may not edit the dataset.
6. **`docs/05` §1 says `domain` is `cgm | glp1 | cross | out_of_scope`; the data uses `other`.**
   The model follows the data. Settle it in one place during 2.1, before 2.2's evaluators read it.
7. **Judge and critic are pass-through stubs.** `docs/09` §1.7 specifies this, but it means
   `max_rounds` is never exercised and every run is a single round until 2.2/2.3.
8. **The deep-read budget is the binding constraint, not the tool-call cap.** The gate run spent 8
   of 10 deep reads and hit the 150k token budget before the search budget. Worth revisiting the
   `fast`/`deep` budgets once the judge can request a second round.
9. **`Read(../starter_agent.py)` in `.claude/settings.json` is a relative pattern** and does not
   match an absolute path. Widen to `Read(**/starter_agent.py)` if a hard block was intended. The
   file is not tracked and nothing was copied from it beyond the three-line prompt and the
   constructor arguments `docs/03` §9 requires.
10. **`extract(doc_id, paragraph_indices, schema)`** (`docs/04` §3) is still deferred — twice now.
   Consequence: rule 6's extractor-set `relevance` is unreachable and every item keeps the 0.8
   agent-authored default, which rule 6 sanctions. Revisit at 2.2 or move to the cut list.

## Fallbacks in effect

**None.** Every role is on its `docs/01` §3 default:

```
root       nvidia/nemotron-3-super-120b-a12b
critic     nvidia/nemotron-3-super-120b-a12b
subagent   moonshotai/Kimi-K2.6
judge      moonshotai/Kimi-K2.6
extractor  moonshotai/Kimi-K2.6
evaluator  moonshotai/Kimi-K2.6
baseline   moonshotai/Kimi-K2.6      (starter default; do not change)
```

No `fallback:` tag appeared on either gate run, so neither the planner's structured-output rung
nor its default-plan rung fired. The repaired ladder in `models.FALLBACKS` is available but has
never been used; applying one still requires asking first.

Budgets: deep `30/20/10 searches/fetches/deep-reads, 6 agents, 3 rounds, 150k tokens, 180s`;
fast `3/2/10, 1 agent, 1 round, 30s`.

## Resume tomorrow

```bash
cd C:/Users/ujjwa/Claude/Projects/tavily/prime-search

make setup                 # if the venv is cold
make smoke                 # confirm all 10 probes still pass before trusting a bench number
make test                  # expect 405 passed, 10 deselected

# Day 1 is complete. Start at 2.1 - a [G] gate, and the one task that is yours:
#   /validate-bench        # yours to invoke
#
# 2.1 is docs/08 §2 step 3: read each worksheet, correct the key, set as_of and
# validated_by, then `uv run python -m eval.searchbench.sync` (which 2.1 also builds).
#   worksheets: data/searchbench/review/<record_id>.md      (30, one per record)
#   what to fix: reports/searchbench-drift.md               (47 flags, high risk first)
#   re-run the fetch after editing keys, to confirm the flags clear:
uv run --env-file .env python -m eval.searchbench.fetch_sources
uv run --env-file .env python -m eval.searchbench.fetch_sources --only cgm  # one domain
uv run python -m eval.searchbench.fetch_sources --offline                   # no network, no writes

# the servers, once 2.4/2.5 exist:
make dev-api               # FastAPI + SSE   (task 2.4)
make dev-ui                # Next.js         (task 2.5)

# re-run either arm of the 1.7 gate at any time:
make ask Q="Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
make ask Q="..." ARGS="--mode baseline"
```

**Next task id: 2.1** — `docs/09` §2.1, a `[G]` gate: 30 records validated, splits assigned.
`/validate-bench` is yours to invoke; tell me when you start and I will pick up 2.2 behind it.

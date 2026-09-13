"""The search sub-agent (docs/03 §4): one independent agent per `SearchTask`.

Five tools over the primitives, a tool-call cap, and a `TaskResult` that never
carries a document back to the root — only ids (docs/03 §4).

Three things decide the shape of this module:

* **`TaskResult` is assembled from the tool-call log, not asked for.** Kimi-K2.6 went
  2/3 on native structured output in `make smoke`, and `queries_issued`,
  `documents_fetched` and `evidence_ids` are facts this module already knows exactly.
  Only `summary` and `unresolved` come from the model's last message.
* **Tool errors are text, never exceptions** (docs/01 §9): a Tavily failure, an
  unknown doc_id and a rejected passage all come back as something the model can act
  on, and the call still counted against the budget. The one exception is
  `BudgetExceeded`, which exists precisely to end the loop.
* **Returns are shaped for a context window.** Snippets, BM25 passages and section
  lists are all clipped. A 52 KB ICD-table paragraph arriving whole would cost more
  context than the task instruction.
"""

from __future__ import annotations

import re
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from langsmith import get_current_run_tree

from prime_search import events
from prime_search.config import Budget, get_settings
from prime_search.evidence.store import EvidenceRejected, EvidenceStore
from prime_search.models import subagent_model, token_usage
from prime_search.primitives import tavily
from prime_search.primitives.sources import host_of
from prime_search.prompts import render
from prime_search.schemas import SearchTask, TaskResult, Usage
from prime_search.tracing import get_logger, trace_run
from prime_search.workspace import RUN_LOCK, DeepReadBudgetExceeded, Workspace

# docs/03 §13: "Sub-agent exceeds its tool-call cap (default 8)". A module constant
# rather than a Budget field: Budget is serialized into SearchPlan, RunRequest and
# every RunRecord and is pinned verbatim in docs/01 §3, and no other component reads
# or divides a tool-call count. 1.7 passes a smaller value for `fast` depth.
MAX_TOOL_CALLS = 8

# Context guards. None are specified; each is a return value that would otherwise
# dominate the agent's context.
MAX_SNIPPET_CHARS = 240  # Tavily "advanced" snippets run 400-600 chars
MAX_PASSAGE_CHARS = 700  # within.py windows go up to 2000
MAX_SECTIONS = 25  # L33822 has ~30 headings
MAX_REJECTION_CHARS = 1200  # the paragraph handed back after a verbatim failure
MAX_SUMMARY_CHARS = 600  # docs/02 §2.3: "2-3 sentences for the tree view"

# prompts/search_agent.md is one file (frozen by docs/05 §5) split into the static
# system prompt and the per-task kickoff, so the task is the last thing the model
# reads without duplicating it into a second file.
PROMPT_SPLIT_MARKER = "<!-- task -->"

SUMMARIZE_AFTER_CAP = (
    "You have no tool calls left ({reason}). Do not call any more tools.\n"
    "Write your final answer now: 2-3 sentences on what you established and the "
    "evidence you recorded, then a final line starting with 'Unresolved:' naming what "
    "you could not confirm. Write unresolved items for a patient or clinician: say what "
    "could not be confirmed. Never mention tool calls, budgets, limits or doc_ids; name a "
    "document by its title or publisher."
)

_LIMITS = {"searches": "max_searches", "fetches": "max_fetches", "deep_reads": "max_deep_reads"}
# `ws.usage` is shared by every task dispatched in the same superstep, and a single
# AIMessage can carry several tool calls, so check-then-increment has to be atomic on
# both the task and the run side. The lock lives in workspace.py and is shared with
# `Workspace.search_within`, which charges the other half of the deep-read counter —
# a second lock here would leave that pair unsynchronized while looking guarded.
_LOCK = RUN_LOCK

_log = get_logger(component="search_agent")

__all__ = ["MAX_TOOL_CALLS", "BudgetExceeded", "ToolContext", "build_tools", "run_search_agent"]


class BudgetExceeded(RuntimeError):
    """docs/03 §13: raised by a tool wrapper when no further call can succeed.

    Raised rather than returned as text precisely because it must end the agent loop:
    the caller catches it, asks the model to summarize what it has, and sets
    `TaskResult.unresolved` to `reason`.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class ToolContext:
    """One task's live state: budgets, counters and the `TaskResult` in progress.

    The five tools are closures over this, which is why nothing about a task has to
    travel through the agent's message state — and why the subgraph can return ids
    only (docs/03 §4).
    """

    ws: Workspace
    store: EvidenceStore
    task: SearchTask
    budget: Budget  # this task's slice of the run (docs/03 §1's dispatch)
    max_tool_calls: int = MAX_TOOL_CALLS
    run_dir: Path | None = None

    calls: int = 0
    queries: list[str] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    @property
    def calls_left(self) -> int:
        return max(0, self.max_tool_calls - self.calls)

    def pressure(self) -> str | None:
        """A nudge when the calls are nearly gone and nothing is recorded yet.

        Measured on the live check: the agent spent all 8 calls on 2 searches, 2
        fetches and 4 deep reads and recorded no evidence at all. The cap is the
        spec's (docs/03 §13) and the workflow does fit inside it, but only if the
        agent stops exploring in time — and it cannot see the count unless a tool
        says so.
        """
        if self.calls_left > 3:
            return None
        if not self.evidence_ids:
            return (
                f"only {self.calls_left} tool calls left and you have recorded no "
                "evidence yet — call add_evidence now with the best passage you have "
                "already seen, before you run out."
            )
        return (
            f"only {self.calls_left} tool calls left ({len(self.evidence_ids)} evidence "
            "items so far) — stop reading and record any remaining passages now."
        )

    def begin(self, name: str) -> None:
        """Count one tool call — docs/03 §13's cap, and docs/01 §9's rule that a
        failed call still counts, which is why this runs before any work."""
        with _LOCK:
            if self.calls >= self.max_tool_calls:
                raise BudgetExceeded(
                    f"tool-call cap reached ({self.max_tool_calls} calls) at {name}()"
                )
            self.calls += 1

    def charge(self, kind: str) -> str | None:
        """Charge one `searches`/`fetches`/`deep_reads` unit.

        Two exhaustions, handled deliberately differently. This *task's* slice running
        out returns a refusal string, because the agent can still do useful work with
        the documents it already has. The *run's* budget running out raises
        `BudgetExceeded`, because no call by anyone can succeed after that and
        continuing only burns context.
        """
        limit = _LIMITS[kind]
        with _LOCK:
            used, allowed = getattr(self.usage, kind), getattr(self.budget, limit)
            if getattr(self.ws.budget_remaining(), limit) <= 0:
                raise BudgetExceeded(f"the run's {limit} budget is exhausted")
            if used >= allowed:
                return (
                    f"this task's {kind} budget is used up ({used}/{allowed}); no more "
                    f"{kind} for this task — work with what you already have."
                )
            setattr(self.usage, kind, used + 1)
            if kind != "deep_reads":
                # ws.search_within increments ws.usage.deep_reads itself, so charging
                # the run side here too would double-count exactly that resource.
                setattr(self.ws.usage, kind, getattr(self.ws.usage, kind) + 1)
        return None

    def charge_run_deep_read(self) -> None:
        """Count a *failed* deep read against the run.

        `ws.search_within` increments the run side only on success, so a deep read that
        raised cost the task but not the run — while a failed search or fetch costs
        both. docs/01 §9: "the budget still counts the call".
        """
        with _LOCK:
            self.ws.usage.deep_reads += 1

    def emit(self, type: str, payload: Any) -> None:
        events.emit(self.ws.run_id, type, payload)

    def error_event(self, tool_name: str, message: str, summary: str) -> None:
        """docs/02 §4's `error` event at severity "warning": a retrieval miss the agent
        works around, not a failed run. Retrieval failures only — an evidence rejection
        is a normal correction loop, not an event."""
        events.emit_error(
            self.ws.run_id,
            f"{tool_name}: {message}",
            f"search_agent:{self.task.branch_id}",
            severity="warning",
            task_id=self.task.task_id,
            summary=summary,
        )

    def page_summary(self, doc_id: str) -> str:
        """The reader's words for an unreadable page: which site, never the extractor's."""
        document = self.ws.documents.get(doc_id)
        host = host_of(document.url) if document is not None else ""
        return f"Couldn't read a page from {host}" if host else "Couldn't read a page"


# --- the five tools (docs/03 §4) --------------------------------------------------


def build_tools(ctx: ToolContext) -> list[BaseTool]:
    """The five tools of docs/03 §4, bound to one task's context.

    The docstrings are the tool descriptions the model reads (docs/03 §11's seed
    checklist asks for them), so they state the rule, not just the signature.
    """

    @tool
    def search(
        query: str,
        include_domains: list[str] | None = None,
        time_range: str | None = None,
    ) -> dict[str, Any]:
        """Web search for candidate documents. Returns up to 8 results, each with a
        doc_id, url, title, snippet, source tier and date hint.

        Results are candidates only: a snippet is never evidence. Call fetch(doc_id)
        on the ones that look authoritative before quoting anything.

        Args:
            query: A specific query. Name the policy, code or condition ("LCD
                therapeutic continuous glucose monitor coverage criteria"), not the
                whole question.
            include_domains: Restrict to these domains, e.g. ["cms.gov"] for Medicare
                policy or ["fda.gov"] for labels. Use it whenever you want primary
                sources.
            time_range: "year" or "month" to find recent changes. Omit for current
                policy, which is often years old and still in force.
        """
        ctx.begin("search")
        refused = ctx.charge("searches")
        if refused:
            return {"error": refused, "tool_calls_left": ctx.calls_left}
        ctx.queries.append(query)  # issued is issued, whether or not it returned rows
        try:
            result = tavily.search(
                query,
                include_domains=include_domains or None,
                time_range=time_range or None,
                docs=ctx.ws.documents,  # registers every hit as snippet_only
            )
        except Exception as exc:  # docs/01 §9: never raise at the model
            ctx.error_event("search", f"{type(exc).__name__}: {exc}", "A web search failed")
            return {
                "error": f"search failed: {type(exc).__name__}: {exc}",
                "tool_calls_left": ctx.calls_left,
            }
        ctx.emit("search", result.event(ctx.task.task_id))
        if result.error:
            ctx.error_event("search", result.error, "A web search returned no usable results")
            return {
                "error": result.error,
                "hint": "reformulate the query once; do not repeat it verbatim",
                "tool_calls_left": ctx.calls_left,
            }
        return {
            "query": result.query,
            "cached": result.cached,
            "n": result.n_results,
            # as_dict() is exactly docs/03 §4's six keys; only the snippet is trimmed,
            # and it is a preview, never a quotable passage.
            "results": [
                {**hit.as_dict(), "snippet": _clip(hit.snippet, MAX_SNIPPET_CHARS)}
                for hit in result.hits
            ],
            **_budget_hint(ctx),
        }

    @tool
    def fetch(doc_id: str) -> dict[str, Any]:
        """Fetch a document's full text so you can quote it. Returns its title, tier,
        document type, external id (e.g. L33822), effective and revision dates,
        section headings and paragraph count.

        You must fetch a document before search_within or add_evidence will work on
        it. Fetch each document once: a repeat fetch of the same doc_id still costs a
        tool call and a fetch from your budget, even though the text is cached. A page
        that could not be read is not retried: fetching it again returns the same error.

        Args:
            doc_id: A doc_id from a previous search result.
        """
        ctx.begin("fetch")
        with _LOCK:
            failed_before = doc_id in ctx.ws.failed_fetches
        if failed_before:
            # Another branch, or an earlier round, already failed on this page. The
            # live run that prompted this tried one unreadable page in two rounds and
            # showed the same miss twice. No fetch is charged and no event repeats it.
            return {
                "doc_id": doc_id,
                "error": "this page could not be read earlier in this run; it is not retried",
                "hint": "try a different source for the same fact",
                "tool_calls_left": ctx.calls_left,
            }
        refused = ctx.charge("fetches")
        if refused:
            return {"error": refused, "tool_calls_left": ctx.calls_left}
        try:
            result = tavily.fetch(doc_id, docs=ctx.ws.documents, run_dir=ctx.run_dir)
        except Exception as exc:  # an unknown doc_id raises ValueError
            ctx.error_event("fetch", f"{type(exc).__name__}: {exc}", ctx.page_summary(doc_id))
            return {
                "error": f"{type(exc).__name__}: {exc}",
                "hint": "search first; doc_ids only exist for search results",
                "tool_calls_left": ctx.calls_left,
            }
        document = result.document
        if not document.is_fetched:
            with _LOCK:
                ctx.ws.failed_fetches[doc_id] = result.error or "no text extracted"
            ctx.error_event("fetch", result.error or "no text extracted", ctx.page_summary(doc_id))
            return {
                "doc_id": doc_id,
                "error": result.error or "no text could be extracted from this page",
                "hint": "try a different source for the same fact",
                "tool_calls_left": ctx.calls_left,
            }
        ctx.fetched.append(document.doc_id)
        ctx.emit("fetch", result.event(ctx.task.task_id))
        payload: dict[str, Any] = {
            "doc_id": document.doc_id,
            "title": document.title,
            "tier": document.source_tier,
            "publisher": document.publisher,
            "doc_type": document.doc_type,
            "external_id": document.document_id_external,
            "effective_date": _iso(document.effective_date),
            "revision_date": _iso(document.revision_date),
            "paragraph_count": document.paragraph_count,
            "sections": _clip_list(result.sections, MAX_SECTIONS),
            "cached": result.cached,
            **_budget_hint(ctx),
        }
        if result.error:  # a thin extract is usable, but say so (docs/11 R2)
            payload["warning"] = result.error
        return payload

    @tool
    def search_within(doc_id: str, query: str, k: int = 5) -> dict[str, Any]:
        """Find the passages of a fetched document that match a query. Returns up to k
        paragraphs with their paragraph_index and text — these indices and this text
        are what add_evidence expects.

        Use it to locate the coverage criteria, the codes or the revision date inside
        a long policy document instead of reading the whole thing.

        Args:
            doc_id: A doc_id you have already fetched.
            query: Words you expect in the passage ("revision effective date",
                "coverage indications insulin", "HCPCS code frequency").
            k: How many paragraphs to return (default 5; keep it small).
        """
        ctx.begin("search_within")
        refused = ctx.charge("deep_reads")
        if refused:
            return {"error": refused, "tool_calls_left": ctx.calls_left}
        try:
            # Delegate to the workspace so the deep read is counted once, in the
            # object that owns the budget (docs/02 §3).
            passages = ctx.ws.search_within(doc_id, query, k=max(1, min(k, 8)))
        except KeyError as exc:
            # The document is not in the workspace at all, so ws.search_within raised
            # before charging the run. The task was charged; keep the two in step.
            ctx.charge_run_deep_read()
            return {"error": str(exc), "tool_calls_left": ctx.calls_left}
        except DeepReadBudgetExceeded as exc:
            # The pre-check in charge() normally gets there first, so this is the race
            # under a parallel fan-out, where the workspace's own re-check bounds the
            # overshoot at one. Matched by type: the same method raises ValueError for
            # an unreadable path, a snippet-only document and drifted offsets, and
            # telling them apart by looking for "budget" in the message held only until
            # someone reworded one.
            raise BudgetExceeded(str(exc)) from exc
        except ValueError as exc:
            return {"error": str(exc), "tool_calls_left": ctx.calls_left}
        except Exception as exc:
            # An OSError if the text file was removed or locked, say. An unguarded
            # raise here escaped the whole agent; the model can route around a missing
            # document, so it comes back as text. Already charged by ws.search_within.
            return {"error": f"{type(exc).__name__}: {exc}", "tool_calls_left": ctx.calls_left}
        if not passages:
            return {
                "doc_id": doc_id,
                "passages": [],
                "hint": "no paragraph matched; try other words from the document",
                "tool_calls_left": ctx.calls_left,
            }
        return {
            "doc_id": doc_id,
            # Offsets and BM25 scores are dropped: add_evidence needs only the index,
            # and the store recomputes offsets from the document's own bytes.
            "passages": [
                _passage_payload(passage)
                for passage in passages
            ],
            **_budget_hint(ctx),
        }

    @tool
    def add_evidence(
        doc_id: str,
        paragraph_index: int,
        claim_text: str,
        evidence_text: str,
        stance: str = "supports",
        confidence: float = 0.8,
    ) -> dict[str, Any]:
        """Record one verbatim passage as evidence for one atomic claim.

        The passage must be copied exactly from the paragraph you name — copy it from
        search_within output, do not retype or paraphrase. If it does not match, the
        tool returns the real paragraph so you can quote it correctly.

        Args:
            doc_id: A doc_id you have fetched.
            paragraph_index: The paragraph_index from search_within.
            claim_text: One atomic statement, at most 200 characters, e.g. "Medicare
                covers therapeutic CGM for beneficiaries treated with insulin". Not a
                summary of several things.
            evidence_text: The exact sentence or clause from that paragraph carrying
                the claim, at most 600 characters.
            stance: "supports", "contradicts" (this passage contradicts the claim), or
                "context" (dates, definitions, scope notes).
            confidence: 0-1, how strongly this passage supports the claim.
        """
        ctx.begin("add_evidence")
        try:
            item = ctx.store.add(
                doc_id=doc_id,
                branch_id=ctx.task.branch_id,  # the task owns it; never ask the model
                claim_text=claim_text,
                evidence_text=evidence_text,
                paragraph_index=paragraph_index,
                stance=stance,
                confidence=confidence,
            )
        except EvidenceRejected as exc:
            payload: dict[str, Any] = {
                "rejected": exc.reason,
                "tool_calls_left": ctx.calls_left,
            }
            if exc.paragraph_text:  # docs/04 §3 rule 2: hand the paragraph back
                payload["paragraph"] = _clip(exc.paragraph_text, MAX_REJECTION_CHARS)
            return payload
        except Exception as exc:
            return {
                "rejected": f"{type(exc).__name__}: {exc}",
                "tool_calls_left": ctx.calls_left,
            }
        if item.evidence_id not in ctx.evidence_ids:
            ctx.evidence_ids.append(item.evidence_id)
            ctx.emit("evidence", item)  # docs/02 §4's payload is the Evidence itself
        return {
            "evidence_id": item.evidence_id,
            "stance": item.stance,
            "effective_date": _iso(item.effective_date),
            "recorded_for_this_task": len(ctx.evidence_ids),
            "tool_calls_left": ctx.calls_left,
        }

    @tool
    def note_unresolved(text: str) -> dict[str, Any]:
        """Record something you could not find or confirm. Use it when a source is
        missing, a date is not stated, or two sources disagree and you cannot tell
        which governs. It reaches the answer's "Unknowns" section.

        Write unresolved items for a patient or clinician: say what could not be
        confirmed. Never mention tool calls, budgets, limits or doc_ids; name a document
        by its title or publisher.

        Args:
            text: One sentence naming what could not be confirmed.
        """
        ctx.begin("note_unresolved")
        cleaned = _clip(text.strip(), 400)
        if cleaned and cleaned not in ctx.unresolved:
            ctx.unresolved.append(cleaned)
            ctx.ws.unknowns.append(cleaned)  # docs/02 §3
        return {"noted": cleaned, "tool_calls_left": ctx.calls_left}

    return [search, fetch, search_within, add_evidence, note_unresolved]


# --- the wrapper ------------------------------------------------------------------


def run_search_agent(
    task: SearchTask,
    *,
    ws: Workspace,
    store: EvidenceStore | None = None,
    budget: Budget | None = None,
    max_tool_calls: int = MAX_TOOL_CALLS,
    model: BaseChatModel | None = None,
    prompt_set: str = "base",
    run_dir: Path | None = None,
) -> TaskResult:
    """Run one search sub-agent to completion and return its `TaskResult`.

    `budget` is the per-task slice `dispatch` computed (docs/03 §1); it defaults to
    the whole remaining run budget, which is right for the single-task case (the
    docs/09 §1.6 check, the CLI).

    `store` should be the run's one `EvidenceStore` so duplicate passages collapse
    across tasks; the default aliases `ws.evidence` so a standalone call still
    accumulates into the workspace.
    """
    store = store or EvidenceStore(documents=ws.documents, items=ws.evidence)
    ctx = ToolContext(
        ws=ws,
        store=store,
        task=task,
        budget=budget or ws.budget_remaining(),
        max_tool_calls=max_tool_calls,
        run_dir=run_dir or events.run_dir(ws.run_id),
    )
    chat = model or subagent_model()
    system_prompt, kickoff = _render_prompt(task, ctx, prompt_set)
    agent = create_agent(
        chat,
        build_tools(ctx),
        system_prompt=system_prompt,
        # No middleware: docs/03 §13 puts the cap in the tool wrapper, and moving it
        # here would hide it from the trace's tool runs.
        middleware=(),
        # A graph name, not the trace name: LangGraph names must be plain identifiers,
        # while docs/06 §1 wants "search_agent:b1" in LangSmith — that comes from
        # config["run_name"] below.
        name=f"search_agent_{task.branch_id}",
    )

    run_name = f"search_agent:{task.branch_id}"
    task.status = "running"
    ctx.emit(
        "task.started",
        {
            "task_id": task.task_id,
            "branch_id": task.branch_id,
            "round": task.round,
            "instruction": task.instruction,
        },
    )
    started = time.monotonic()
    trace_url: str | None = None

    with ExitStack() as stack:
        parent = get_current_run_tree()
        if parent is not None:
            # Nested under the graph (or a caller's own trace): take the URL from the
            # parent rather than leaving it None. Reporting None here meant every task
            # logged None once 1.7 wires the graph, and RunRecord.langsmith_run_url
            # (docs/02 §2.1) got no help from the node that did the work.
            trace_url = _run_tree_url(parent)
        elif _tracing_enabled():
            # Standalone (the CLI, the 1.6 check, a test): open the run ourselves so
            # the tool runs have a parent and a URL exists.
            handle = stack.enter_context(
                trace_run(
                    f"{run_name} (standalone)",  # distinct, or the trace nests b1 > b1
                    tags=[f"branch:{task.branch_id}", f"round:{task.round}", "node:search_agent"],
                    metadata={
                        "run_id": ws.run_id,
                        "task_id": task.task_id,
                        "max_tool_calls": max_tool_calls,
                    },
                    inputs={"instruction": task.instruction},
                )
            )
            trace_url = handle.url
        messages, cap_reason = _drive(
            agent,
            kickoff,
            config={
                "run_name": run_name,
                # Two supersteps per tool call plus slack. The cap is the real limit;
                # this only stops a pathological loop hitting LangGraph's default.
                "recursion_limit": 2 * max_tool_calls + 6,
                "tags": [f"branch:{task.branch_id}"],
                "metadata": {"run_id": ws.run_id, "task_id": task.task_id},
            },
        )
        if cap_reason is not None:
            # The raw reason ("tool-call cap reached (8 calls) at fetch()", "the run's
            # max_searches budget is exhausted") goes to the log and the summarize turn;
            # the answer's Unknowns get a sentence a reader can use (docs/11).
            _log.info("search_agent.stopped", task_id=task.task_id, reason=cap_reason)
            ctx.unresolved.append(plain_stop_note(cap_reason))
            # docs/03 §13: request the final message with "summarize what you have".
            # Only when there is something to summarize: with no trajectory the model
            # would be inventing, and `_fallback_summary` states the facts instead.
            if any(getattr(m, "type", "") in {"ai", "tool"} for m in messages):
                reply = _final_summary(chat, system_prompt, messages, cap_reason)
                if reply is not None:
                    messages = [*messages, reply]  # kept whole so its tokens count

    ctx.usage.agents = 1
    ctx.usage.wall_seconds = round(time.monotonic() - started, 3)
    estimated = _count_tokens(messages, ctx)
    result = _build_result(ctx, messages)
    task.result, task.status = result, "done"
    ctx.emit("task.done", {"task_id": task.task_id, "result": result})
    _log.info(
        "search_agent.done",
        task_id=task.task_id,
        branch_id=task.branch_id,
        tool_calls=ctx.calls,
        evidence=len(result.evidence_ids),
        documents=len(result.documents_fetched),
        tokens_estimated=estimated,  # docs/06 §2 puts the tag on the root run (1.7)
        trace_url=trace_url,
    )
    return result


STOPPED_NOTE = "This line of research stopped before it was finished."
STOPPED_ON_ERROR_NOTE = "This line of research stopped early because of a technical problem."


def plain_stop_note(reason: str) -> str:
    """The Unknowns line for a task that stopped early, without tool calls, budgets or
    exception text (those stay in the log and the trace)."""
    return STOPPED_ON_ERROR_NOTE if reason.startswith("the agent stopped on an error") else STOPPED_NOTE


def _drive(
    agent: Any, kickoff: str, config: dict[str, Any]
) -> tuple[list[BaseMessage], str | None]:
    """Run the agent, keeping the last good state. Returns (messages, cap_reason).

    Streamed rather than invoked because `BudgetExceeded` propagates out of `invoke`
    with the message history inside it; `stream_mode="values"` hands back a snapshot
    after every superstep, so the history survives the raise and the model can still
    summarize its own work.
    """
    last: dict[str, Any] = {"messages": []}
    try:
        for snapshot in agent.stream(
            {"messages": [HumanMessage(kickoff)]}, config=config, stream_mode="values"
        ):
            last = snapshot
    except BudgetExceeded as exc:
        return _drop_dangling_tool_calls(list(last.get("messages", []))), exc.reason
    except Exception as exc:
        # A recursion limit, a 5xx from the endpoint, a deleted document file. The task
        # has to come back as a failed TaskResult with whatever it gathered: letting
        # this escape left no TaskResult at all, no `task.done` event, and the task
        # stuck at status "running" — and docs/02 §2.3 has a "failed" status for
        # exactly this.
        _log.warning("search_agent.aborted", error=f"{type(exc).__name__}: {exc}")
        return (
            _drop_dangling_tool_calls(list(last.get("messages", []))),
            f"the agent stopped on an error: {type(exc).__name__}: {str(exc)[:200]}",
        )
    return list(last.get("messages", [])), None


def _drop_dangling_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Trim trailing tool calls that never got a result.

    The snapshot that raised ends with the AIMessage whose tool call blew the cap.
    Sending that to a chat endpoint is a 400, so the summarize turn starts from the
    last complete cycle.

    Two passes, because one AIMessage can carry several tool calls: dropping it while
    leaving the results of its *answered* siblings behind would produce ToolMessages
    with no preceding `tool_calls`, which the endpoint rejects just as firmly.
    """
    answered = {
        message.tool_call_id for message in messages if getattr(message, "type", "") == "tool"
    }
    # Drop any assistant turn with an unanswered call, wherever it sits — not only a
    # trailing one. An AIMessage carrying two calls where only the first came back is
    # mid-history by the time the second raises.
    kept: list[BaseMessage] = []
    dropped_ids: set[str] = set()
    for message in messages:
        pending = [call["id"] for call in getattr(message, "tool_calls", None) or []]
        if pending and not set(pending) <= answered:
            dropped_ids.update(pending)
            continue
        kept.append(message)
    # ... and drop the results of the calls that went with it, which would otherwise
    # be ToolMessages with no preceding tool_calls — rejected just as firmly.
    return [
        message
        for message in kept
        if getattr(message, "type", "") != "tool" or message.tool_call_id not in dropped_ids
    ]


def _final_summary(
    chat: BaseChatModel, system_prompt: str, messages: list[BaseMessage], reason: str
) -> AIMessage | None:
    """One un-tooled call: "summarize what you have" (docs/03 §13).

    Returns the whole message rather than its text so its `usage_metadata` reaches
    `_count_tokens` — rebuilding a bare AIMessage threw those tokens away, and this
    call is the largest single prompt of the task.
    """
    try:
        reply = chat.invoke(
            [
                SystemMessage(system_prompt),
                *messages,
                HumanMessage(SUMMARIZE_AFTER_CAP.format(reason=reason)),
            ]
        )
        return reply if isinstance(reply, AIMessage) else AIMessage(content=str(reply))
    except Exception as exc:  # a failed summary must not fail the task
        _log.warning("search_agent.summary_failed", error=f"{type(exc).__name__}: {exc}")
        return None


def _build_result(ctx: ToolContext, messages: list[BaseMessage]) -> TaskResult:
    """`TaskResult` from the tool-call log; only summary/unresolved from the model."""
    summary, trailing = _split_summary(_last_text(messages))
    unresolved = _unique([*ctx.unresolved, *([trailing] if trailing else [])])
    return TaskResult(
        queries_issued=_unique(ctx.queries),
        documents_fetched=_unique(ctx.fetched),
        evidence_ids=_unique(ctx.evidence_ids),
        summary=summary or _fallback_summary(ctx),
        unresolved="; ".join(unresolved) or None,
        usage=ctx.usage,
    )


def _fallback_summary(ctx: ToolContext) -> str:
    """A model that ended with an empty message still owes the tree view a sentence,
    and every fact in it is already in the log."""
    return (
        f"Branch {ctx.task.branch_id}: {len(_unique(ctx.queries))} queries, "
        f"{len(_unique(ctx.fetched))} documents fetched, "
        f"{len(ctx.evidence_ids)} evidence items recorded. "
        "The agent returned no closing summary."
    )


# Matches "Unresolved:", "**Unresolved:**", "## Unresolved -" and friends. The
# trailing `\**` is what stopped the tail starting with a stray "**".
_UNRESOLVED_LINE = re.compile(r"(?im)^[ \t]*#{0,4}[ \t]*\**unresolved\**[ \t]*[:\-][ \t]*\**")
_MD_NOISE = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]*")


def _strip_markdown(text: str) -> str:
    """Drop heading markers and stray emphasis from a model's closing message.

    `TaskResult.summary` is rendered in the UI's search tree as a plain sentence, so a
    literal "## Summary" line is noise — and when the model writes nothing but that
    heading before its Unresolved block, it was the whole summary.
    """
    cleaned = _MD_NOISE.sub("", text or "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    # A bare "Summary" label on its own line adds nothing to a field called summary.
    cleaned = re.sub(r"(?im)^[ \t]*summary[ \t]*:?[ \t]*$\n?", "", cleaned)
    return cleaned.strip()


def _split_summary(text: str) -> tuple[str, str | None]:
    """Rule 6 asks for a summary plus unresolved items in one message. note_unresolved
    is the structured channel; this only rescues what the model wrote inline."""
    text = (text or "").strip()
    if not text:
        return "", None
    parts = _UNRESOLVED_LINE.split(text, maxsplit=1)
    summary = _clip(_strip_markdown(parts[0]), MAX_SUMMARY_CHARS)
    tail = _clip(_strip_markdown(parts[1]), 400) if len(parts) > 1 else None
    return summary, (tail or None)


def _render_prompt(task: SearchTask, ctx: ToolContext, prompt_set: str) -> tuple[str, str]:
    """(system prompt, kickoff message) from prompts/search_agent.md."""
    branch = _branch_for(ctx.ws, task.branch_id)
    text = render(
        "search_agent",
        prompt_set=prompt_set,
        instruction=task.instruction,
        hypothesis=(branch.hypothesis if branch and branch.hypothesis else "(none given)"),
        source_hint=(branch.source_hint if branch else "any"),
        queries_hint=", ".join(task.queries_hint) or "(none)",
        include_domains=", ".join(task.include_domains) or "(none; choose your own)",
        time_range=task.time_range or "(none)",
        budget=(
            f"{ctx.max_tool_calls} tool calls, {ctx.budget.max_searches} searches, "
            f"{ctx.budget.max_fetches} fetches, {ctx.budget.max_deep_reads} "
            "search_within calls"
        ),
    )
    system, _, kickoff = text.partition(PROMPT_SPLIT_MARKER)
    if not kickoff.strip():  # the marker was edited out: degrade, do not crash
        return text, "Begin now."
    return system.strip(), kickoff.strip()


def _branch_for(ws: Workspace, branch_id: str) -> Any:
    if ws.plan is None:
        return None
    return next((b for b in ws.plan.branches if b.branch_id == branch_id), None)


def _count_tokens(messages: list[BaseMessage], ctx: ToolContext) -> bool:
    """docs/06 §5: usage from `usage_metadata`, else the heuristic. Returns whether
    any reply had to be estimated, so the caller can tag the run `tokens:estimated`.

    A wrapper that reports nothing used to leave the totals at zero, which silently
    disables the `max_tokens` budget and understates every cost figure in the bench
    report — a plausible number, quietly wrong.
    """
    estimated = False
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        input_tokens, output_tokens, was_estimated = token_usage(message)
        ctx.usage.input_tokens += input_tokens
        ctx.usage.output_tokens += output_tokens
        estimated = estimated or was_estimated
    with _LOCK:  # the run-wide max_tokens budget is checked against ws.usage
        ctx.ws.usage.input_tokens += ctx.usage.input_tokens
        ctx.ws.usage.output_tokens += ctx.usage.output_tokens
        # docs/06 section 2 puts `tokens:estimated` on the ROOT run, which only the
        # graph can reach - so the finding is recorded here and tagged there.
        ctx.ws.tokens_estimated = ctx.ws.tokens_estimated or estimated
    return estimated


def _run_tree_url(run_tree: Any) -> str | None:
    """The LangSmith URL of an already-open run, or None if it cannot be built."""
    try:
        return run_tree.get_url()
    except Exception:  # no project resolved yet, or tracing disabled mid-run
        return None


def _tracing_enabled() -> bool:
    try:
        return get_settings().tracing_enabled
    except Exception:  # no keys configured: run untraced rather than fail
        return False


# --- small helpers ----------------------------------------------------------------


def _passage_payload(passage: dict[str, object]) -> dict[str, object]:
    """One paragraph for the model, clipped, and honest about the clipping.

    A model that quotes past a silent truncation gets its evidence rejected and burns
    a call; `truncated` lets it quote only what it was shown.
    """
    text = str(passage["text"])
    clipped = _clip_sentence(text, MAX_PASSAGE_CHARS)
    payload: dict[str, object] = {
        "paragraph_index": passage["paragraph_index"],
        "section": passage["section"],
        "text": clipped,
    }
    if clipped != text:
        payload["truncated"] = True
        payload["quote_only_from"] = "the text shown above, not beyond it"
    return payload


def _budget_hint(ctx: ToolContext) -> dict[str, Any]:
    """`tool_calls_left`, plus a nudge when the calls are nearly gone and nothing has
    been recorded (see ToolContext.pressure)."""
    payload: dict[str, Any] = {"tool_calls_left": ctx.calls_left}
    nudge = ctx.pressure()
    if nudge:
        payload["hint"] = nudge
    return payload


def _last_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.text.strip():
            return message.text
    return ""


def _unique(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value:
            seen.setdefault(value, None)
    return list(seen)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _clip(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _clip_sentence(text: str, limit: int) -> str:
    """Truncate a passage at a sentence boundary.

    The model quotes what it is shown, and a prefix is still verbatim so add_evidence
    accepts it — but a cut mid-sentence invites a quote that runs past the cut and
    gets rejected.
    """
    text = text or ""
    if len(text) <= limit:
        return text
    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind(".\n"), window.rfind("; "))
    if cut < limit // 2:
        cut = window.rfind(" ")
    cut = cut if cut > 0 else limit
    return window[: cut + 1].rstrip() + f" ...[truncated; paragraph is {len(text)} chars]"


def _clip_list(values: list[str], limit: int) -> list[str]:
    if len(values) <= limit:
        return list(values)
    return [*values[:limit], f"...+{len(values) - limit} more"]

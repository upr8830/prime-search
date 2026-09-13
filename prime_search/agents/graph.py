"""The PRIME graph (docs/03 §1): understand -> plan -> dispatch -> search_agent ->
collect -> judge -> critic -> synthesize.

After every search round the judge (docs/03 §6) decides whether to search again; the
critic (§7) is a pass-through until the next step of task 2.2.

Three places where the spec's diagram and working LangGraph differ. Each is a
deliberate deviation, logged in docs/11:

1. **`dispatch` is a node *plus* a conditional edge.** §1 says "`dispatch` returns
   `[Send(...)]`", but a node's return value is a state update — only a routing
   function on a conditional edge may return `Send`. The node does the budget
   arithmetic and writes `pending_tasks`; `_fan_out` reads them and returns the Sends.
   Same picture, correct semantics.

2. **The `Send` payload carries `ws` and `store`.** §1's payload is
   `{"task", "run_id", "budget"}`, which `run_search_agent` cannot work from — it needs
   the workspace to fetch into and the evidence store to record against, and those are
   the run's single mutable objects.

3. **Fan-out branches return only `task_results` and `events`.** `PrimeState.ws` has
   no reducer, so two concurrent branches both returning `ws` raise `InvalidUpdateError`
   ("Can receive only one value per step"). They do not need to: they mutate the shared
   object, and `collect` reads it.

Because those branches run concurrently in one superstep, every shared mutation goes
through `workspace.RUN_LOCK`.
"""

from __future__ import annotations

import operator
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from prime_search import events
from prime_search.agents.judge import MAX_NEW_TASKS, run_judge
from prime_search.agents.root import plan_run
from prime_search.agents.search_agent import MAX_TOOL_CALLS, run_search_agent
from prime_search.agents.synthesizer import synthesize
from prime_search.config import Budget, get_settings
from prime_search.evidence.graph import build_claim_graph
from prime_search.evidence.store import EvidenceStore
from prime_search.models import structured
from prime_search.prompts import render
from prime_search.schemas import (
    Answer,
    QueryUnderstanding,
    RunRecord,
    RunRequest,
    SearchTask,
    TaskResult,
)
from prime_search.tracing import get_logger, trace_run
from prime_search.workspace import RUN_LOCK, Workspace

_log = get_logger(component="graph")

__all__ = ["PrimeState", "build_graph", "run_prime"]

# docs/03 §10's depth table.
DEPTH: dict[str, dict[str, int]] = {
    "fast": {"max_branches": 2, "max_agents": 1, "max_rounds": 1, "tool_calls": 5},
    "deep": {"max_branches": 7, "max_agents": 6, "max_rounds": 3, "tool_calls": MAX_TOOL_CALLS},
}

# Not specified anywhere (docs/11). A round is one model-driven sub-agent per task, and
# a sub-agent times only itself; starting a round with less than this left would run it
# past the deadline, so the judge and critic add no round below it.
MIN_SECONDS_FOR_ROUND = 30


def _merge_results(
    left: dict[str, TaskResult] | None, right: dict[str, TaskResult] | None
) -> dict[str, TaskResult]:
    """Reducer for `results_by_task`: concurrent branches each add their own key."""
    return {**(left or {}), **(right or {})}


class PrimeState(TypedDict, total=False):
    """docs/03 §1, verbatim. `total=False` because a fan-out branch returns two keys."""

    run_id: str
    request: RunRequest
    ws: Workspace  # single object; nodes mutate and return it
    store: EvidenceStore
    pending_tasks: list[SearchTask]
    task_results: Annotated[list[TaskResult], operator.add]
    # Not in §1: keyed by task id, so `collect` pairs a result with the task that
    # produced it. `task_results` accumulates across rounds, and zipping it against the
    # tasks still running paired round-0 results with round-1 tasks.
    results_by_task: Annotated[dict[str, TaskResult], _merge_results]
    round: int
    critic_rounds: int
    deadline: float
    events: Annotated[list[dict], operator.add]
    answer: Answer
    # Not in §1's list: the depth knobs and the trace handle have to reach the nodes,
    # and threading them through a closure would make the graph untestable.
    depth: str
    prompt_set: str
    models: dict[str, Any]
    fallback_tags: Annotated[list[str], operator.add]
    trace_url: str | None


# --- nodes -------------------------------------------------------------------------


def _understand(state: PrimeState) -> dict[str, Any]:
    """docs/03 §2: judge model, structured output, temperature 0."""
    ws = state["ws"]
    if _past_deadline(state):
        return {}
    override = state.get("models", {}).get("understand")
    prompt = render("understand", state.get("prompt_set", "base"), question=ws.objective)
    try:
        if override is not None:
            understanding = override.with_structured_output(QueryUnderstanding).invoke(prompt)
        else:
            understanding = structured("judge", QueryUnderstanding).invoke(prompt)
    except Exception as exc:  # noqa: BLE001 - a run without classification still runs
        _log.warning("understand.failed", error=f"{type(exc).__name__}: {exc}")
        understanding = QueryUnderstanding(
            normalized_question=ws.objective,
            domain="other",
            question_type="other",
            time_sensitivity="medium",
        )
    ws.understanding = understanding
    record = events.emit(ws.run_id, "understanding", understanding)
    _persist(state)
    return {"events": [record]}


def _plan(state: PrimeState) -> dict[str, Any]:
    """docs/03 §3, via agents/root.py's ladder."""
    ws = state["ws"]
    if _past_deadline(state):
        return {}
    depth = state.get("depth", "deep")
    outcome = plan_run(
        ws,
        prompt_set=state.get("prompt_set", "base"),
        model=state.get("models", {}).get("root"),
        depth=depth,
        max_branches=DEPTH[depth]["max_branches"],
    )
    update: dict[str, Any] = {}
    if outcome.fallback_tag:
        update["fallback_tags"] = [outcome.fallback_tag]
    _persist(state)
    return update


def _dispatch(state: PrimeState) -> dict[str, Any]:
    """Turn branches (or the judge's new tasks) into `SearchTask`s the budget allows.

    docs/03 §1: "dispatch truncates `pending_tasks` to what the remaining budget allows
    (`max_agents`, `max_searches` divided across tasks)."
    """
    ws = state["ws"]
    if _past_deadline(state):
        return {"pending_tasks": []}

    pending = list(state.get("pending_tasks") or [])
    # Round 0 only: the tasks are the plan's branches. Seeding whenever `pending_tasks`
    # was empty would re-dispatch every branch the moment a later node routed back here.
    if not pending and state.get("round", 0) == 0 and not ws.tasks:
        pending = _tasks_from_plan(state)

    remaining = ws.budget_remaining()
    depth = state.get("depth", "deep")
    # `max_agents` caps each round, not the run (docs/11). And a run with no searches
    # left gets no agents: each would spend a model call discovering it cannot search.
    max_agents = min(ws.budget.max_agents, DEPTH[depth]["max_agents"], remaining.max_searches)
    # Highest priority first, so truncation drops the branches the planner itself
    # ranked least important rather than whichever happened to be last.
    pending.sort(key=lambda task: _priority_of(ws, task))
    kept = pending[: max(0, max_agents)]

    for task in kept:
        task.status = "running"
    with RUN_LOCK:
        ws.tasks.extend(kept)
        ws.usage.agents += len(kept)

    # No event of its own. docs/02 §4's table is closed and its `plan` payload is a
    # `SearchPlan` (emitted by the planner) while `task.started` is per task with
    # `{task_id, branch_id, round, instruction}` (emitted by each sub-agent). An
    # aggregate under either name is a payload no SSE client typing the event can read,
    # so what dispatch alone knows - how many tasks the budget dropped - is logged.
    dropped = len(pending) - len(kept)
    if dropped:
        _log.info("dispatch.truncated", round=state.get("round", 0), dropped=dropped, kept=len(kept))
    _persist(state)
    return {"pending_tasks": kept}


def _fan_out(state: PrimeState) -> list[Send] | str:
    """The conditional edge that actually fans out (see the module docstring).

    Returns the node name `"collect"` when there is nothing to dispatch — a `Send`
    list that is empty leaves the superstep with no outgoing task and the graph stops
    with the answer unwritten.
    """
    tasks = state.get("pending_tasks") or []
    if not tasks:
        return "collect"
    ws, store = state["ws"], state["store"]
    budget = _slice_budget(ws, len(tasks), state.get("depth", "deep"))
    return [
        Send(
            "search_agent",
            {
                "task": task,
                "run_id": state["run_id"],
                "budget": budget,
                "deadline": state.get("deadline", float("inf")),
                # Not in §1's payload; see the module docstring.
                "ws": ws,
                "store": store,
                "depth": state.get("depth", "deep"),
                "prompt_set": state.get("prompt_set", "base"),
                "models": state.get("models", {}),
            },
        )
        for task in tasks
    ]


def _search_agent(payload: dict[str, Any]) -> dict[str, Any]:
    """One sub-agent (docs/03 §4). Returns **only** `task_results`, `results_by_task`
    and `events` - never `ws` (see the module docstring)."""
    task: SearchTask = payload["task"]
    ws: Workspace = payload["ws"]
    depth = payload.get("depth", "deep")
    # docs/01 §9: "a checked deadline at every node boundary". The sub-agent times only
    # itself, so a task started after the run's deadline would otherwise run past it.
    if time.time() >= payload.get("deadline", float("inf")):
        return _failed_task(payload, task, "not started: run deadline reached")
    try:
        result = run_search_agent(
            task,
            ws=ws,
            store=payload["store"],
            budget=payload["budget"],
            max_tool_calls=DEPTH[depth]["tool_calls"],
            model=payload.get("models", {}).get("subagent"),
            prompt_set=payload.get("prompt_set", "base"),
            run_dir=events.run_dir(payload["run_id"]),
        )
        # `run_search_agent` emits its own docs/02 §4 `task.done` on every path it
        # controls, so this node does not emit a second one - two events per task made
        # the CLI print each branch twice, once with an empty payload.
        return {"task_results": [result], "results_by_task": {task.task_id: result}, "events": []}
    except Exception as exc:  # noqa: BLE001 - one failed branch is not a failed run
        _log.warning("search_agent.failed", task=task.task_id, error=str(exc))
        events.emit(
            payload["run_id"],
            "error",
            {"message": f"{task.task_id}: {type(exc).__name__}: {exc}"[:500], "node": "search_agent"},
        )
        return _failed_task(payload, task, f"this branch failed: {type(exc).__name__}: {exc}")


def _failed_task(payload: dict[str, Any], task: SearchTask, unresolved: str) -> dict[str, Any]:
    """A task that produced nothing: failed, with the reason as its unresolved note."""
    task.status = "failed"
    result = TaskResult(
        queries_issued=[],
        documents_fetched=[],
        evidence_ids=[],
        summary="",
        unresolved=unresolved[:500],
        usage=_empty_usage(),
    )
    task.result = result
    # The one path where nothing else will: the sub-agent never got far enough to
    # report, so the task would otherwise vanish from the stream entirely.
    record = events.emit(
        payload["run_id"],
        "task.done",
        {
            "task_id": task.task_id,
            "branch_id": task.branch_id,
            "evidence": 0,
            "unresolved": result.unresolved,
        },
    )
    return {"task_results": [result], "results_by_task": {task.task_id: result}, "events": [record]}


def _collect(state: PrimeState) -> dict[str, Any]:
    """docs/03 §5: merge, rebuild the claim graph, detect contradictions, next round.

    **Usage is not re-added here.** `TaskResult.usage` is a *report* of what the task
    spent; the tools already charged every unit to `ws.usage` as they went. Adding it
    again would double every search, fetch and token in the run record and in the bench
    cost column.
    """
    ws = state["ws"]
    by_task = state.get("results_by_task") or {}

    # The sub-agent sets its own task's status (docs/02 §2.3) - "done" when it
    # finished, "failed" when it aborted - so `collect` attaches the result and leaves
    # that judgement alone. An earlier version derived it here as
    # `"done" if not result.unresolved else "failed"`, which inverts the meaning of
    # `unresolved`: docs/03 §4 rule 6 asks every *successful* task to end with "any
    # unresolved items", so a branch that fetched the LCD and recorded five evidence
    # items was persisted as failed and would render as a failed node in the UI tree.
    #
    # Paired by task id. The sub-agent normally attaches its own result; this covers a
    # task whose result reached only the state. A running task with no result at all
    # failed.
    for task in ws.tasks:
        if task.status != "running":
            continue
        if task.result is None:
            task.result = by_task.get(task.task_id)
        task.status = "done" if task.result is not None else "failed"

    graph = build_claim_graph(ws.evidence, ws.documents)
    with RUN_LOCK:
        ws.claims = graph.claims
        ws.contradictions = [claim.claim_id for claim in graph.contested]
        ws.unknowns = _unknowns(ws, state)
        ws.usage.rounds = state.get("round", 0) + 1

    # docs/02 §4: `usage` carries a `Usage` and drives the cost/latency footer. The
    # round summary the CLI shows is counted from the `evidence` events the sub-agents
    # already emit, rather than inventing a second payload under a taken event name.
    ws.usage.wall_seconds = round(
        (datetime.now(UTC) - ws.started_at).total_seconds(), 1
    )
    record = events.emit(ws.run_id, "usage", ws.usage)
    _log.info(
        "collect",
        round=state.get("round", 0),
        evidence=len(ws.evidence),
        claims=len(ws.claims),
        tasks=len(ws.tasks),
    )
    _persist(state)
    return {
        "pending_tasks": [],
        "round": state.get("round", 0) + 1,
        "events": [record],
    }


def _judge(state: PrimeState) -> dict[str, Any]:
    """docs/03 §6: is there enough? If not, and a round is left, new tasks for dispatch.

    `collect` has already advanced `round`, so the verdict judges round `round - 1` and
    any task it adds belongs to round `round`. `max_rounds` counts every search round,
    the initial one included (docs/11), so tasks are allowed while `round < max_rounds`.
    """
    ws = state["ws"]
    if _past_deadline(state):
        return {}
    depth = state.get("depth", "deep")
    current = state.get("round", 0)
    may_search = depth != "fast" and current < _max_rounds(state) and _can_search(ws, state)
    per_round = min(ws.budget.max_agents, DEPTH[depth]["max_agents"])
    outcome = run_judge(
        ws,
        judged_round=max(0, current - 1),
        max_new_tasks=min(MAX_NEW_TASKS, per_round) if may_search else 0,
        rounds_left=max(0, _max_rounds(state) - current),
        prompt_set=state.get("prompt_set", "base"),
        model=state.get("models", {}).get("judge"),
    )
    verdict = outcome.verdict
    if verdict.new_tasks and not may_search:
        # docs/03 §6: "the graph ignores `new_tasks` when `round == max_rounds`". The
        # recorded verdict lists only tasks actually dispatched (docs/02 §2.6).
        _log.info("judge.tasks_ignored", round=current, tasks=len(verdict.new_tasks))
        verdict = verdict.model_copy(update={"new_tasks": []})
    with RUN_LOCK:
        ws.verdicts.append(verdict)
    record = events.emit(ws.run_id, "verdict", verdict)
    update: dict[str, Any] = {
        "events": [record],
        "pending_tasks": [] if verdict.sufficient else list(verdict.new_tasks),
    }
    if outcome.fallback_tag:
        update["fallback_tags"] = [outcome.fallback_tag]
    _persist(state)
    return update


def _critic(state: PrimeState) -> dict[str, Any]:
    """docs/09 §1.7: stubbed as a pass-through today. Task 2.3 implements docs/03 §7."""
    _persist(state)
    return {}


def _synthesize(state: PrimeState) -> dict[str, Any]:
    """docs/03 §8."""
    ws = state["ws"]
    answer = synthesize(
        ws,
        prompt_set=state.get("prompt_set", "base"),
        model=state.get("models", {}).get("root"),
        on_token=state.get("models", {}).get("on_token"),
        unresolved=ws.unknowns,
    )
    _persist(state, answer=answer)
    return {"answer": answer}


# --- assembly ----------------------------------------------------------------------


def build_graph() -> Any:
    """Compile the docs/03 §1 graph."""
    builder = StateGraph(PrimeState)
    builder.add_node("understand", _understand)
    builder.add_node("plan", _plan)
    builder.add_node("dispatch", _dispatch)
    builder.add_node("search_agent", _search_agent)
    builder.add_node("collect", _collect)
    builder.add_node("judge", _judge)
    builder.add_node("critic", _critic)
    builder.add_node("synthesize", _synthesize)

    builder.add_edge(START, "understand")
    builder.add_edge("understand", "plan")
    builder.add_edge("plan", "dispatch")
    # The deviation from §1's diagram: the node computed the tasks, this edge sends them.
    builder.add_conditional_edges("dispatch", _fan_out, ["search_agent", "collect"])
    builder.add_edge("search_agent", "collect")
    builder.add_edge("collect", "judge")
    builder.add_conditional_edges("judge", _after_judge, ["dispatch", "critic", "synthesize"])
    builder.add_edge("critic", "synthesize")
    builder.add_edge("synthesize", END)
    return builder.compile()


def run_prime(
    request: RunRequest,
    *,
    on_event: Callable[[dict], None] | None = None,
    on_token: Callable[[str], None] | None = None,
    models: dict[str, BaseChatModel] | None = None,
    ws: Workspace | None = None,
) -> RunRecord:
    """Run one PRIME investigation end to end and return its `RunRecord`.

    `on_event` and `on_token` are how the CLI (and, at 2.4, the SSE stream) watch a
    run: the CLI subscribes rather than reaching into the graph, so the API will not
    need a second rendering path.
    """
    settings = get_settings()
    budget = request.budget_override or settings.budget(request.depth)
    workspace = ws or Workspace(objective=request.question, budget=budget)
    store = EvidenceStore(documents=workspace.documents, items=workspace.evidence)
    started = datetime.now(UTC)

    unsubscribe = events.subscribe(workspace.run_id, on_event) if on_event else None
    node_models = dict(models or {})
    if on_token is not None:
        node_models["on_token"] = on_token  # type: ignore[assignment]

    state: PrimeState = {
        "run_id": workspace.run_id,
        "request": request,
        "ws": workspace,
        "store": store,
        "pending_tasks": [],
        "task_results": [],
        "round": 0,
        "critic_rounds": 0,
        "deadline": time.time() + budget.max_seconds,
        "events": [],
        "depth": request.depth,
        "prompt_set": request.prompt_set,
        "models": node_models,
        "fallback_tags": [],
        "trace_url": None,
    }

    tags, metadata = _trace_tags(request, settings, workspace)
    record: RunRecord | None = None
    trace_url: str | None = None
    try:
        with trace_run(
            "prime_search",
            tags=tags,
            metadata=metadata,
            inputs={"question": request.question},
        ) as handle:
            trace_url = handle.url
            state["trace_url"] = handle.url  # so every node boundary records it
            events.emit(
                workspace.run_id,
                "run.started",
                {
                    "run_id": workspace.run_id,
                    "question": request.question,
                    "mode": request.mode,
                    "depth": request.depth,
                    "trace_url": handle.url,
                },
            )
            _write_record(workspace, request, started, handle.url, status="running")
            final = build_graph().invoke(
                state,
                config={
                    # NOT "prime_search". `trace_run` above already opened a root run
                    # by that name (docs/06 §1), and LangGraph always adds its own run
                    # for the compiled graph - so naming both the same produced a trace
                    # whose only visible child was an identically named row, with
                    # understand/plan/synthesize hidden one level below it. Two rows
                    # called `prime_search` read as a rendering glitch, not a hierarchy.
                    "run_name": "graph",
                    "recursion_limit": 50,
                    "metadata": {"run_id": workspace.run_id},
                },
            )
            # docs/06 §2 puts domain/qtype on the root run; they only exist now.
            if workspace.understanding is not None:
                handle.add_tags(
                    f"domain:{workspace.understanding.domain}",
                    f"qtype:{workspace.understanding.question_type}",
                )
            handle.add_tags(*final.get("fallback_tags", []))
            if state_tags := _usage_tags(workspace):
                handle.add_tags(*state_tags)
            record = _write_record(
                workspace,
                request,
                started,
                handle.url,
                status=_terminal_status(workspace, state),
                answer=final.get("answer"),
            )
    except Exception as exc:
        _log.warning("run.failed", error=f"{type(exc).__name__}: {exc}")
        events.emit(
            workspace.run_id,
            "error",
            {"message": f"{type(exc).__name__}: {exc}"[:500], "node": "run_prime"},
        )
        record = _write_record(
            workspace, request, started, None, status="failed", error=f"{type(exc).__name__}: {exc}"
        )
        raise
    finally:
        # Emitted BEFORE unsubscribing. docs/06 §4 has `emit()` push to the in-process
        # subscriber queue, and docs/02 §4 makes `run.finished` the footer link and the
        # natural point for an SSE client to close - so unsubscribing first delivered
        # the event to the JSONL and to nobody listening. The CLI hid it by taking the
        # URL from `run.started` and the answer from the returned record.
        events.emit(
            workspace.run_id,
            "run.finished",
            {
                "status": record.status if record else "failed",
                "langsmith_run_url": trace_url,
            },
        )
        if unsubscribe:
            unsubscribe()
    return record


# --- helpers -----------------------------------------------------------------------


def _tasks_from_plan(state: PrimeState) -> list[SearchTask]:
    """One `SearchTask` per branch (docs/03 §1, round 0).

    docs/03 §3's contract says a change-detection question must get a branch with
    `time_range="year"`. `Branch` has no such field — `SearchTask` does — so the rule is
    applied here: the recency branch of a change-detection question gets the window.
    """
    ws = state["ws"]
    if ws.plan is None:
        return []
    change_detection = (
        ws.understanding is not None and ws.understanding.question_type == "change_detection"
    )
    tasks: list[SearchTask] = []
    for branch in ws.plan.branches:
        recency = _is_recency_branch(branch.question)
        tasks.append(
            SearchTask(
                task_id=f"{branch.branch_id}-r0",
                branch_id=branch.branch_id,
                round=0,
                instruction=branch.question,
                queries_hint=[],
                include_domains=[],
                time_range="year" if (recency or change_detection) and recency else None,
            )
        )
    # A change-detection question whose plan has no recency branch at all still needs
    # one time-filtered task, or the contract is unmet by omission.
    if change_detection and tasks and not any(task.time_range for task in tasks):
        tasks[0].time_range = "year"
    return tasks


_RECENCY_WORDS = (
    "recent", "recently", "current", "latest", "change", "changed", "revision",
    "revised", "update", "updated", "new", "since", "now",
)


def _is_recency_branch(question: str) -> bool:
    lowered = question.lower()
    return any(word in lowered for word in _RECENCY_WORDS)


def _priority_of(ws: Workspace, task: SearchTask) -> int:
    if ws.plan is None:
        return task.round
    branch = next((b for b in ws.plan.branches if b.branch_id == task.branch_id), None)
    return branch.priority if branch else 99


def _slice_budget(ws: Workspace, tasks: int, depth: str) -> Budget:
    """docs/03 §1: "`max_searches` divided across tasks".

    Divided from what *remains*, not from the original budget: on round 2 the first
    round has already spent, and slicing the original would hand out budget that is
    gone. At least one of each while any remains, so a task is never dispatched unable
    to act - but never one that is not there.
    """
    remaining = ws.budget_remaining()
    share = max(1, tasks)
    return Budget(
        max_searches=_share(remaining.max_searches, share),
        max_fetches=_share(remaining.max_fetches, share),
        max_deep_reads=_share(remaining.max_deep_reads, share),
        max_agents=remaining.max_agents,
        max_rounds=remaining.max_rounds,
        max_tokens=remaining.max_tokens,
        max_seconds=remaining.max_seconds,
    )


def _share(remaining: int, tasks: int) -> int:
    """One task's slice: at least one while any remains, zero when none does."""
    return max(min(1, remaining), remaining // tasks)


def _unknowns(ws: Workspace, state: PrimeState) -> list[str]:
    """What to carry into the answer's "Unknowns / not verified" section."""
    notes = [task.result.unresolved for task in ws.tasks if task.result and task.result.unresolved]
    covered = {item.branch_id for item in ws.evidence}
    for branch in ws.plan.branches if ws.plan else []:
        if branch.branch_id not in covered:
            notes.append(f"No evidence was found for: {branch.question}")
    # docs/01 section 9: "Budget exhausted -> graph jumps to synthesis with whatever
    # evidence exists; answer's 'unknowns' section states the budget was hit." Without
    # this the answer is thin and never says why, which reads as the sources being
    # silent rather than the run being cut short.
    for limit, note in ws.exhausted_limits():
        notes.append(note)
        _log.info("budget.exhausted", limit=limit)
    # Stable order, no duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for note in notes:
        if note not in seen:
            seen.add(note)
            unique.append(note)
    return unique


def _terminal_status(ws: Workspace, state: PrimeState) -> str:
    """docs/02 section 2.1's status. `budget_exhausted` is a real outcome, not a
    failure: the answer is valid, it is just built on less than the plan asked for -
    and the bench needs to tell the two apart when it reads a thin row."""
    return "budget_exhausted" if ws.exhausted_limits() else "completed"


def _usage_tags(ws: Workspace) -> list[str]:
    """docs/06 section 5: a run whose token counts are chars/4 guesses must be
    distinguishable in LangSmith from a measured one, or every cost figure derived
    from it looks exact. The 1.6 decision log assigned this tagging to 1.7."""
    from prime_search.models import TOKENS_ESTIMATED_TAG

    return [TOKENS_ESTIMATED_TAG] if ws.tokens_estimated else []


def _max_rounds(state: PrimeState) -> int:
    """Search rounds allowed, the initial one included (docs/11)."""
    return min(state["ws"].budget.max_rounds, DEPTH[state.get("depth", "deep")]["max_rounds"])


def _can_search(ws: Workspace, state: PrimeState) -> bool:
    """docs/03 §7's "budget allows", used by the judge and the critic before adding a
    round: searches and tokens left, and time for a round before the deadline."""
    remaining = ws.budget_remaining()
    seconds_left = state.get("deadline", float("inf")) - time.time()
    return (
        seconds_left >= MIN_SECONDS_FOR_ROUND
        and remaining.max_searches > 0
        and remaining.max_tokens > 0
    )


def _after_judge(state: PrimeState) -> str:
    """docs/03 §1: insufficient with a round left -> dispatch, otherwise the critic.
    Fast depth has no critic (§10); an expired deadline goes straight to synthesis."""
    if _past_deadline(state):
        return "synthesize"
    if state.get("pending_tasks"):
        return "dispatch"
    return "synthesize" if state.get("depth", "deep") == "fast" else "critic"


def _past_deadline(state: PrimeState) -> bool:
    """docs/03 §1: "Every node checks `time.time() < deadline`; if not, it returns a
    state that routes straight to `synthesize`."

    With judge and critic stubbed there is no branching to short-circuit yet, so an
    expired deadline makes the remaining nodes cheap no-ops and the run synthesizes
    from what it has — the same outcome, without a conditional edge that 2.2 would
    immediately rewrite.
    """
    expired = time.time() >= state.get("deadline", float("inf"))
    if expired:
        _log.warning("deadline.expired", run_id=state.get("run_id"))
    return expired


def _empty_usage() -> Any:
    from prime_search.schemas import Usage

    return Usage()


def _trace_tags(
    request: RunRequest, settings: Any, ws: Workspace
) -> tuple[list[str], dict[str, Any]]:
    """docs/06 §2's root-run tags and metadata. `domain:`/`qtype:` are added later —
    they do not exist until `understand` has run."""
    tags = [
        f"mode:{request.mode}",
        f"depth:{request.depth}",
        f"prompt_set:{request.prompt_set}",
        f"model:{settings.models.root}",
        f"subagent:{settings.models.subagent}",
        "source:cli",
    ]
    metadata = {
        "run_id": ws.run_id,
        "question_id": request.question_id,
        "question": request.question,
        "git_sha": _git_sha(),
        "budget": ws.budget.model_dump(),
        "models": settings.models.model_dump(),
        "tavily_cache": True,
    }
    return tags, metadata


def _git_sha() -> str | None:
    import subprocess

    try:
        return subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip() or None
    except Exception:  # noqa: BLE001 - a run outside a checkout still runs
        return None


def _write_record(
    ws: Workspace,
    request: RunRequest,
    started: datetime,
    trace_url: str | None,
    *,
    status: str,
    answer: Answer | None = None,
    error: str | None = None,
) -> RunRecord:
    """Build the `RunRecord` and write docs/02 §5's run layout.

    The files are `request.json`, `state.json` and `answer.md` - the spec's names. An
    earlier build wrote a single `run.json`, which nothing written to the spec would
    find: docs/01 §2 and docs/06 §7's `prime-search diff` both name `state.json`, and
    `evidence/graph.py`'s own docstring already says "inside state.json".
    """
    record = ws.to_record(
        request,
        started_at=started,
        finished_at=None if status == "running" else datetime.now(UTC),
        langsmith_run_url=trace_url,
        answer=answer,
        status=status,
        error=error,
    )
    events.write_run_artifacts(record)
    return record


def _persist(state: PrimeState, *, answer: Answer | None = None) -> None:
    """docs/06 §4: "`RunRecord` is written at every node boundary ... so a crashed run
    still has a partial record the UI can open."

    Called at the end of each node rather than only at the start and end of the run:
    a process killed during search previously left a record saying `status: "running"`
    with no plan, no documents and no evidence - exactly the case §4 exists for. The
    file is rewritten, not appended, so the extra writes cost one serialization each.
    """
    _write_record(
        state["ws"],
        state["request"],
        state["ws"].started_at,
        state.get("trace_url"),
        status="running",
        answer=answer,
    )

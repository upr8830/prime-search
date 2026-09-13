"""The evidence judge (docs/03 §6): after each search round, is there enough?

The cheap, frequent check. It reads what the round produced as a compact per-branch
summary - claim statuses, governing dates, source tiers, the searches already run -
never the passages, and returns a `Verdict`: coverage per branch, what is still
missing, and at most three new `SearchTask`s when the answer is not there yet.

Everything in a proposed task that the harness owns is rewritten here, the way the
planner's output is (docs/11): the task id, its round and status. A task for a branch
the plan does not have, for a branch the judge itself called resolved, or repeating a
search the run already made is dropped rather than dispatched - each would spend a
sub-agent learning nothing new.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from langchain_core.language_models import BaseChatModel

from prime_search import events
from prime_search.models import structured
from prime_search.primitives import sources
from prime_search.prompts import render
from prime_search.schemas import Claim, Evidence, SearchTask, Verdict
from prime_search.tracing import get_logger
from prime_search.workspace import Workspace

_log = get_logger(component="judge")

__all__ = [
    "FAILED_TAG",
    "MAX_NEW_TASKS",
    "JudgeOutcome",
    "build_prompt",
    "failed_verdict",
    "normalize_verdict",
    "run_judge",
]

MAX_NEW_TASKS = 3  # docs/03 §6: "at most 3 per round"
MAX_QUERIES = 3
# Enough to show a branch's shape without the prompt growing with the evidence.
MAX_CLAIMS_PER_BRANCH = 12
MAX_MISSING = 8
FAILED_TAG = "fallback:judge_failed"
_TIME_RANGES = {"year", "month"}


@dataclass
class JudgeOutcome:
    verdict: Verdict
    mode: str  # native | native_retry_N | fenced_json | injected | failed
    fallback_tag: str | None = None
    error: str | None = None
    dropped_tasks: int = 0


def run_judge(
    ws: Workspace,
    *,
    judged_round: int,
    max_new_tasks: int,
    rounds_left: int,
    prompt_set: str = "base",
    model: BaseChatModel | None = None,
) -> JudgeOutcome:
    """Judge the round just collected. Never raises.

    docs/01 §9: "Model output unparseable -> one repair attempt ... then the node
    returns a structured failure and the graph proceeds." `models.structured` is the
    repair attempt (native twice, then fenced JSON); a failure after that becomes
    `failed_verdict`, an `error` event and a fallback tag.
    """
    prompt = build_prompt(
        ws,
        judged_round=judged_round,
        max_new_tasks=max_new_tasks,
        rounds_left=rounds_left,
        prompt_set=prompt_set,
    )
    message = None
    try:
        if model is not None:
            raw = model.with_structured_output(Verdict).invoke(prompt)
            mode = "injected"
        else:
            caller = structured("judge", Verdict)
            raw = caller.invoke(prompt)
            mode, message = caller.last_mode, caller.last_message
        if not isinstance(raw, Verdict):
            raw = Verdict.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - a failed judge must not fail the run
        error = f"{type(exc).__name__}: {exc}"[:500]
        _log.warning("judge.failed", run_id=ws.run_id, error=error)
        events.emit(ws.run_id, "error", {"message": f"judge: {error}", "node": "judge"})
        ws.charge_tokens(None, prompt)
        return JudgeOutcome(failed_verdict(ws, judged_round, error), "failed", FAILED_TAG, error)

    ws.charge_tokens(message, prompt)
    verdict, dropped = normalize_verdict(
        raw, ws, judged_round=judged_round, max_new_tasks=max_new_tasks
    )
    if dropped:
        _log.info("judge.tasks_dropped", run_id=ws.run_id, dropped=dropped)
    return JudgeOutcome(verdict, mode, dropped_tasks=dropped)


def build_prompt(
    ws: Workspace,
    *,
    judged_round: int,
    max_new_tasks: int,
    rounds_left: int,
    prompt_set: str = "base",
) -> str:
    """docs/03 §6's input: stop criteria, per-branch claims with statuses and governing
    dates, unresolved notes, remaining budget."""
    return render(
        "judge",
        prompt_set,
        question=ws.objective,
        stop_criteria=ws.plan.stop_criteria if ws.plan else "(no plan was made)",
        branches=_render_branches(ws),
        unresolved=_render_list(ws.unknowns, "(none)"),
        budget=_render_budget(ws, rounds_left),
        round=str(judged_round),
        max_new_tasks=str(max(0, max_new_tasks)),
    )


def normalize_verdict(
    raw: Verdict, ws: Workspace, *, judged_round: int, max_new_tasks: int
) -> tuple[Verdict, int]:
    """The verdict the graph acts on, and how many proposed tasks were dropped."""
    ids = _branch_ids(ws)
    covered = {item.branch_id for item in ws.evidence}
    coverage = {
        branch: raw.coverage.get(branch) or ("partial" if branch in covered else "unresolved")
        for branch in ids
    }
    issued = _issued(ws)
    next_round = judged_round + 1

    kept: list[SearchTask] = []
    per_branch: dict[str, int] = {}
    for proposed in [] if raw.sufficient else raw.new_tasks:
        if len(kept) >= max(0, max_new_tasks):
            break
        branch = proposed.branch_id.strip()
        instruction = _squash(proposed.instruction)
        if branch not in ids or coverage.get(branch) == "resolved" or not instruction:
            continue
        queries = _dedupe(_squash(query) for query in proposed.queries_hint)[:MAX_QUERIES]
        if _repeats(branch, instruction, queries, issued):
            continue
        # A second identical proposal in the same verdict is a repeat too.
        issued.setdefault(branch, (set(), set()))[0].add(instruction.lower())
        per_branch[branch] = per_branch.get(branch, 0) + 1
        suffix = "" if per_branch[branch] == 1 else f"-{per_branch[branch]}"
        kept.append(
            SearchTask(
                task_id=f"{branch}-r{next_round}{suffix}",
                branch_id=branch,
                round=next_round,
                instruction=instruction,
                queries_hint=queries,
                include_domains=_hosts(proposed.include_domains),
                time_range=proposed.time_range if proposed.time_range in _TIME_RANGES else None,
            )
        )

    verdict = Verdict(
        round=judged_round,
        sufficient=raw.sufficient,
        coverage=coverage,
        missing=[_squash(item) for item in raw.missing if item.strip()][:MAX_MISSING],
        new_tasks=kept,
        reasoning=raw.reasoning.strip(),
    )
    return verdict, len(raw.new_tasks) - len(kept)


def failed_verdict(ws: Workspace, judged_round: int, error: str) -> Verdict:
    """What the run records when the judge could not answer.

    `sufficient` is False: routing is the same either way (no tasks, on to the critic),
    and recording True would claim a sufficiency nobody checked in the run record, the
    UI's round separator and the bench.
    """
    covered = {item.branch_id for item in ws.evidence}
    return Verdict(
        round=judged_round,
        sufficient=False,
        coverage={
            branch: "partial" if branch in covered else "unresolved" for branch in _branch_ids(ws)
        },
        missing=[f"judge output unusable: {error}"[:300]],
        new_tasks=[],
        reasoning="The judge failed; the run continued without a sufficiency check.",
    )


# --- rendering ---------------------------------------------------------------------


def _branch_ids(ws: Workspace) -> list[str]:
    ids = [branch.branch_id for branch in ws.plan.branches] if ws.plan else []
    for task in ws.tasks:
        if task.branch_id not in ids:
            ids.append(task.branch_id)
    return ids


def _render_branches(ws: Workspace) -> str:
    ids = _branch_ids(ws)
    if not ids:
        return "(no branches)"
    evidence = {item.evidence_id: item for item in ws.evidence}
    blocks: list[str] = []
    for branch_id in ids:
        branch = (
            next((b for b in ws.plan.branches if b.branch_id == branch_id), None)
            if ws.plan
            else None
        )
        header = f"### {branch_id}"
        lines: list[str] = []
        if branch is not None:
            header += f" (priority {branch.priority}, look in: {branch.source_hint})"
            lines.append(f"Question: {branch.question}")

        claims = [claim for claim in ws.claims if claim.branch_id == branch_id]
        lines.append("Claims:")
        lines.extend(f"- {_claim_line(claim, evidence, ws)}" for claim in claims[:MAX_CLAIMS_PER_BRANCH])
        if len(claims) > MAX_CLAIMS_PER_BRANCH:
            lines.append(f"- ... and {len(claims) - MAX_CLAIMS_PER_BRANCH} more")
        if not claims:
            lines.append("- (none yet)")

        tasks = [task for task in ws.tasks if task.branch_id == branch_id]
        lines.append("Searches already run:")
        for task in tasks:
            queries = task.result.queries_issued if task.result else []
            quoted = "; ".join(f'"{query}"' for query in queries) or "no queries recorded"
            lines.append(
                f"- {task.task_id} (round {task.round}, {task.status}): {task.instruction}"
                f" — queries: {quoted}"
            )
            if task.result and task.result.unresolved:
                lines.append(f"  unresolved: {task.result.unresolved}")
        if not tasks:
            lines.append("- (none)")
        blocks.append("\n".join([header, *lines]))
    return "\n\n".join(blocks)


def _claim_line(claim: Claim, evidence: dict[str, Evidence], ws: Workspace) -> str:
    tiers = [
        ws.documents[evidence[eid].doc_id].source_tier
        for eid in claim.supported_by
        if eid in evidence and evidence[eid].doc_id in ws.documents
    ]
    best = max(tiers, key=sources.tier_rank) if tiers else "none"
    governing = claim.governing_date.isoformat() if claim.governing_date else "no date"
    return (
        f"{claim.claim_id} [{claim.status} · governing {governing} · "
        f"{len(claim.supported_by)} for / {len(claim.contradicted_by)} against · "
        f"best source {best}] {claim.text}"
    )


def _render_budget(ws: Workspace, rounds_left: int) -> str:
    remaining = ws.budget_remaining()
    elapsed = (datetime.now(UTC) - ws.started_at).total_seconds()
    seconds = max(0, int(ws.budget.max_seconds - elapsed))
    return (
        f"searches {remaining.max_searches}, fetches {remaining.max_fetches}, "
        f"deep reads {remaining.max_deep_reads}, tokens {remaining.max_tokens:,}, "
        f"about {seconds}s; search rounds left: {max(0, rounds_left)}"
    )


def _render_list(items: list[str], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else empty


# --- normalization helpers -----------------------------------------------------------


def _squash(text: str) -> str:
    return " ".join((text or "").split())


def _dedupe(items) -> list[str]:  # noqa: ANN001
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def _issued(ws: Workspace) -> dict[str, tuple[set[str], set[str]]]:
    """Per branch: the instructions already dispatched and the queries already run."""
    out: dict[str, tuple[set[str], set[str]]] = {}
    for task in ws.tasks:
        instructions, queries = out.setdefault(task.branch_id, (set(), set()))
        instructions.add(_squash(task.instruction).lower())
        for query in [*(task.result.queries_issued if task.result else []), *task.queries_hint]:
            queries.add(_squash(query).lower())
    return out


def _repeats(
    branch: str, instruction: str, queries: list[str], issued: dict[str, tuple[set[str], set[str]]]
) -> bool:
    instructions, done = issued.get(branch, (set(), set()))
    if instruction.lower() in instructions:
        return True
    return bool(queries) and all(query.lower() in done for query in queries)


def _hosts(domains: list[str]) -> list[str]:
    hosts: list[str] = []
    for domain in domains:
        host = re.sub(r"^[a-z]+://", "", domain.strip().lower()).split("/")[0].strip(".")
        if host and host not in hosts:
            hosts.append(host)
    return hosts

"""The root planner (docs/03 §3): the node that plans by *writing Python*.

This is where the "recursive language model" idea becomes concrete. The root does not
call a `make_plan` tool; it writes a cell that constructs `ws.plan` and the harness
executes it against the workspace. Two reasons the spec gives, and one it does not:

* it works with reasoning models regardless of native tool-calling support on the
  Nebius endpoint (docs/01 §4);
* the plan becomes an executable object rather than prose;
* and — the unstated one — it is the *same* mechanism the root uses later to inspect
  the workspace (`ws.evidence_for("b3")`, `ws.dates()`), so there is one sandbox and
  one mental model rather than a planning API plus an inspection API.

The ladder in `plan_run` is docs/03 §3 and §13 read together, and it degrades in a
specific order: a bad cell gets one repair turn, no cell at all drops to structured
output on the judge model (`fallback:plan_structured`), and a second failure falls back
to a fixed two-branch plan (`fallback:default_plan`). A run never dies here — an
unplanned question still gets searched, just less cleverly.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.language_models import BaseChatModel

from prime_search import events
from prime_search.models import root_model, structured
from prime_search.prompts import render
from prime_search.schemas import Branch, QueryUnderstanding, SearchPlan
from prime_search.tracing import get_logger
from prime_search.workspace import Workspace

_log = get_logger(component="root")

__all__ = ["DEFAULT_PLAN_BRANCHES", "PlanOutcome", "default_plan", "plan_run", "strategy_card"]

# docs/03 §3's planning contract; §10's depth table narrows it for `fast`.
MIN_BRANCHES, MAX_BRANCHES = 3, 7
FAST_MAX_BRANCHES = 2

# Fenced Python, or an unlabelled fence. Non-greedy so the *first* complete block
# wins: a reasoning model often narrates a sketch before the real cell, and the
# sketch is usually the one that does not run.
_PY_FENCE = re.compile(r"```(?:python|py)?\s*\n(.+?)```", re.DOTALL)

# docs/03 §13: "Empty plan (model failure twice): a default two-branch plan is used
# (primary policy + recent changes)".
DEFAULT_PLAN_BRANCHES = (
    (
        "b1",
        "What does the current governing policy document say about {objective}?",
        "primary_policy",
    ),
    (
        "b2",
        "What changed most recently in the policy governing {objective}?",
        "primary_policy",
    ),
)


class PlanOutcome:
    """A plan plus how it was reached.

    `fallback_tag` is `None` on the normal path and otherwise the docs/06 §2 tag the
    caller puts on the *root* LangSmith run — which is the only place a reviewer
    scanning traces will see that this run planned itself badly.
    """

    __slots__ = ("plan", "mode", "fallback_tag", "repairs")

    def __init__(
        self, plan: SearchPlan, mode: str, *, fallback_tag: str | None = None, repairs: int = 0
    ) -> None:
        self.plan = plan
        self.mode = mode
        self.fallback_tag = fallback_tag
        self.repairs = repairs


# --- strategy cards ----------------------------------------------------------------

# docs/03 §3 calls these "a compact search strategy card for the domain (the seed of
# what the roadmap calls procedural memory)" and quotes the CGM one verbatim; that
# text is reproduced exactly below.
#
# **The GLP-1 card is authored.** No spec contains one, so it is assembled from
# docs/11 A6, docs/00 S3/S4 and docs/08 — and deliberately written as *where to look*
# rather than *what is true*. A card that asserted "Part D cannot cover weight-loss
# drugs" would be handing the model an answer the bench is supposed to measure, which
# is the same teaching-to-the-test the 1.6 spec review flagged in search_agent.md.
_CARDS: dict[str, str] = {
    "cgm": (
        "Coverage criteria live in the DME MAC LCD (L33822); codes and frequency live "
        "in the companion article (A52464); the April 2023 revision changed the insulin "
        "requirement; always confirm the current revision date."
    ),
    "glp1": (
        "Medicare drug coverage splits by benefit: Part B covers drugs administered "
        "incident to a physician's service or through covered DME, Part D covers "
        "outpatient prescriptions - establish which one the question is about before "
        "anything else. Part D's statutory exclusions (Social Security Act 1860D-2(e)(2), "
        "which points at 1927(d)(2)) are the governing text for weight-management "
        "indications; read the exclusion itself rather than a summary of it. An FDA "
        "label indication and a Medicare coverage decision are different documents that "
        "can disagree: cite each separately and date both. Where a drug has more than "
        "one brand or indication (semaglutide, tirzepatide), the indication on the label "
        "decides which rule applies, so confirm which product the question names. CMS "
        "guidance on this has moved - prefer a dated CMS memo, manual section or fact "
        "sheet over any undated explainer."
    ),
}

_CARD_FALLBACK = (
    "No strategy card exists for this domain. Work from primary sources: find the "
    "governing statute, regulation or coverage document first, confirm its effective or "
    "revision date, and only then look for secondary explanations."
)


def strategy_card(domain: str) -> str:
    """The domain's search strategy card (docs/03 §3)."""
    return _CARDS.get(domain, _CARD_FALLBACK)


# --- the workspace API the root is shown -------------------------------------------

# docs/03 §3: the root is given "the workspace API (as a docstring)". Hand-written
# rather than introspected: `inspect.getdoc` over Workspace would pour ~200 lines of
# implementation notes into the prompt, most of it about persistence and the sandbox's
# trace hook, none of which helps write a plan.
WORKSPACE_API = '''\
ws.objective            str   - the user's question
ws.understanding        QueryUnderstanding - already classified, shown above
ws.budget               Budget - max_searches, max_fetches, max_deep_reads, max_agents,
                                 max_rounds, max_tokens, max_seconds
ws.plan                 SearchPlan | None  - YOU SET THIS
ws.documents            dict[doc_id, Document]   - empty until searching starts
ws.evidence             list[Evidence]           - empty until searching starts
ws.evidence_for(bid)    list[Evidence]  - evidence recorded for one branch
ws.dates()              list[(label, date|None)] - dates found so far
ws.budget_remaining()   Budget - what is left

Schema classes available in the cell: SearchPlan, Branch, QueryUnderstanding, Budget,
SearchTask, Evidence, Document, Claim, date, datetime. `print(...)` works and its
output comes back to you.'''


def _plan_payload(plan: SearchPlan, code: str | None) -> dict:
    """The `plan` event: the SearchPlan plus the cell that built it (docs/02 §4).

    docs/07 §4's Plan tab shows the root's plan code, the code-as-action a reviewer
    reads, and nothing else keeps it: the cell was a local variable here. `None` when
    the plan came from a fallback rung rather than code.
    """
    return {**plan.model_dump(mode="json"), "code": code}


def plan_run(
    ws: Workspace,
    *,
    prompt_set: str = "base",
    model: BaseChatModel | None = None,
    depth: str = "deep",
    max_branches: int | None = None,
) -> PlanOutcome:
    """Plan the run, by the docs/03 §3 ladder. Always returns a usable plan.

    Sets `ws.plan` as a side effect (the cell does it on the happy path; the fallback
    rungs assign it directly) so every rung leaves the workspace in the same state.
    """
    understanding = ws.understanding or _minimal_understanding(ws.objective)
    limit = max_branches or (FAST_MAX_BRANCHES if depth == "fast" else MAX_BRANCHES)
    minimum = 1 if depth == "fast" else MIN_BRANCHES
    chat = model or root_model()

    prompt = render(
        "plan",
        prompt_set,
        objective=ws.objective,
        understanding=understanding.model_dump_json(indent=2),
        workspace_api=WORKSPACE_API,
        strategy_card=strategy_card(understanding.domain),
        min_branches=minimum,
        max_branches=limit,
        budget=ws.budget.model_dump_json(indent=2),
    )

    transcript: list[Any] = [{"role": "user", "content": prompt}]
    problem: str | None = None

    # Rung 1 and 2: the cell, then exactly one repair turn (docs/03 §3: "on failure
    # asks once for a corrected block").
    for attempt in range(2):
        try:
            reply = chat.invoke(transcript)
        except Exception as exc:  # noqa: BLE001 - an endpoint failure drops to rung 3
            problem = f"{type(exc).__name__}: {exc}"
            _log.warning("root.plan_call_failed", attempt=attempt, error=problem)
            break

        code = _extract_code(reply.text)
        if code is None:
            problem = "no fenced Python block in the reply"
        else:
            ws.plan = None  # so a cell that runs but assigns nothing is caught below
            outcome = ws.exec(code)
            if not outcome.ok:
                problem = outcome.as_text()
            else:
                problem = _validate(ws.plan, minimum, limit, understanding)
                if problem is None:
                    _normalize(ws.plan, understanding, ws)
                    events.emit(ws.run_id, "plan", _plan_payload(ws.plan, code))
                    _log.info("root.planned", mode="code", repairs=attempt,
                              branches=len(ws.plan.branches))
                    return PlanOutcome(ws.plan, "code", repairs=attempt)

        _log.info("root.plan_retry", attempt=attempt, problem=(problem or "")[:300])
        if attempt == 0:
            transcript += [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": render("plan_repair", prompt_set, problem=problem)},
            ]

    # Rung 3: structured output on the judge model (docs/03 §3).
    try:
        plan = structured("judge", SearchPlan).invoke(prompt)
        problem = _validate(plan, minimum, limit, understanding)
        if problem is None:
            ws.plan = plan
            _normalize(plan, understanding, ws)
            events.emit(ws.run_id, "plan", _plan_payload(plan, None))
            _log.warning("root.plan_structured_fallback", branches=len(plan.branches))
            return PlanOutcome(plan, "structured", fallback_tag="fallback:plan_structured")
    except Exception as exc:  # noqa: BLE001 - rung 4 is the point
        problem = f"{type(exc).__name__}: {exc}"
        _log.warning("root.plan_structured_failed", error=problem)

    # Rung 4: docs/03 §13's default plan.
    plan = default_plan(ws, understanding, limit)
    ws.plan = plan
    events.emit(ws.run_id, "plan", _plan_payload(plan, None))
    events.emit_error(
        ws.run_id,
        f"planning fell back to the default plan: {problem or 'unknown'}",
        "plan",
        severity="warning",
        summary="The research followed a standard plan for this kind of question",
    )
    _log.warning("root.default_plan", problem=(problem or "")[:300])
    return PlanOutcome(plan, "default", fallback_tag="fallback:default_plan")


def default_plan(
    ws: Workspace, understanding: QueryUnderstanding, limit: int = MAX_BRANCHES
) -> SearchPlan:
    """docs/03 §13's "primary policy + recent changes" plan."""
    branches = [
        Branch(
            branch_id=branch_id,
            question=question.replace("{objective}", ws.objective),
            rationale="Default plan: the model did not produce a usable one.",
            source_hint=hint,  # type: ignore[arg-type]
            priority=index,
        )
        for index, (branch_id, question, hint) in enumerate(DEFAULT_PLAN_BRANCHES, start=1)
    ][: max(1, limit)]
    # The change-detection branch is the one that needs a time window, and it is the
    # second: giving both `time_range` would waste half the budget on recency-filtered
    # results when the criteria themselves are years old.
    plan = SearchPlan(
        understanding=understanding,
        branches=branches,
        stop_criteria=(
            "The governing document is cited with its effective or revision date, and "
            "the most recent change to it is identified or ruled out."
        ),
        budget=ws.budget,
    )
    return plan


# --- helpers -----------------------------------------------------------------------


def _extract_code(text: str) -> str | None:
    match = _PY_FENCE.search(text or "")
    if match:
        return match.group(1)
    # A model that answers with bare code and no fence at all. Accepted only when it
    # actually looks like the cell we asked for, so prose never reaches `exec`.
    stripped = (text or "").strip()
    return stripped if stripped.startswith("ws.plan") else None


def _validate(
    plan: Any, minimum: int, maximum: int, understanding: QueryUnderstanding
) -> str | None:
    """The docs/03 §3 planning contract. Returns the problem, or None if the plan is
    usable — phrased as an instruction, because it is fed back to the model verbatim."""
    if plan is None:
        return "the cell ran but did not assign ws.plan"
    if not isinstance(plan, SearchPlan):
        return f"ws.plan is a {type(plan).__name__}, not a SearchPlan"
    count = len(plan.branches)
    if count < minimum or count > maximum:
        return f"ws.plan has {count} branches; the contract requires {minimum}-{maximum}"
    ids = [branch.branch_id for branch in plan.branches]
    if len(set(ids)) != len(ids):
        return f"branch_ids must be unique; got {ids}"
    if not (plan.stop_criteria or "").strip():
        return "stop_criteria is empty; state what would make this question answered"
    empty = [branch.branch_id for branch in plan.branches if not branch.question.strip()]
    if empty:
        return f"these branches have an empty question: {empty}"
    # docs/03 §3: "a rule that change-detection questions must include a branch with
    # time_range='year'". SearchPlan has no time_range field - Branch does not either;
    # it lives on SearchTask - so the plan expresses it by naming recency in a branch,
    # and `dispatch` sets time_range on that branch's task. Checked as a *hint*,
    # because refusing an otherwise good plan over a missing keyword would trade a
    # working run for a spec technicality.
    return None


def _normalize(plan: SearchPlan, understanding: QueryUnderstanding, ws: Workspace) -> None:
    """Make the plan self-consistent whatever the model put in it.

    A model that constructs `SearchPlan(...)` by hand routinely passes a *rewritten*
    understanding or a budget it invented. Neither is its call: the understanding came
    from an earlier node and the budget from config, and a plan carrying a fabricated
    `max_searches` would be silently believed by `dispatch`.
    """
    plan.understanding = understanding
    plan.budget = ws.budget
    for index, branch in enumerate(plan.branches, start=1):
        if not branch.branch_id:
            branch.branch_id = f"b{index}"
        if not branch.rationale:
            branch.rationale = "(none given)"


def _minimal_understanding(objective: str) -> QueryUnderstanding:
    """Used only when `plan` runs without `understand` having set one — the graph
    always runs them in order, but the planner is also called directly in tests and
    from the sandbox, and a None here would be an AttributeError inside a cell."""
    return QueryUnderstanding(
        normalized_question=objective,
        domain="other",
        question_type="eligibility",
        time_sensitivity="medium",
    )

"""The critic (docs/03 §7): before synthesis, is what the run found actually right?

The expensive, single check. Where the judge asks "is there enough?", the critic reads
the claims *with their evidence* - passage, tier, dates - plus the documents fetched
and the searches run, and answers §7's six questions adversarially: single-source
claims, secondary sources used where a primary one was fetched, missing or superseded
dates, interpretations the plan missed, contradictions the claim graph did not flag,
and the one search most likely to change the answer.

It runs on the root model and answers in fenced JSON rather than a native tool call
(docs/01 §4). The ladder mirrors the planner's (docs/11): fenced JSON, one repair turn,
structured output on the judge model, and finally no report at all - never a failed
run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from prime_search import events
from prime_search.agents.judge import (
    _branch_ids,
    _charge,
    _dedupe,
    _hosts,
    _issued,
    _repeats,
    _squash,
)
from prime_search.evidence.graph import supersession_edges
from prime_search.models import critic_model, parse_fenced_json, structured
from prime_search.prompts import render
from prime_search.schemas import CriticReport, Document, Evidence, SearchTask
from prime_search.tracing import get_logger
from prime_search.workspace import Workspace

_log = get_logger(component="critic")

__all__ = [
    "PSEUDO_BRANCH",
    "SKIPPED_TAG",
    "STRUCTURED_TAG",
    "CriticOutcome",
    "build_prompt",
    "normalize_report",
    "run_critic",
]

MAX_RECOMMENDED = 3  # docs/03 §7: "dispatch `recommended_searches` (max 3)"
MAX_QUERIES = 3
MAX_CLAIMS = 40
MAX_EVIDENCE_PER_SIDE = 3
MAX_PASSAGE_CHARS = 300
MAX_DOCUMENTS = 30
MAX_FINDINGS = 8
MAX_FINDING_CHARS = 300
# A contradiction entry that is not a known claim id must say something: "c9" for a
# claim that does not exist, or "yes", is dropped; a sentence naming both sides is kept.
MIN_DESCRIPTION_CHARS = 20
# Where a recommended search goes when it names no branch the plan has. docs/07 §3
# labels critic-triggered tasks `critic`; the task id carries that label too.
PSEUDO_BRANCH = "critic"
STRUCTURED_TAG = "fallback:critic_structured"
SKIPPED_TAG = "fallback:critic_skipped"
_CLAIM_ID = re.compile(r"c\d+")
_LIST_FIELDS = (
    "weak_claims",
    "missing_interpretations",
    "source_independence_issues",
    "secondary_when_primary_exists",
    "outdated_sources",
    "contradictions",
    "recommended_searches",
)
_REVIEW_MODE = {
    True: (
        "A re-search is still possible. If `completion_probability` is below 0.7, your "
        "`recommended_searches` (at most 3) will be run and you will review the result once "
        "more."
    ),
    False: (
        "This is the final review: no more searches will run, and the answer will be written "
        "from what is shown. Still list what you would search, and say plainly what is weak."
    ),
}


@dataclass
class CriticOutcome:
    report: CriticReport | None
    mode: str  # fenced_json | fenced_json_repair | structured | skipped
    fallback_tag: str | None = None
    error: str | None = None


class _Unusable(ValueError):
    """The reply held no valid report."""


def run_critic(
    ws: Workspace,
    *,
    state_round: int,
    may_search: bool,
    prompt_set: str = "base",
    model: BaseChatModel | None = None,
) -> CriticOutcome:
    """Review the run so far. Never raises (docs/01 §9: the graph proceeds)."""
    prompt = build_prompt(ws, may_search=may_search, prompt_set=prompt_set)
    tag: str | None = None
    try:
        report, mode = _fenced(model or critic_model(), prompt, ws, prompt_set)
    except Exception as exc:  # noqa: BLE001 - an endpoint error or an unusable repair
        first = f"{type(exc).__name__}: {exc}"[:300]
        _log.warning("critic.fenced_failed", run_id=ws.run_id, error=first)
        caller = structured("judge", CriticReport)
        try:
            report = caller.invoke(prompt)
            mode, tag = "structured", STRUCTURED_TAG
        except Exception as fallback:  # noqa: BLE001 - no report is not a failed run
            error = f"{first}; then {type(fallback).__name__}: {fallback}"[:500]
            _log.warning("critic.skipped", run_id=ws.run_id, error=error)
            events.emit(ws.run_id, "error", {"message": f"critic: {error}", "node": "critic"})
            _charge(ws, caller, prompt)
            return CriticOutcome(None, "skipped", SKIPPED_TAG, error)
        _charge(ws, caller, prompt)
    return CriticOutcome(normalize_report(report, ws, state_round=state_round), mode, tag)


def _fenced(
    chat: BaseChatModel, prompt: str, ws: Workspace, prompt_set: str
) -> tuple[CriticReport, str]:
    """Fenced JSON with one repair turn (docs/01 §9). Raises when both replies are
    unusable, or at once when the endpoint itself fails - that is not a formatting
    problem a repair turn can fix."""
    reply = chat.invoke([HumanMessage(content=prompt)])
    ws.charge_tokens(reply, prompt)
    try:
        return _parse(reply), "fenced_json"
    except _Unusable as problem:
        repair = render("critic_repair", prompt_set, problem=str(problem))
        second = chat.invoke([HumanMessage(content=prompt), reply, HumanMessage(content=repair)])
        ws.charge_tokens(second, prompt + repair)
        return _parse(second), "fenced_json_repair"


def _parse(reply: Any) -> CriticReport:
    try:
        return CriticReport.model_validate(_coerce(parse_fenced_json(reply.text)))
    except Exception as exc:
        raise _Unusable(f"{type(exc).__name__}: {exc}"[:500]) from exc


def _coerce(data: Any) -> Any:
    """Accept the near-misses a model writes that carry the same meaning: `null` for an
    empty list, a recommended search given as a bare instruction, and a search without
    the fields the harness assigns anyway (`task_id`, `round`, `branch_id`)."""
    if not isinstance(data, dict):
        return data
    for key in _LIST_FIELDS:
        if data.get(key) is None:
            data[key] = []
    if data.get("reasoning") is None:
        data["reasoning"] = ""
    searches: list[Any] = []
    for item in data["recommended_searches"] if isinstance(data["recommended_searches"], list) else []:
        if isinstance(item, str):
            item = {"instruction": item}
        if isinstance(item, dict):
            item = {**item, "task_id": item.get("task_id") or "", "round": item.get("round") or 0}
            item["branch_id"] = item.get("branch_id") or PSEUDO_BRANCH
            item["queries_hint"] = item.get("queries_hint") or []
            item["include_domains"] = item.get("include_domains") or []
        searches.append(item)
    data["recommended_searches"] = searches
    return data


# --- normalization -----------------------------------------------------------------


def normalize_report(raw: CriticReport, ws: Workspace, *, state_round: int) -> CriticReport:
    """The report the graph acts on: only ids that exist, findings trimmed, and
    recommended searches turned into dispatchable tasks the harness has named."""
    claim_ids = {claim.claim_id for claim in ws.claims}

    def known_claims(items: list[str]) -> list[str]:
        return _dedupe(item for item in map(_squash, items) if item in claim_ids)[:MAX_FINDINGS]

    def notes(items: list[str]) -> list[str]:
        return _dedupe(_squash(item)[:MAX_FINDING_CHARS] for item in items)[:MAX_FINDINGS]

    contradictions = [
        entry[:MAX_FINDING_CHARS]
        for entry in map(_squash, raw.contradictions)
        if entry in claim_ids
        or (len(entry) >= MIN_DESCRIPTION_CHARS and not _CLAIM_ID.fullmatch(entry))
    ]
    return CriticReport(
        weak_claims=known_claims(raw.weak_claims),
        missing_interpretations=notes(raw.missing_interpretations),
        source_independence_issues=notes(raw.source_independence_issues),
        secondary_when_primary_exists=known_claims(raw.secondary_when_primary_exists),
        outdated_sources=_doc_ids(raw.outdated_sources, ws.documents),
        contradictions=_dedupe(contradictions)[:MAX_FINDINGS],
        recommended_searches=_recommended(raw.recommended_searches, ws, state_round),
        completion_probability=min(1.0, max(0.0, raw.completion_probability)),
        reasoning=raw.reasoning.strip(),
    )


def _doc_ids(items: list[str], documents: dict[str, Document]) -> list[str]:
    """Doc ids, accepting an external id (`L33822`) for every document that carries it."""
    by_external: dict[str, list[str]] = {}
    for document in documents.values():
        if document.document_id_external:
            by_external.setdefault(document.document_id_external.lower(), []).append(document.doc_id)
    found: list[str] = []
    for item in map(_squash, items):
        for doc_id in [item] if item in documents else by_external.get(item.lower(), []):
            if doc_id not in found:
                found.append(doc_id)
    return found[:MAX_FINDINGS]


def _recommended(proposed: list[SearchTask], ws: Workspace, state_round: int) -> list[SearchTask]:
    known = set(_branch_ids(ws))
    issued = _issued(ws)
    kept: list[SearchTask] = []
    for task in proposed:
        if len(kept) >= MAX_RECOMMENDED:
            break
        instruction = _squash(task.instruction)
        if not instruction:
            continue
        branch = task.branch_id.strip() if task.branch_id.strip() in known else PSEUDO_BRANCH
        queries = _dedupe(map(_squash, task.queries_hint))[:MAX_QUERIES]
        if _repeats(branch, instruction, queries, issued):
            continue
        issued.setdefault(branch, (set(), set()))[0].add(instruction.lower())
        kept.append(
            SearchTask(
                task_id=f"{branch}-r{state_round}-critic{len(kept) + 1}",
                branch_id=branch,
                round=state_round,
                instruction=instruction,
                queries_hint=queries,
                include_domains=_hosts(task.include_domains),
                time_range=task.time_range if task.time_range in {"year", "month"} else None,
            )
        )
    return kept


# --- rendering ---------------------------------------------------------------------


def build_prompt(ws: Workspace, *, may_search: bool, prompt_set: str = "base") -> str:
    """docs/03 §7's input: the question, every claim with its supporting and
    contradicting evidence (text, tier, dates), the search trajectory, the stop
    criteria - plus the documents and the judge's latest coverage, which the six
    questions need."""
    return render(
        "critic",
        prompt_set,
        question=ws.objective,
        stop_criteria=ws.plan.stop_criteria if ws.plan else "(no plan was made)",
        branches=_render_branches(ws),
        claims=_render_claims(ws),
        documents=_render_documents(ws),
        contested=", ".join(ws.contradictions) or "(none)",
        trajectory=_render_trajectory(ws),
        coverage=_render_coverage(ws),
        review_mode=_REVIEW_MODE[bool(may_search)],
    )


def _render_branches(ws: Workspace) -> str:
    planned = {branch.branch_id: branch for branch in ws.plan.branches} if ws.plan else {}
    lines: list[str] = []
    for branch_id in _branch_ids(ws):
        branch = planned.get(branch_id)
        if branch is None:
            lines.append(f"- {branch_id}: searches added outside the plan")
        else:
            lines.append(
                f"- {branch_id} (priority {branch.priority}, look in: {branch.source_hint}): "
                f"{branch.question}"
            )
    return "\n".join(lines) or "(no branches)"


def _render_claims(ws: Workspace) -> str:
    if not ws.claims:
        return "(no claims were assembled)"
    evidence = {item.evidence_id: item for item in ws.evidence}
    lines: list[str] = []
    for claim in ws.claims[:MAX_CLAIMS]:
        governing = claim.governing_date.isoformat() if claim.governing_date else "no governing date"
        lines.append(
            f"{claim.claim_id} [{claim.status} · confidence {claim.confidence:.2f} · "
            f"{governing} · branch {claim.branch_id}] {claim.text}"
        )
        for sign, ids in (("+", claim.supported_by), ("-", claim.contradicted_by)):
            for evidence_id in ids[:MAX_EVIDENCE_PER_SIDE]:
                if (item := evidence.get(evidence_id)) is not None:
                    lines.append(f"  {sign} {_evidence_line(item, ws.documents.get(item.doc_id))}")
            if len(ids) > MAX_EVIDENCE_PER_SIDE:
                lines.append(f"  {sign} ... and {len(ids) - MAX_EVIDENCE_PER_SIDE} more")
    if len(ws.claims) > MAX_CLAIMS:
        lines.append(f"... and {len(ws.claims) - MAX_CLAIMS} more claims")
    return "\n".join(lines)


def _evidence_line(item: Evidence, document: Document | None) -> str:
    tier = document.source_tier if document else "unknown"
    label = _document_label(document) if document else item.doc_id
    dated = item.effective_date or (
        (document.revision_date or document.effective_date) if document else None
    )
    when = f"dated {dated.isoformat()}" if dated else "undated"
    passage = _squash(item.evidence_text)[:MAX_PASSAGE_CHARS]
    return f'{item.evidence_id} · {tier} · {label} · {when}: "{passage}"'


def _document_label(document: Document) -> str:
    name = document.document_id_external or document.publisher or urlparse(document.url).netloc
    return " ".join(part for part in (name, document.doc_type) if part)


def _render_documents(ws: Workspace) -> str:
    fetched = [document for document in ws.documents.values() if document.is_fetched]
    if not fetched:
        return "(no documents were fetched)"
    superseded = supersession_edges(ws.documents)
    lines: list[str] = []
    for document in fetched[:MAX_DOCUMENTS]:
        parts = [document.doc_id, document.source_tier, _document_label(document)]
        if document.revision_date:
            parts.append(f"revised {document.revision_date.isoformat()}")
        if document.effective_date:
            parts.append(f"effective {document.effective_date.isoformat()}")
        if not (document.revision_date or document.effective_date):
            parts.append("no date found")
        if document.doc_id in superseded:
            parts.append(f"superseded by {superseded[document.doc_id]}")
        lines.append(f'- {" · ".join(parts)} · "{_squash(document.title)[:120]}"')
    if len(fetched) > MAX_DOCUMENTS:
        lines.append(f"- ... and {len(fetched) - MAX_DOCUMENTS} more")
    return "\n".join(lines)


def _render_trajectory(ws: Workspace) -> str:
    lines: list[str] = []
    for branch_id in _branch_ids(ws):
        tasks = [task for task in ws.tasks if task.branch_id == branch_id]
        if not tasks:
            lines.append(f"{branch_id}: not searched")
            continue
        lines.append(f"{branch_id}:")
        for task in tasks:
            result = task.result
            queries = "; ".join(f'"{query}"' for query in (result.queries_issued if result else []))
            found = len(result.evidence_ids) if result else 0
            lines.append(
                f"- {task.task_id} (round {task.round}, {task.status}): {task.instruction}"
                f" — queries: {queries or 'none recorded'} — evidence {found}"
            )
            if result and result.unresolved:
                lines.append(f"  unresolved: {result.unresolved}")
    return "\n".join(lines) or "(no searches were run)"


def _render_coverage(ws: Workspace) -> str:
    if not ws.verdicts:
        return "(the judge has not run)"
    verdict = ws.verdicts[-1]
    coverage = ", ".join(f"{branch} {status}" for branch, status in verdict.coverage.items())
    missing = "; ".join(verdict.missing) or "nothing listed"
    state = "sufficient" if verdict.sufficient else "insufficient"
    return f"round {verdict.round}: {state}; {coverage or 'no coverage recorded'}; missing: {missing}"

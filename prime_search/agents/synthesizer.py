"""The `synthesize` node (docs/03 §8): evidence and claims into a cited `Answer`.

docs/03 §8 describes "streaming tokens, then a structured pass on the judge model to
produce `Answer` fields ... or a single structured call if streaming structured output
proves unreliable." This module takes the third option the sentence implies: **stream
the prose, compute the fields.**

`citations`, `effective_dates`, `claims` and `contradictions` are all derivable from
the claim graph and the evidence store, by functions that already exist and are already
tested (`evidence/cite.py`, `evidence/graph.py`). Asking a model to restate them is a
chance to get them wrong — a fabricated revision date in `effective_dates` is exactly
the failure this system exists to prevent — and costs a second call. So the model
writes `summary` and `body_markdown`; everything else is assembled.

What the model writes is then **checked against** the assembled data: docs/03 §8's
post-hoc citation validation drops any `[n]` that does not resolve to an evidence id.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from prime_search import events
from prime_search.evidence.cite import build_citations, effective_dates_section, source_line
from prime_search.models import root_model, token_usage
from prime_search.prompts import render
from prime_search.schemas import Answer, Citation, Evidence
from prime_search.tracing import get_logger
from prime_search.workspace import Workspace

_log = get_logger(component="synthesize")

__all__ = ["SECTION_HEADINGS", "confidence_for", "safe_token_sink", "synthesize"]

# docs/03 §8's section order. Asserted in tests, because this list is what the gate
# and the docs/05 §2 completeness evaluator both look for.
SECTION_HEADINGS = (
    "Answer",
    "Criteria / Details",
    "Codes and documentation",
    "Effective dates relied on",
    "Contradictions and caveats",
    "Unknowns / not verified",
    "Sources",
)

_CITATION = re.compile(r"\[(\d{1,3})\]")

# Citation forms models actually emit instead of `[n]`, normalized before validating so
# the answer the reader sees uses one form and docs/03 §8's check sees all of them.
#
# Both were observed live, in consecutive runs of the same question:
#   `【3】`          a CJK lenticular bracket
#   `【1†L1-L3】`    the same bracket with a dagger and a line range
#
# Each sailed straight past `\[(\d+)\]`: unmapped numbers were neither checked nor
# dropped, and for those runs the §8 guarantee was silently off. The trailing segment
# is discarded rather than kept - it names lines in a source the citation already
# identifies, and nothing downstream can resolve it.
_ALT_CITATION = re.compile("[【［]\\s*(\\d{1,3})(?:\\s*†[^】］]*)?\\s*[】］]")

# How much of each passage the synthesis prompt carries. The answer quotes from these,
# so they cannot be clipped as hard as the sub-agent's tool returns (700) — but the
# whole evidence set goes in one prompt, so they cannot be unbounded either.
MAX_EVIDENCE_CHARS = 900

# docs/02 §2.7 gives `Answer.confidence` no derivation, and no other spec defines one.
# Authored here so the docs/05 §2 evaluator scores against something written down:
# start from the mean confidence of supported claims, then discount for the two
# conditions that most often make a confident-looking answer wrong.
NO_PRIMARY_SOURCE_PENALTY = 0.8
UNRESOLVED_BRANCH_PENALTY = 0.8
MIN_CONFIDENCE = 0.05
# The tier table (primitives/sources.py) has exactly one primary tier.
_PRIMARY_TIERS = {"primary_policy"}


def synthesize(
    ws: Workspace,
    *,
    prompt_set: str = "base",
    model: BaseChatModel | None = None,
    on_token: Callable[[str], None] | None = None,
    unresolved: list[str] | None = None,
) -> Answer:
    """Produce the run's `Answer`. Never raises on an empty run.

    `on_token` receives the streamed body as it arrives, so the CLI can render it live
    and the event stream can carry `token` events (docs/02 §4) — the same callback
    serves both, rather than this module knowing about either.
    """
    citations = build_citations(ws.evidence, ws.documents)
    unresolved_notes = unresolved if unresolved is not None else list(ws.unknowns)

    # docs/03 §13: "No evidence at all: synthesis returns an answer consisting of the
    # scope warning/unknowns only; the UI shows it plainly rather than an error."
    if not citations:
        return _empty_answer(ws, unresolved_notes)

    prompt = render(
        "synthesize",
        prompt_set,
        question=ws.objective,
        understanding=(
            ws.understanding.model_dump_json(indent=2) if ws.understanding else "{}"
        ),
        evidence=_render_evidence(ws, citations),
        claims=_render_claims(ws),
        unresolved=_render_unresolved(unresolved_notes),
    )

    body, estimated = _stream(model or root_model(), prompt, on_token, ws)
    body, dropped = _validate_citations(body, citations)
    if dropped:
        _log.warning("synthesize.citations_dropped", numbers=sorted(dropped))
        events.emit(ws.run_id, "error", {"message": f"dropped unmapped citations {sorted(dropped)}", "node": "synthesize"})

    warning = ws.understanding.scope_warning if ws.understanding else None
    body = _ensure_scope_warning(body, warning)
    # docs/03 §8 derives the answer's fields "from the streamed body plus the claim
    # graph". Keeping every gathered passage in `citations` overstated what the answer
    # rested on - the CLI footer counted them and the docs/04 §7 citation evaluator
    # reads the field - so the list is narrowed to the numbers the body actually cites.
    # Numbers are NOT reassigned: `[3]` in the body still means citation 3.
    cited = _cited_numbers(body)
    used = [citation for citation in citations if citation.n in cited] or citations
    body = _ensure_budget_note(body, ws)
    body = _ensure_sources_section(body, used, ws)
    answer = Answer(
        summary=_summary_from(body, warning),
        body_markdown=body,
        claims=list(ws.claims),
        citations=used,
        effective_dates=effective_dates_section(_cited_evidence(ws, used), ws.documents),
        contradictions=list(ws.contradictions),
        unknowns=unresolved_notes,
        confidence=confidence_for(ws),
        scope_warning=ws.understanding.scope_warning if ws.understanding else None,
    )
    # docs/02 section 4: the `answer` payload is the `Answer`, not a summary of it -
    # the UI's answer panel renders the model, and a hand-made dict left the replay
    # without the body, the citations or the dates.
    events.emit(ws.run_id, "answer", answer)
    if estimated:
        _log.info("synthesize.tokens_estimated", run_id=ws.run_id)
    return answer


def confidence_for(ws: Workspace) -> float:
    """`Answer.confidence` (docs/02 §2.7), by the formula documented at the top.

    Deliberately not asked of a model: a number a model picks for its own answer is
    not a measurement, and this one feeds the docs/05 §2 calibration evaluator.
    """
    supported = [claim for claim in ws.claims if claim.status == "supported"]
    if not supported:
        # Contested or weak claims only: the system found things and could not stand
        # behind them. Halfway is the honest report, not zero.
        base = 0.4 if ws.claims else 0.0
    else:
        base = sum(claim.confidence for claim in supported) / len(supported)

    has_primary = any(
        document.source_tier in _PRIMARY_TIERS for document in ws.documents.values()
    )
    if not has_primary:
        base *= NO_PRIMARY_SOURCE_PENALTY

    planned = {branch.branch_id for branch in (ws.plan.branches if ws.plan else [])}
    covered = {item.branch_id for item in ws.evidence}
    if planned - covered:
        base *= UNRESOLVED_BRANCH_PENALTY

    return round(max(MIN_CONFIDENCE, min(1.0, base)), 3) if ws.claims else 0.0


# --- rendering the prompt ----------------------------------------------------------


def _render_evidence(ws: Workspace, citations: list[Citation]) -> str:
    """Each passage with its citation number, tier and date — the numbers the model
    must use are the ones it is shown, which is why they are computed first."""
    by_id = {item.evidence_id: item for item in ws.evidence}
    blocks: list[str] = []
    for citation in citations:
        item = by_id.get(citation.evidence_id)
        if item is None:
            continue
        document = ws.documents.get(item.doc_id)
        tier = document.source_tier if document else "unknown"
        dated = _date_note(item, document)
        text = item.evidence_text
        if len(text) > MAX_EVIDENCE_CHARS:
            text = text[:MAX_EVIDENCE_CHARS].rstrip() + " [...]"
        # No section appended: `citation.label` is built by `cite.citation_label(
        # document, item.location.section)` and already carries it. A second copy made
        # every line read "...§CODING GUIDELINES, revision effective 2025-02-18,
        # §CODING GUIDELINES" - and a live answer copied that into its Sources list.
        blocks.append(
            f"[{citation.n}] {citation.label}\n"
            f"    tier: {tier} | stance: {item.stance}{dated}\n"
            f"    claim: {item.claim_text}\n"
            f'    passage: "{text}"'
        )
    return "\n\n".join(blocks)


def _cited_numbers(body: str) -> set[int]:
    """The citation numbers the answer actually uses."""
    return {int(number) for number in _CITATION.findall(body)}


def _cited_evidence(ws: Workspace, citations: list[Citation]) -> list[Evidence]:
    """The evidence behind a citation list, in citation order.

    `effective_dates` is the section the answer is graded on for currency (docs/05
    section 2), so it must list the dates the answer relied on - not every document the
    run happened to open.
    """
    by_id = {item.evidence_id: item for item in ws.evidence}
    return [by_id[c.evidence_id] for c in citations if c.evidence_id in by_id]


def _ensure_scope_warning(body: str, warning: str | None) -> str:
    """docs/03 section 8: "Carry `scope_warning` from understanding into the answer
    verbatim."

    The prompt asks for it; this makes it true. A warning that the question is out of
    scope, or asks for an individual coverage decision, is the one sentence the reader
    most needs and the one a model is most likely to smooth away.
    """
    if not warning or warning in body:
        return body
    match = re.search(r"^##+\s*Answer\s*$", body, re.MULTILINE)
    if match is None:
        return f"## Answer\n\n{warning}\n\n{body}"
    cut = match.end()
    return f"{body[:cut]}\n\n{warning}\n{body[cut:].lstrip()}"


def _date_note(item: Evidence, document: object) -> str:
    revision = getattr(document, "revision_date", None)
    effective = getattr(document, "effective_date", None)
    if item.effective_date:
        return f" | date in passage: {item.effective_date.isoformat()}"
    if revision:
        return f" | document revised: {revision.isoformat()}"
    if effective:
        return f" | document effective: {effective.isoformat()}"
    return " | no date on this document"


def _render_claims(ws: Workspace) -> str:
    if not ws.claims:
        return "(none assembled)"
    lines = []
    for claim in ws.claims:
        governing = (
            f", governing date {claim.governing_date.isoformat()}"
            if claim.governing_date
            else ""
        )
        lines.append(
            f"- [{claim.status}{governing}] {claim.text} "
            f"(branch {claim.branch_id}, {len(claim.supported_by)} supporting, "
            f"{len(claim.contradicted_by)} contradicting)"
        )
    return "\n".join(lines)


def _render_unresolved(notes: list[str]) -> str:
    return "\n".join(f"- {note}" for note in notes) if notes else "(nothing reported)"


# --- the model call ----------------------------------------------------------------


def _stream(
    model: BaseChatModel,
    prompt: str,
    on_token: Callable[[str], None] | None,
    ws: Workspace,
) -> tuple[str, bool]:
    """Stream the body, returning it whole plus whether token usage was estimated.

    Falls back to a plain invoke if the endpoint will not stream: a run that has done
    all the searching must not die at the last step over a transport feature.
    """
    sink = safe_token_sink(on_token)

    def emit(text: str) -> None:
        """docs/02 §4: `token | {text} | streaming answer (synthesis only)`.

        The in-process callback alone was not enough: `events.jsonl` then contained no
        answer text at all, so 2.4's replay of a past run could not reproduce the
        streamed answer it is supposed to replay.
        """
        events.emit(ws.run_id, "token", {"text": text})
        sink(text)

    pieces: list[str] = []
    estimated = False
    try:
        last = None
        for chunk in model.stream(prompt):
            last = chunk if last is None else last + chunk
            text = chunk.text
            if text:
                pieces.append(text)
                emit(text)
        if last is not None:
            ws.charge_tokens(last)
            estimated = token_usage(last)[2]
    except Exception as exc:  # noqa: BLE001 - see docstring
        _log.warning("synthesize.stream_failed", error=f"{type(exc).__name__}: {exc}")
        pieces = []
        message = model.invoke(prompt)
        text = message.text
        emit(text)
        pieces.append(text)
        ws.charge_tokens(message)
        estimated = token_usage(message)[2]
    return "".join(pieces).strip(), estimated


def safe_token_sink(on_token: Callable[[str], None] | None) -> Callable[[str], None]:
    """Wrap the caller's token sink so it cannot end the run.

    Measured, not hypothetical: a console that could not encode U+202F raised out of
    the callback, out of the stream, into the `invoke` fallback, out of *that*, and
    killed a run that had already gathered all ten of its evidence items. Whatever is
    watching a run - a terminal, an SSE connection that just dropped - is downstream of
    the answer, and downstream failures do not propagate upstream.
    """
    if on_token is None:
        return lambda _text: None

    failed = False

    def emit(text: str) -> None:
        nonlocal failed
        if not text or failed:
            return
        try:
            on_token(text)
        except Exception as exc:  # noqa: BLE001 - see docstring
            failed = True  # log once, not once per token
            _log.warning("synthesize.token_sink_failed", error=f"{type(exc).__name__}: {exc}")

    return emit


# --- post-hoc validation -----------------------------------------------------------


def _validate_citations(body: str, citations: list[Citation]) -> tuple[str, set[int]]:
    """docs/03 §8: "every `[n]` must map to an evidence id; unmapped citations are
    removed and logged (this feeds the citation-correctness evaluator)."

    Removed, not renumbered: renumbering would silently repoint a surviving citation
    at a different passage, turning a visible gap into an invisible misattribution.
    """
    body = _ALT_CITATION.sub(lambda match: f"[{int(match.group(1))}]", body)
    valid = {citation.n for citation in citations}
    dropped: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if number in valid:
            return match.group(0)
        dropped.add(number)
        return ""

    cleaned = _CITATION.sub(replace, body)
    # Only tidy the spacing the removal itself created.
    cleaned = re.sub(r" +([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned, dropped


def _ensure_sources_section(body: str, citations: list[Citation], ws: Workspace) -> str:
    """Write the Sources list from `citations`, replacing the model's if it wrote one.

    Replaced rather than merely appended-when-missing. The model is shown every gathered
    passage, so it lists every one — a live answer cited seven and printed nine sources,
    which is a reader following `[4]` to a numbered list that does not agree with
    `Answer.citations` or with the docs/04 §7 evaluator. The list is fully derivable
    from the citations the body actually uses, so deriving it is the only way the three
    cannot disagree.
    """
    lines = []
    for citation in citations:
        document = ws.documents.get(citation.doc_id)
        if document is None:
            continue
        item = next(
            (e for e in ws.evidence if e.evidence_id == citation.evidence_id), None
        )
        lines.append(source_line(citation.n, document, item.location.section if item else None))
    if not lines:
        return body
    match = re.search(r"^##+\s*Sources\b.*$", body, re.MULTILINE)
    trimmed = body[: match.start()].rstrip() if match else body.rstrip()
    return trimmed + "\n\n## Sources\n\n" + "\n".join(lines) + "\n"


def _ensure_budget_note(body: str, ws: Workspace) -> str:
    """docs/01 §9: the answer's unknowns section must state that the budget was hit.

    `collect` puts the sentence in `ws.unknowns` and the prompt shows it, but a model
    summarizing its unknowns paraphrases the retrieval gaps and drops this one — and it
    is the single line that tells a reader why the answer is thin. Appended under the
    existing heading rather than reworded into the model's prose.
    """
    notes = [note for _, note in ws.exhausted_limits() if note not in body]
    if not notes:
        return body
    bullets = "\n".join(f"- {note}" for note in notes)
    match = re.search(r"^##+\s*Unknowns[^\n]*$", body, re.MULTILINE)
    if match is None:
        return body.rstrip() + "\n\n## Unknowns / not verified\n\n" + bullets + "\n"
    # Insert at the end of that section, before whatever heading follows it.
    following = re.search(r"^##+\s", body[match.end():], re.MULTILINE)
    cut = match.end() + (following.start() if following else len(body) - match.end())
    return body[:cut].rstrip() + "\n" + bullets + "\n\n" + body[cut:].lstrip()


def _summary_from(body: str, warning: str | None = None) -> str:
    """`Answer.summary` is the Answer section (docs/02 §2.7: "2-4 sentence direct
    answer"), taken from the body rather than requested separately so the two can
    never disagree.

    The scope warning is stripped back out. It is deliberately the first line of the
    body, but §2.7 asks this field for the *answer*, and it is what the UI shows as a
    one-line summary — leading every out-of-scope answer with the caveat instead of the
    finding would bury it. `Answer.scope_warning` carries the sentence separately.
    """
    match = re.search(r"^##+\s*Answer\s*$(.+?)(?=^##|\Z)", body, re.MULTILINE | re.DOTALL)
    text = (match.group(1) if match else body).strip()
    if warning:
        text = text.replace(warning, "", 1).strip()
    text = _CITATION.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1000]


def _empty_answer(ws: Workspace, unresolved: list[str]) -> Answer:
    """docs/03 §13's no-evidence answer: what we could not establish, said plainly."""
    warning = ws.understanding.scope_warning if ws.understanding else None
    unknowns = unresolved or ["The search returned no usable evidence for this question."]
    parts = ["## Answer", ""]
    if warning:
        parts += [warning, ""]
    parts += [
        "No answer is given: the search did not produce any verified passage from a "
        "source document, and this system does not answer coverage questions from "
        "memory.",
        "",
        "## Unknowns / not verified",
        "",
    ]
    parts += [f"- {note}" for note in unknowns]
    body = "\n".join(parts) + "\n"
    answer = Answer(
        summary="No verified evidence was found for this question.",
        body_markdown=body,
        claims=[],
        citations=[],
        effective_dates=[],
        contradictions=[],
        unknowns=unknowns,
        confidence=0.0,
        scope_warning=warning,
    )
    events.emit(ws.run_id, "answer", answer)
    return answer

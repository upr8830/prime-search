"""The claim graph (docs/04 §4).

Turns a pile of evidence into claims that carry a *status* — the answer to "may this
be stated, and how firmly". docs/04 §1's consumer rule lives here: a coverage claim
is `supported` only when something primary or official backs it.

The graph is **derived, never stored**. Claims, statuses, contradiction and
supersession all follow from the evidence and the documents, so recomputing is the
only way they cannot drift apart. docs/04 §6 says "graph edges: inside state.json",
but `RunRecord` has no edge field and needs none: `supersession_edges()` recomputes
them from the documents whenever the UI or the critic asks.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from prime_search.evidence.store import claim_tokens
from prime_search.primitives import within
from prime_search.schemas import Claim, Document, Evidence

# docs/04 §4 thresholds, named rather than inlined because the critic and the
# evaluators (docs/05 §2) test against the same numbers.
PRIMARY_QUALITY = 0.85  # tier >= official_secondary
CONFIDENT = 0.6  # an item worth counting for or against a claim
JACCARD_MERGE = 0.6  # token overlap at which two claim texts are one claim
CONTESTED_PENALTY = 0.3


def jaccard(left: str, right: str) -> float:
    """Token Jaccard on claim text. docs/04 §4 calls for "a simple embedding-free
    similarity"; an embedding step is a docs/10 roadmap item."""
    a, b = claim_tokens(left), claim_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class ClaimGraph:
    """Claims plus the edges docs/04 §4 draws around them."""

    claims: list[Claim] = field(default_factory=list)
    # older doc_id -> the newest doc_id for that external id (docs/04 §4).
    superseded_by: dict[str, str] = field(default_factory=dict)
    # Evidence excluded from `supported` because a later revision replaced its source.
    superseded_evidence: set[str] = field(default_factory=set)

    @property
    def contested(self) -> list[Claim]:
        return [claim for claim in self.claims if claim.status == "contested"]

    @property
    def unsupported(self) -> list[Claim]:
        return [claim for claim in self.claims if claim.status in {"weak", "unresolved"}]

    def claim_for(self, claim_id: str) -> Claim | None:
        return next((claim for claim in self.claims if claim.claim_id == claim_id), None)


def supersession_edges(documents: dict[str, Document]) -> dict[str, str]:
    """docs/04 §4: same `document_id_external`, later `revision_date` supersedes.

    Returns `older doc_id -> the newest doc_id for that external id`. Keyed by the
    older document because that is the question every caller asks ("has this been
    replaced?"), and because a newest-wins mapping is well defined when three or more
    revisions are present or when two share a date — pairing consecutive versions
    instead left the older of two same-dated documents looking current.

    Only primary documents form these edges — a fact sheet restating an LCD is not a
    newer version of it — and only fetched ones, since an unfetched document has no
    metadata to compare.
    """
    by_external: dict[str, list[Document]] = defaultdict(list)
    for document in documents.values():
        if (
            document.is_fetched
            and document.document_id_external
            and document.source_tier == "primary_policy"
            and document.revision_date
        ):
            by_external[document.document_id_external].append(document)

    edges: dict[str, str] = {}
    for versions in by_external.values():
        newest = max(versions, key=lambda d: (d.revision_date, d.doc_id))  # type: ignore[arg-type,return-value]
        for document in versions:
            if document.doc_id != newest.doc_id and document.revision_date < newest.revision_date:  # type: ignore[operator]
                edges[document.doc_id] = newest.doc_id
    return edges


def _newer_document_has_passage(passage: str, newer: Document) -> bool:
    """Whether the superseding document still contains this passage.

    docs/04 §4 excludes superseded evidence "unless the later document lacks the
    passage", so this decides which way that clause falls — and it has to read the
    later document's own text. Deciding it from what agents happened to quote would
    call any clause nobody re-quoted "lacking", which is the opposite of the truth
    in the common case where a revision changed one paragraph and left the rest.

    Whitespace-normalized, because the two revisions may wrap the same sentence
    differently.
    """
    try:
        text = within.load_text(newer)
    except (OSError, ValueError):
        return False  # cannot read the later revision: keep the older evidence
    return _squeeze(passage) in _squeeze(text)


def _squeeze(text: str) -> str:
    return " ".join((text or "").split())


def build_claim_graph(
    evidence: list[Evidence], documents: dict[str, Document]
) -> ClaimGraph:
    """Group evidence into claims and assign each a status (docs/04 §4).

    Called by the `collect` node after every round (docs/03 §5).
    """
    edges = supersession_edges(documents)

    # docs/04 §4: an item whose document was superseded is excluded from `supported`
    # — unless the later revision lacks the passage, in which case the older document
    # is the only place that text exists and dropping it would lose the finding.
    superseded_evidence = {
        item.evidence_id
        for item in evidence
        if item.doc_id in edges
        and (newer := documents.get(edges[item.doc_id])) is not None
        and _newer_document_has_passage(item.evidence_text, newer)
    }

    graph = ClaimGraph(superseded_by=edges, superseded_evidence=superseded_evidence)

    # Group by (branch_id, near-duplicate claim text) so near-identical claims from
    # different sub-agents merge instead of appearing as separate findings.
    groups: list[tuple[str, str, list[Evidence]]] = []  # (branch_id, text, items)
    for item in evidence:
        for index, (branch_id, text, items) in enumerate(groups):
            if branch_id == item.branch_id and jaccard(text, item.claim_text) >= JACCARD_MERGE:
                items.append(item)
                # Keep the longest phrasing: it is the most specific statement of the
                # same claim, and it is what the answer will quote.
                if len(item.claim_text) > len(text):
                    groups[index] = (branch_id, item.claim_text, items)
                break
        else:
            groups.append((item.branch_id, item.claim_text, [item]))

    for index, (branch_id, text, items) in enumerate(groups, start=1):
        graph.claims.append(_claim(f"c{index}", text, branch_id, items, superseded_evidence))
    return graph


def _claim(
    claim_id: str,
    text: str,
    branch_id: str,
    items: list[Evidence],
    superseded: set[str],
) -> Claim:
    supporting = [i for i in items if i.stance == "supports"]
    contradicting = [i for i in items if i.stance == "contradicts"]
    # A superseded passage still belongs on the claim for the audit trail, but it
    # cannot be what makes the claim supported.
    live_support = [i for i in supporting if i.evidence_id not in superseded]
    confident_contra = [i for i in contradicting if i.confidence >= CONFIDENT]

    status = _status(supporting, live_support, confident_contra)
    confidence = max(
        (item.source_quality * item.confidence for item in live_support), default=0.0
    )
    if status == "contested":
        confidence = max(0.0, confidence - CONTESTED_PENALTY)

    governing_date = _governing_date(live_support)
    # docs/04 §4's third contradiction rule: where a contradicting item carries a
    # later effective date than the support, "the later date governs and the claim's
    # text is annotated". A reader seeing this claim needs to know the newer source
    # disagrees, or the claim reads as current when it is not.
    later_contra = _later_contradiction(live_support, confident_contra, governing_date)
    if later_contra is not None and later_contra.effective_date:
        governing_date = later_contra.effective_date
        text = f"{text} [contradicted by a later source effective {governing_date.isoformat()}]"

    return Claim(
        claim_id=claim_id,
        text=text,
        branch_id=branch_id,
        supported_by=[i.evidence_id for i in supporting],
        contradicted_by=[i.evidence_id for i in contradicting],
        status=status,
        confidence=round(confidence, 3),
        governing_date=governing_date,
    )


def _status(
    supporting: list[Evidence],
    live_support: list[Evidence],
    confident_contra: list[Evidence],
) -> str:
    """docs/04 §4's four statuses, quoted clause by clause.

    `unresolved` is "no supporting evidence" — which is why both lists are needed:
    support that exists but was superseded falls to `weak`, because the spec excludes
    superseded evidence from `supported` status, not from existence.
    """
    if not supporting:
        return "unresolved"
    if not live_support:
        return "weak"
    # "with confidence >= 0.6" governs both sides of the contested test.
    confident_support = [i for i in live_support if i.confidence >= CONFIDENT]
    if confident_support and confident_contra:
        return "contested"
    primary = [i for i in confident_support if i.source_quality >= PRIMARY_QUALITY]
    if primary:
        return "supported"
    # "supporting evidence only from tiers < 0.85, or a single supporting item with
    # confidence < 0.6" — the second clause is why a lone hedged primary passage is
    # weak rather than supported.
    return "weak"


def _governing_date(live_support: list[Evidence]) -> date | None:
    """docs/04 §4: "the effective_date of the highest-quality supporting evidence".

    Restricted to items *at* the top quality, so a web page's date is never reported
    as governing while a primary source carries the claim — that date feeds docs/04
    §7's currency metric, and a misattributed one is worse than none. Within that
    tier, ties break toward the later date.
    """
    if not live_support:
        return None
    best_quality = max(item.source_quality for item in live_support)
    dated = [
        item
        for item in live_support
        if item.source_quality == best_quality and item.effective_date
    ]
    return max(item.effective_date for item in dated) if dated else None


def _later_contradiction(
    live_support: list[Evidence],
    confident_contra: list[Evidence],
    governing_date: date | None,
) -> Evidence | None:
    """The confident contradiction whose effective date is later than the support's."""
    if governing_date is None:
        return None
    later = [
        item
        for item in confident_contra
        if item.effective_date and item.effective_date > governing_date
    ]
    return max(later, key=lambda item: item.effective_date) if later else None  # type: ignore[arg-type,return-value]

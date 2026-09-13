"""Evidence creation and the docs/04 §3 rules.

Rule 2 is the one that matters: `evidence_text` must be a verbatim substring of the
paragraph it cites. Everything the answer claims is traceable to a passage a reader
can find on the page, and a paraphrase that slipped through here would look exactly
like a citation while being unverifiable.

Two deliberate behaviours beyond the literal rules:

* A match is found with whitespace normalized (rule 2 says so), and then the stored
  `evidence_text` is replaced with **the document's own bytes** for that span. So
  `text[char_start:char_end] == evidence_text` holds exactly, and the UI can
  highlight the passage rather than approximately locating it. An agent that retypes
  a line with different spacing gets accepted and corrected, not rejected.
* A rejection carries the paragraph text back to the caller, because docs/04 §3
  rule 2 says the tool "rejects it with the paragraph text so it can retry".
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

from prime_search.primitives import sources, within
from prime_search.schemas import Document, Evidence, Location
from prime_search.workspace import RUN_LOCK

MAX_EVIDENCE_CHARS = 600  # docs/02 §2.4
MAX_CLAIM_CHARS = 200  # docs/04 §3 rule 3
DEFAULT_RELEVANCE = 0.8  # docs/04 §3 rule 6, for agent-authored evidence
STANCES = ("supports", "contradicts", "context")


class EvidenceRejected(ValueError):
    """A candidate failed a docs/04 §3 rule.

    `paragraph_text` is populated for a failed verbatim check so the caller can put
    the real passage in front of the agent for a retry (rule 2).
    """

    def __init__(self, reason: str, *, paragraph_text: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.paragraph_text = paragraph_text


def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def _find_verbatim(paragraph: str, candidate: str) -> tuple[int, int] | None:
    """Offsets of `candidate` within `paragraph`, comparing whitespace-insensitively.

    Returns offsets into `paragraph` so the caller can slice the document's own bytes.
    Built by walking the paragraph's non-space characters, so a candidate that
    differs only in runs of whitespace or line breaks still locates exactly.
    """
    if not candidate.strip():
        return None
    direct = paragraph.find(candidate)
    if direct >= 0:
        return direct, direct + len(candidate)

    # Map each non-space character of the paragraph to its index, then search the
    # squeezed forms and translate the hit back to real offsets.
    indices = [i for i, char in enumerate(paragraph) if not char.isspace()]
    squeezed = "".join(paragraph[i] for i in indices)
    target = "".join(char for char in candidate if not char.isspace())
    if not target:
        return None
    position = squeezed.find(target)
    if position < 0:
        return None
    return indices[position], indices[position + len(target) - 1] + 1


@dataclass
class EvidenceStore:
    """Holds a run's evidence and is the only thing that creates it.

    `documents` is the run's document mapping (`ws.documents`); the store reads
    paragraph text through `within.load_paragraphs`, so it validates against the
    same persisted bytes the citation will point at.
    """

    documents: dict[str, Document]
    items: list[Evidence] = field(default_factory=list)
    _by_id: dict[str, Evidence] = field(default_factory=dict, repr=False)

    def add(
        self,
        *,
        doc_id: str,
        branch_id: str,
        claim_text: str,
        evidence_text: str,
        paragraph_index: int,
        stance: str = "supports",
        confidence: float = 0.8,
        relevance: float | None = None,
        effective_date: date | None = None,
    ) -> Evidence:
        """Create one evidence item, enforcing every docs/04 §3 rule.

        Raises `EvidenceRejected` rather than returning None: a silently dropped
        passage would leave a claim looking unsupported for no stated reason.
        """
        document = self.documents.get(doc_id)
        if document is None:
            raise EvidenceRejected(f"unknown doc_id {doc_id!r}; search and fetch it first")

        # Rule 1: the document has been fetched.
        if not document.is_fetched:
            raise EvidenceRejected(
                f"{doc_id} is {document.fetch_method}: evidence may only come from a "
                "fetched document, never from a search snippet (docs/04 §3 rule 1). "
                "Call fetch first."
            )

        # Rule 4: stance vocabulary.
        if stance not in STANCES:
            raise EvidenceRejected(f"stance must be one of {STANCES}, got {stance!r}")

        # Rule 3: one atomic statement.
        claim_text = claim_text.strip()
        if not claim_text:
            raise EvidenceRejected("claim_text is empty")
        if len(claim_text) > MAX_CLAIM_CHARS:
            raise EvidenceRejected(
                f"claim_text is {len(claim_text)} chars (max {MAX_CLAIM_CHARS}); "
                "state one atomic claim, not a summary"
            )

        paragraphs = within.load_paragraphs(document)
        if not 0 <= paragraph_index < len(paragraphs):
            raise EvidenceRejected(
                f"paragraph_index {paragraph_index} out of range for {doc_id} "
                f"(0-{len(paragraphs) - 1})"
            )
        paragraph = paragraphs[paragraph_index]

        # Rule 2: verbatim substring of the referenced paragraph.
        span = _find_verbatim(paragraph.text, evidence_text)
        if span is None:
            raise EvidenceRejected(
                f"evidence_text is not a verbatim passage of paragraph "
                f"{paragraph_index} of {doc_id}. Quote the paragraph exactly, do not "
                "paraphrase. The paragraph reads:",
                paragraph_text=paragraph.text,
            )
        start, end = span
        exact = paragraph.text[start:end]  # the document's own bytes win
        if len(exact) > MAX_EVIDENCE_CHARS:
            raise EvidenceRejected(
                f"evidence_text is {len(exact)} chars (max {MAX_EVIDENCE_CHARS}); "
                "quote the sentence that carries the claim, not the whole paragraph"
            )

        # Rule 5: fall back to the document's revision date.
        if effective_date is None:
            effective_date = document.revision_date or document.effective_date

        # Rule 6: quality from the tier; relevance defaulted for agent-authored items.
        item = Evidence(
            evidence_id=_evidence_id(
                doc_id, paragraph_index, exact, branch_id, claim_text, stance
            ),
            doc_id=doc_id,
            branch_id=branch_id,
            claim_text=claim_text,
            evidence_text=exact,
            location=Location(
                section=paragraph.section,
                paragraph_index=paragraph_index,
                char_start=paragraph.char_start + start,
                char_end=paragraph.char_start + end,
            ),
            effective_date=effective_date,
            relevance=DEFAULT_RELEVANCE if relevance is None else relevance,
            source_quality=sources.quality(document.source_tier),
            confidence=confidence,
            stance=stance,  # type: ignore[arg-type]
        )

        # Two agents quoting the same passage for the same branch is one finding, not
        # two, and double-counting it would inflate a claim's support. Under the
        # `Send` fan-out those two agents run concurrently, so the de-duplicating
        # check and the two appends have to be one atomic step or the same passage
        # lands in `items` twice with one entry in `_by_id`.
        with RUN_LOCK:
            existing = self._by_id.get(item.evidence_id)
            if existing is not None:
                return existing
            self._by_id[item.evidence_id] = item
            self.items.append(item)
        return item

    def for_branch(self, branch_id: str) -> list[Evidence]:
        return [item for item in self.items if item.branch_id == branch_id]

    def get(self, evidence_id: str) -> Evidence | None:
        return self._by_id.get(evidence_id)

    def verify(self) -> list[str]:
        """Re-check every stored item against the document on disk.

        Cheap insurance for the bench and the UI: if a document were refetched
        mid-run, offsets could move and a citation would point at the wrong words.
        Returns the evidence ids that no longer slice to their own text.
        """
        broken: list[str] = []
        for item in self.items:
            document = self.documents.get(item.doc_id)
            if document is None or not document.is_fetched:
                broken.append(item.evidence_id)
                continue
            try:
                text = within.load_text(document)
            except (OSError, ValueError):
                # A missing text file or a sidecar sha1 mismatch is exactly what this
                # method exists to report; raising here would make the check itself
                # the failure.
                broken.append(item.evidence_id)
                continue
            if text[item.location.char_start : item.location.char_end] != item.evidence_text:
                broken.append(item.evidence_id)
        return broken


def _evidence_id(
    doc_id: str,
    paragraph_index: int,
    passage: str,
    branch_id: str,
    claim_text: str,
    stance: str,
) -> str:
    """Content-addressed, so the *same* finding recorded twice is one item.

    `claim_text` and `stance` are part of the key, not just the passage: one passage
    can legitimately be cited for two different claims, and — the case that matters —
    the same passage can be offered as `supports` for one reading and `contradicts`
    for another. Hashing only the passage silently returned the first item and threw
    the second away, which suppressed contested detection outright while telling the
    agent its evidence was recorded.

    docs/02 pins `doc_id`'s format but says nothing about this one.
    """
    key = "|".join(
        (
            doc_id,
            str(paragraph_index),
            branch_id,
            stance,
            _normalize_whitespace(claim_text).lower(),
            _normalize_whitespace(passage),
        )
    )
    return f"ev_{hashlib.sha1(key.encode()).hexdigest()[:10]}"


_TOKEN = re.compile(r"[a-z0-9]+")


def claim_tokens(text: str) -> set[str]:
    """Tokens used for the docs/04 §4 Jaccard merge. Shared with graph.py so the
    merge and any debugging of it see the same tokens."""
    return set(_TOKEN.findall((text or "").lower()))

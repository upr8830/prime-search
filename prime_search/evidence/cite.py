"""Citation rendering (docs/04 §5).

docs/04 §5's worked example:

    [3] LCD L33822 - Glucose Monitors, §Coverage Indications, Limitations, and/or
        Medical Necessity, revision effective 2023-04-16. Noridian (DME MAC).
        primary_policy.
        https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822

The governing rule is the last sentence of §5: **missing pieces are omitted, never
invented.** A document whose revision date did not survive extraction gets a label
without a date rather than a plausible one — and that is common, not exceptional:
measured on the live pages, the CMS header block is JavaScript-rendered, so both
flagship documents have a revision date and no effective date at all.
"""

from __future__ import annotations

from prime_search.schemas import Citation, Document, Evidence


def citation_label(document: Document, section: str | None = None) -> str:
    """The one-line label for `Citation.label` (docs/04 §5).

    Every part is conditional. With nothing but a URL, the label is the title, and
    with no title either it is the URL — never a fabricated identifier.
    """
    head_parts = [part for part in (document.doc_type, document.document_id_external) if part]
    head = " ".join(head_parts)
    if head and document.title:
        head = f"{head} - {document.title}"
    elif not head:
        head = document.title or document.url

    pieces = [head]
    if section:
        pieces.append(f"§{section}")
    if document.revision_date:
        pieces.append(f"revision effective {document.revision_date.isoformat()}")
    elif document.effective_date:
        # Only reached when no revision date is known: saying "revision effective"
        # of an original effective date would misdate the policy.
        pieces.append(f"effective {document.effective_date.isoformat()}")
    return ", ".join(pieces)


def source_line(n: int, document: Document, section: str | None = None) -> str:
    """The full entry for the answer's Sources list (docs/04 §5's example shape)."""
    tail = [part for part in (document.publisher, document.source_tier) if part]
    line = f"[{n}] {citation_label(document, section)}."
    if tail:
        line += " " + ". ".join(tail) + "."
    return f"{line}\n    {document.url}"


def build_citations(
    evidence: list[Evidence], documents: dict[str, Document]
) -> list[Citation]:
    """Number the citations [1..n] in the order their evidence is cited.

    One citation per **evidence item**, not per (document, section). docs/02 §2.7
    gives `Citation` a single `evidence_id`, and docs/04 §7 has the evaluators check a
    citation against the passage it names — so collapsing two passages from one
    section into one citation would leave `[n]` pointing at the wrong quote for
    whichever sentence rested on the second passage. Repeats of the same evidence id
    still collapse.
    """
    citations: list[Citation] = []
    seen: set[str] = set()
    for item in evidence:
        document = documents.get(item.doc_id)
        if document is None:
            continue  # nothing to cite; the synthesizer drops the claim instead
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        citations.append(
            Citation(
                n=len(citations) + 1,
                evidence_id=item.evidence_id,
                doc_id=item.doc_id,
                url=document.url,
                label=citation_label(document, item.location.section),
            )
        )
    return citations


def effective_dates_section(
    evidence: list[Evidence], documents: dict[str, Document]
) -> list[str]:
    """`Answer.effective_dates` (docs/02 §2.7): "LCD L33822: revision effective
    2023-04-16", one line per cited document that states a date.

    This is the section the answer is graded on for currency (docs/05 §2), and the
    reason a coverage answer is trustworthy at all — so a document with no date is
    left out here and surfaces as a critic finding instead (docs/04 §2).
    """
    lines: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        document = documents.get(item.doc_id)
        if document is None or document.doc_id in seen:
            continue
        label = document.document_id_external or document.title or document.url
        if document.revision_date:
            lines.append(f"{label}: revision effective {document.revision_date.isoformat()}")
        elif document.effective_date:
            lines.append(f"{label}: effective {document.effective_date.isoformat()}")
        else:
            continue  # no date known; omitted rather than guessed
        seen.add(document.doc_id)
    return lines

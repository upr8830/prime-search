"""The evidence model (docs/04 §3-5).

docs/09 §1.5 requires three: contested detection, supersession by revision date, and
citation labels with missing fields omitted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from prime_search.evidence import cite
from prime_search.evidence.graph import build_claim_graph, jaccard, supersession_edges
from prime_search.evidence.store import EvidenceRejected, EvidenceStore
from prime_search.primitives import docmeta
from prime_search.schemas import Document, Evidence, Location

PARAGRAPHS = [
    "## Coverage Guidance",
    "The beneficiary has a history of problematic hypoglycemia with documentation of "
    "at least one level 2 event.",
    "Coverage requires treatment with insulin or a documented history of problematic "
    "hypoglycemia.",
    "Multiple daily injections of insulin are not required for coverage.",
]
BODY = "\n\n".join(PARAGRAPHS)


def _write(tmp_path: Path, name: str, body: str) -> tuple[Path, int]:
    text = docmeta.normalize_text(body)
    path = tmp_path / f"{name}.txt"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path, len(docmeta.split_paragraphs(text))


def _document(
    tmp_path: Path,
    doc_id: str = "doc_lcd",
    *,
    tier: str = "primary_policy",
    body: str = BODY,
    **kwargs,
) -> Document:
    path, count = _write(tmp_path, doc_id, body)
    return Document(
        doc_id=doc_id,
        url=kwargs.pop("url", f"https://www.cms.gov/medicare-coverage-database/{doc_id}"),
        title=kwargs.pop("title", "Glucose Monitors"),
        source_tier=tier,  # type: ignore[arg-type]
        publisher=kwargs.pop("publisher", "Noridian (DME MAC)"),
        doc_type=kwargs.pop("doc_type", "LCD"),
        document_id_external=kwargs.pop("document_id_external", "L33822"),
        revision_date=kwargs.pop("revision_date", date(2024, 10, 1)),
        retrieved_at=datetime.now(UTC),
        text_path=str(path),
        paragraph_count=count,
        fetch_method="extract",
        **kwargs,
    )


@pytest.fixture
def store(tmp_path: Path) -> EvidenceStore:
    document = _document(tmp_path)
    return EvidenceStore(documents={document.doc_id: document})


# --- docs/04 §3: the six add_evidence rules ---------------------------------------


def test_a_verbatim_passage_is_accepted_and_located(store: EvidenceStore) -> None:
    item = store.add(
        doc_id="doc_lcd",
        branch_id="b1",
        claim_text="Coverage requires insulin treatment or problematic hypoglycemia",
        evidence_text="Coverage requires treatment with insulin",
        paragraph_index=2,
    )
    text = Path(store.documents["doc_lcd"].text_path).read_text(encoding="utf-8")
    assert text[item.location.char_start : item.location.char_end] == item.evidence_text
    assert item.location.paragraph_index == 2
    assert item.location.section == "Coverage Guidance"
    assert store.verify() == []


def test_a_paraphrase_is_rejected_with_the_paragraph_text(store: EvidenceStore) -> None:
    """docs/04 §3 rule 2: the tool "rejects it with the paragraph text so it can
    retry" — without the paragraph the agent has nothing to correct against."""
    with pytest.raises(EvidenceRejected) as caught:
        store.add(
            doc_id="doc_lcd",
            branch_id="b1",
            claim_text="Insulin is required",
            evidence_text="Beneficiaries need insulin to qualify for coverage",
            paragraph_index=2,
        )
    assert "not a verbatim passage" in caught.value.reason
    assert "Coverage requires treatment with insulin" in caught.value.paragraph_text


def test_whitespace_differences_are_tolerated_and_canonicalized(store: EvidenceStore) -> None:
    """An agent retyping a line across a newline should not be rejected — but what is
    stored must be the document's own bytes, so the offsets slice to it exactly."""
    item = store.add(
        doc_id="doc_lcd",
        branch_id="b1",
        claim_text="Problematic hypoglycemia qualifies",
        evidence_text="documented history of\n   problematic hypoglycemia",
        paragraph_index=2,
    )
    assert item.evidence_text == "documented history of problematic hypoglycemia"
    text = Path(store.documents["doc_lcd"].text_path).read_text(encoding="utf-8")
    assert text[item.location.char_start : item.location.char_end] == item.evidence_text


def test_a_snippet_only_document_is_refused(tmp_path: Path) -> None:
    """docs/04 §3 rule 1 — the rule that keeps search snippets out of the answer."""
    snippet = Document(
        doc_id="doc_snip",
        url="https://www.cms.gov/x",
        title="x",
        source_tier="primary_policy",
        retrieved_at=datetime.now(UTC),
        fetch_method="snippet_only",
    )
    store = EvidenceStore(documents={"doc_snip": snippet})
    with pytest.raises(EvidenceRejected, match="never from a search snippet"):
        store.add(
            doc_id="doc_snip",
            branch_id="b1",
            claim_text="c",
            evidence_text="anything",
            paragraph_index=0,
        )


def test_an_over_long_claim_is_refused(store: EvidenceStore) -> None:
    with pytest.raises(EvidenceRejected, match="one atomic claim"):
        store.add(
            doc_id="doc_lcd",
            branch_id="b1",
            claim_text="x" * 201,  # docs/04 §3 rule 3
            evidence_text="Coverage requires treatment with insulin",
            paragraph_index=2,
        )


def test_an_unknown_stance_is_refused(store: EvidenceStore) -> None:
    with pytest.raises(EvidenceRejected, match="stance must be one of"):
        store.add(
            doc_id="doc_lcd",
            branch_id="b1",
            claim_text="c",
            evidence_text="Coverage requires treatment with insulin",
            paragraph_index=2,
            stance="refutes",
        )


def test_effective_date_and_quality_are_filled_from_the_document(store: EvidenceStore) -> None:
    """docs/04 §3 rules 5 and 6."""
    item = store.add(
        doc_id="doc_lcd",
        branch_id="b1",
        claim_text="c",
        evidence_text="Coverage requires treatment with insulin",
        paragraph_index=2,
    )
    assert item.effective_date == date(2024, 10, 1)  # the document's revision date
    assert item.source_quality == 1.0  # primary_policy
    assert item.relevance == 0.8  # agent-authored default


def test_the_same_passage_twice_is_one_item(store: EvidenceStore) -> None:
    """Two sub-agents finding the same passage is one finding; counting it twice would
    inflate the claim's support."""
    first = store.add(
        doc_id="doc_lcd", branch_id="b1", claim_text="c",
        evidence_text="Coverage requires treatment with insulin", paragraph_index=2,
    )
    second = store.add(
        doc_id="doc_lcd", branch_id="b1", claim_text="c",
        evidence_text="Coverage requires  treatment with insulin", paragraph_index=2,
    )
    assert first.evidence_id == second.evidence_id
    assert len(store.items) == 1


# --- docs/09 §1.5 test 1: contested detection -------------------------------------


def _evidence(
    evidence_id: str,
    *,
    stance: str = "supports",
    quality: float = 1.0,
    confidence: float = 0.9,
    claim: str = "A therapeutic CGM is covered when the beneficiary uses insulin",
    branch: str = "b1",
    doc_id: str = "doc_lcd",
    effective: date | None = None,
    text: str = "passage",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        doc_id=doc_id,
        branch_id=branch,
        claim_text=claim,
        evidence_text=text,
        location=Location(paragraph_index=0, char_start=0, char_end=len(text)),
        effective_date=effective,
        relevance=0.8,
        source_quality=quality,
        confidence=confidence,
        stance=stance,  # type: ignore[arg-type]
    )


def test_contested_when_support_and_contradiction_are_both_confident(tmp_path: Path) -> None:
    """docs/04 §4: "supporting and contradicting evidence both present with
    confidence >= 0.6"."""
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph(
        [_evidence("ev_1"), _evidence("ev_2", stance="contradicts", confidence=0.8)],
        documents,
    )
    (claim,) = graph.claims
    assert claim.status == "contested"
    assert claim.confidence == pytest.approx(1.0 * 0.9 - 0.3)  # penalty applied
    assert graph.contested == [claim]


def test_a_low_confidence_contradiction_does_not_contest(tmp_path: Path) -> None:
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph(
        [_evidence("ev_1"), _evidence("ev_2", stance="contradicts", confidence=0.4)],
        documents,
    )
    assert graph.claims[0].status == "supported"


def test_only_secondary_support_is_weak_not_supported(tmp_path: Path) -> None:
    """docs/04 §1's consumer rule: a coverage claim needs primary or official
    backing, so a vendor page alone cannot make it supported."""
    documents = {"doc_web": _document(tmp_path, "doc_web", tier="web")}
    graph = build_claim_graph([_evidence("ev_1", quality=0.3, doc_id="doc_web")], documents)
    assert graph.claims[0].status == "weak"
    assert graph.unsupported == graph.claims


def test_no_support_is_unresolved(tmp_path: Path) -> None:
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph([_evidence("ev_1", stance="contradicts")], documents)
    assert graph.claims[0].status == "unresolved"


def test_near_duplicate_claims_from_different_agents_merge(tmp_path: Path) -> None:
    """docs/04 §4: token Jaccard >= 0.6 on claim text."""
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph(
        [
            _evidence("ev_1", claim="A therapeutic CGM is covered when the beneficiary uses insulin"),
            _evidence("ev_2", claim="A therapeutic CGM is covered if the beneficiary uses insulin"),
        ],
        documents,
    )
    assert len(graph.claims) == 1
    assert len(graph.claims[0].supported_by) == 2


def test_claims_on_different_branches_never_merge(tmp_path: Path) -> None:
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph(
        [_evidence("ev_1", branch="b1"), _evidence("ev_2", branch="b2")], documents
    )
    assert len(graph.claims) == 2


def test_jaccard_is_symmetric_and_bounded() -> None:
    assert jaccard("insulin required", "insulin required") == 1.0
    assert jaccard("insulin required", "") == 0.0
    assert jaccard("a b c d", "a b") == pytest.approx(0.5)


# --- docs/09 §1.5 test 2: supersession by revision date ---------------------------


# The 2023 revision of L33822 required multiple daily injections; the 2024 one
# dropped that clause. Two bodies that differ in exactly that way let both halves of
# docs/04 §4's supersession rule be tested.
REMOVED_CLAUSE = "Three or more daily administrations of insulin are required."
OLD_BODY = f"{BODY}\n\n{REMOVED_CLAUSE}"


def _revisions(tmp_path: Path) -> dict[str, Document]:
    return {
        "doc_old": _document(
            tmp_path, "doc_old", body=OLD_BODY, revision_date=date(2023, 4, 16)
        ),
        "doc_new": _document(tmp_path, "doc_new", body=BODY, revision_date=date(2024, 10, 1)),
    }


def test_supersession_by_revision_date(tmp_path: Path) -> None:
    """docs/04 §4: same document_id_external, later revision_date supersedes.

    Keyed older -> newest, which is the question callers ask and the only shape that
    stays well defined for three or more revisions.
    """
    assert supersession_edges(_revisions(tmp_path)) == {"doc_old": "doc_new"}


def test_evidence_the_newer_revision_still_contains_is_superseded(tmp_path: Path) -> None:
    """docs/04 §4: the older document's evidence "is flagged superseded and excluded
    from `supported` status". Quoting the 2023 revision for a clause the 2024 one also
    carries is citing a stale document for current text."""
    documents = _revisions(tmp_path)
    graph = build_claim_graph(
        [_evidence("ev_old", doc_id="doc_old", text="treatment with insulin")], documents
    )
    assert graph.superseded_by == {"doc_old": "doc_new"}
    assert "ev_old" in graph.superseded_evidence
    # Support exists but cannot confer `supported`; docs/04 §4 reserves `unresolved`
    # for "no supporting evidence".
    assert graph.claims[0].status == "weak"
    assert "ev_old" in graph.claims[0].supported_by  # still on the record


def test_evidence_the_newer_revision_lacks_is_not_superseded(tmp_path: Path) -> None:
    """docs/04 §4's "unless the later document lacks the passage" — the old revision
    is then the only place that text exists, so dropping it would lose the finding."""
    documents = _revisions(tmp_path)
    graph = build_claim_graph(
        [
            _evidence(
                "ev_old",
                doc_id="doc_old",
                text=REMOVED_CLAUSE,
                claim="Three or more daily insulin administrations were once required",
            )
        ],
        documents,
    )
    assert graph.superseded_evidence == set()
    assert graph.claims[0].status == "supported"


def test_the_newer_revisions_own_evidence_carries_the_claim(tmp_path: Path) -> None:
    documents = _revisions(tmp_path)
    graph = build_claim_graph(
        [
            _evidence("ev_old", doc_id="doc_old", text="treatment with insulin"),
            _evidence("ev_new", doc_id="doc_new", text="treatment with insulin"),
        ],
        documents,
    )
    assert graph.superseded_evidence == {"ev_old"}
    assert graph.claims[0].status == "supported"  # ev_new is live


def test_three_revisions_all_point_at_the_newest(tmp_path: Path) -> None:
    documents = {
        "doc_r14": _document(tmp_path, "doc_r14", revision_date=date(2024, 1, 1)),
        "doc_r15": _document(tmp_path, "doc_r15", revision_date=date(2024, 4, 1)),
        "doc_r16": _document(tmp_path, "doc_r16", revision_date=date(2024, 10, 1)),
    }
    assert supersession_edges(documents) == {"doc_r14": "doc_r16", "doc_r15": "doc_r16"}


def test_two_revisions_sharing_a_date_are_both_superseded_by_the_newest(
    tmp_path: Path,
) -> None:
    """Pairing consecutive versions left the older of two same-dated documents looking
    current, because the equal-date pair produced no edge."""
    documents = {
        "doc_a": _document(tmp_path, "doc_a", revision_date=date(2023, 4, 16)),
        "doc_b": _document(tmp_path, "doc_b", revision_date=date(2023, 4, 16)),
        "doc_c": _document(tmp_path, "doc_c", revision_date=date(2024, 10, 1)),
    }
    edges = supersession_edges(documents)
    assert edges == {"doc_a": "doc_c", "doc_b": "doc_c"}


def test_different_external_ids_do_not_supersede(tmp_path: Path) -> None:
    documents = {
        "doc_lcd": _document(tmp_path, "doc_lcd", document_id_external="L33822"),
        "doc_art": _document(
            tmp_path, "doc_art", document_id_external="A52464", revision_date=date(2025, 2, 18)
        ),
    }
    assert supersession_edges(documents) == {}


def test_a_secondary_document_never_supersedes_a_policy(tmp_path: Path) -> None:
    """A fact sheet restating an LCD is not a newer version of it."""
    documents = {
        "doc_lcd": _document(tmp_path, "doc_lcd", revision_date=date(2023, 4, 16)),
        "doc_fs": _document(
            tmp_path, "doc_fs", tier="official_secondary", revision_date=date(2026, 1, 1)
        ),
    }
    assert supersession_edges(documents) == {}


def test_governing_date_comes_from_the_best_supporting_evidence(tmp_path: Path) -> None:
    documents = {
        "doc_lcd": _document(tmp_path),
        "doc_web": _document(tmp_path, "doc_web", tier="web"),
    }
    graph = build_claim_graph(
        [
            _evidence("ev_web", quality=0.3, doc_id="doc_web", effective=date(2026, 1, 1)),
            _evidence("ev_lcd", quality=1.0, effective=date(2024, 10, 1)),
        ],
        documents,
    )
    assert graph.claims[0].governing_date == date(2024, 10, 1)  # primary wins over newer


# --- docs/09 §1.5 test 3: citation labels omit what is missing --------------------


def test_a_full_label_matches_the_spec_example(tmp_path: Path) -> None:
    document = _document(tmp_path, revision_date=date(2023, 4, 16))
    label = cite.citation_label(
        document, "Coverage Indications, Limitations, and/or Medical Necessity"
    )
    assert label == (
        "LCD L33822 - Glucose Monitors, "
        "§Coverage Indications, Limitations, and/or Medical Necessity, "
        "revision effective 2023-04-16"
    )


@pytest.mark.parametrize(
    ("overrides", "absent"),
    [
        ({"revision_date": None}, "revision effective"),
        ({"document_id_external": None}, "L33822"),
        ({"doc_type": None}, "LCD"),
    ],
)
def test_missing_pieces_are_omitted_never_invented(
    tmp_path: Path, overrides: dict, absent: str
) -> None:
    """docs/04 §5's governing rule. This is not an edge case: measured on the live
    pages, the CMS header block is JavaScript-rendered, so real documents routinely
    arrive without one of these."""
    document = _document(tmp_path, **overrides)
    label = cite.citation_label(document, "Coverage Guidance")
    assert absent not in label
    assert "None" not in label and "none" not in label.lower()


def test_a_bare_document_falls_back_to_title_then_url(tmp_path: Path) -> None:
    document = _document(
        tmp_path, doc_type=None, document_id_external=None, revision_date=None, title=""
    )
    assert cite.citation_label(document) == document.url


def test_no_revision_date_uses_effective_without_calling_it_a_revision(
    tmp_path: Path,
) -> None:
    """Labelling an original effective date as a revision would misdate the policy."""
    document = _document(tmp_path, revision_date=None, effective_date=date(2015, 10, 1))
    label = cite.citation_label(document)
    assert "effective 2015-10-01" in label
    assert "revision effective" not in label


def test_one_citation_per_evidence_item_so_each_n_names_its_own_passage(
    tmp_path: Path,
) -> None:
    """docs/02 §2.7 gives Citation a single evidence_id and docs/04 §7 has the
    evaluators check [n] against the passage it names, so two passages from one
    section cannot share a number — the second sentence's [n] would point at the
    first sentence's quote."""
    documents = {"doc_lcd": _document(tmp_path), "doc_art": _document(tmp_path, "doc_art")}
    evidence = [
        _evidence("ev_1", doc_id="doc_lcd", text="treatment with insulin"),
        _evidence("ev_2", doc_id="doc_lcd", text="problematic hypoglycemia"),
        _evidence("ev_3", doc_id="doc_art"),
    ]
    citations = cite.build_citations(evidence, documents)
    assert [c.n for c in citations] == [1, 2, 3]
    assert [c.evidence_id for c in citations] == ["ev_1", "ev_2", "ev_3"]


def test_the_same_evidence_cited_twice_is_one_citation(tmp_path: Path) -> None:
    documents = {"doc_lcd": _document(tmp_path)}
    item = _evidence("ev_1")
    assert len(cite.build_citations([item, item], documents)) == 1


def test_the_source_line_carries_publisher_tier_and_url(tmp_path: Path) -> None:
    document = _document(tmp_path, revision_date=date(2023, 4, 16))
    line = cite.source_line(3, document, "Coverage Indications")
    assert line.startswith("[3] LCD L33822 - Glucose Monitors, §Coverage Indications")
    assert "Noridian (DME MAC)" in line
    assert "primary_policy" in line
    assert document.url in line


def test_effective_dates_section_omits_undated_documents(tmp_path: Path) -> None:
    """docs/02 §2.7's Answer.effective_dates — the section the answer is graded on for
    currency. An undated document is a critic finding, not a guess."""
    documents = {
        "doc_lcd": _document(tmp_path),
        "doc_none": _document(tmp_path, "doc_none", revision_date=None, effective_date=None),
    }
    lines = cite.effective_dates_section(
        [_evidence("ev_1"), _evidence("ev_2", doc_id="doc_none")], documents
    )
    assert lines == ["L33822: revision effective 2024-10-01"]


# --- gaps found by the 1.5 spec review --------------------------------------------


def test_a_lone_low_confidence_item_is_weak_even_from_a_primary_source(
    tmp_path: Path,
) -> None:
    """docs/04 §4's `weak` has a second clause that was missing: "or a single
    supporting item with confidence < 0.6". A hedged reading of one passage is not a
    coverage determination, however authoritative the document."""
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph([_evidence("ev_1", confidence=0.3)], documents)
    assert graph.claims[0].status == "weak"


def test_low_confidence_support_does_not_contest(tmp_path: Path) -> None:
    """docs/04 §4: "supporting and contradicting evidence both present with confidence
    >= 0.6" — the threshold governs both sides, not just the contradiction."""
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph(
        [
            _evidence("ev_1", confidence=0.2),
            _evidence("ev_2", stance="contradicts", confidence=0.9),
        ],
        documents,
    )
    assert graph.claims[0].status == "weak"


def test_a_later_contradiction_governs_the_date_and_annotates_the_claim(
    tmp_path: Path,
) -> None:
    """docs/04 §4's third contradiction rule: "the later date governs and the claim's
    text is annotated". Without the annotation the claim reads as current when a newer
    source disagrees with it."""
    documents = {"doc_lcd": _document(tmp_path), "doc_art": _document(tmp_path, "doc_art")}
    graph = build_claim_graph(
        [
            _evidence("ev_1", effective=date(2023, 4, 16)),
            _evidence(
                "ev_2", stance="contradicts", confidence=0.9, effective=date(2025, 2, 18),
                doc_id="doc_art",
            ),
        ],
        documents,
    )
    claim = graph.claims[0]
    assert claim.governing_date == date(2025, 2, 18)  # the later date governs
    assert "contradicted by a later source effective 2025-02-18" in claim.text
    assert claim.status == "contested"


def test_an_earlier_contradiction_does_not_annotate(tmp_path: Path) -> None:
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph(
        [
            _evidence("ev_1", effective=date(2025, 2, 18)),
            _evidence("ev_2", stance="contradicts", confidence=0.9, effective=date(2023, 4, 16)),
        ],
        documents,
    )
    assert graph.claims[0].governing_date == date(2025, 2, 18)
    assert "contradicted by a later source" not in graph.claims[0].text


def test_governing_date_is_not_borrowed_from_a_weaker_source(tmp_path: Path) -> None:
    """The date feeds docs/04 §7's currency metric. When the primary passage carries no
    date, reporting a vendor page's date as governing is worse than reporting none."""
    documents = {
        "doc_lcd": _document(tmp_path),
        "doc_web": _document(tmp_path, "doc_web", tier="web"),
    }
    graph = build_claim_graph(
        [
            _evidence("ev_lcd", quality=1.0, effective=None),
            _evidence("ev_web", quality=0.3, doc_id="doc_web", effective=date(2026, 1, 1)),
        ],
        documents,
    )
    assert graph.claims[0].governing_date is None


def test_the_same_passage_for_the_opposite_stance_is_a_separate_item(
    store: EvidenceStore,
) -> None:
    """The evidence id used to hash only the passage, so a contradicting item over the
    same sentence silently returned the earlier supporting one — telling the agent its
    evidence was recorded while suppressing contested detection."""
    supports = store.add(
        doc_id="doc_lcd", branch_id="b1", claim_text="Insulin treatment qualifies",
        evidence_text="Coverage requires treatment with insulin", paragraph_index=2,
    )
    contradicts = store.add(
        doc_id="doc_lcd", branch_id="b1", claim_text="Insulin treatment is mandatory",
        evidence_text="Coverage requires treatment with insulin", paragraph_index=2,
        stance="contradicts", confidence=0.95,
    )
    assert supports.evidence_id != contradicts.evidence_id
    assert len(store.items) == 2
    assert contradicts.stance == "contradicts" and contradicts.confidence == 0.95


def test_an_over_long_passage_is_refused(store: EvidenceStore, tmp_path: Path) -> None:
    """docs/02 §2.4 caps evidence_text at 600 chars."""
    long_sentence = " ".join(f"word{i}" for i in range(200))  # well over 600 chars
    document = _document(tmp_path, "doc_long", body=f"## S\n\n{long_sentence}")
    store.documents["doc_long"] = document
    with pytest.raises(EvidenceRejected, match="max 600"):
        store.add(
            doc_id="doc_long", branch_id="b1", claim_text="c",
            evidence_text=long_sentence, paragraph_index=1,
        )


def test_an_out_of_range_paragraph_is_refused(store: EvidenceStore) -> None:
    with pytest.raises(EvidenceRejected, match="out of range"):
        store.add(
            doc_id="doc_lcd", branch_id="b1", claim_text="c",
            evidence_text="anything", paragraph_index=99,
        )


def test_an_unknown_document_is_refused(store: EvidenceStore) -> None:
    with pytest.raises(EvidenceRejected, match="unknown doc_id"):
        store.add(
            doc_id="doc_nope", branch_id="b1", claim_text="c",
            evidence_text="anything", paragraph_index=0,
        )


def test_context_evidence_neither_supports_nor_contradicts(tmp_path: Path) -> None:
    """docs/03 §4 rule 4 has the agent add the revision date as `context` evidence, so
    a context-only group must not read as a supported claim."""
    documents = {"doc_lcd": _document(tmp_path)}
    graph = build_claim_graph([_evidence("ev_1", stance="context")], documents)
    claim = graph.claims[0]
    assert claim.status == "unresolved"
    assert claim.supported_by == [] and claim.contradicted_by == []


def test_verify_reports_stale_offsets_instead_of_raising(store: EvidenceStore) -> None:
    """The check exists for the case where a document was refetched and offsets moved;
    it must report the broken ids, not raise from inside the check."""
    item = store.add(
        doc_id="doc_lcd", branch_id="b1", claim_text="c",
        evidence_text="Coverage requires treatment with insulin", paragraph_index=2,
    )
    assert store.verify() == []
    Path(store.documents["doc_lcd"].text_path).write_text(
        "## Coverage Guidance\n\nEntirely different text.\n", encoding="utf-8", newline="\n"
    )
    assert store.verify() == [item.evidence_id]


def test_verify_reports_a_missing_text_file(store: EvidenceStore) -> None:
    item = store.add(
        doc_id="doc_lcd", branch_id="b1", claim_text="c",
        evidence_text="Coverage requires treatment with insulin", paragraph_index=2,
    )
    Path(store.documents["doc_lcd"].text_path).unlink()
    assert store.verify() == [item.evidence_id]


def test_a_source_line_omits_publisher_it_does_not_have(tmp_path: Path) -> None:
    document = _document(tmp_path, publisher=None)
    line = cite.source_line(1, document)
    assert "None" not in line
    assert "primary_policy" in line

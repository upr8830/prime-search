"""BM25 over paragraphs (docs/01 §5, docs/03 §4).

Offline: builds a Document over text written to tmp_path, so no Tavily call.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from prime_search.primitives import docmeta, within
from prime_search.schemas import Document

BIG_TABLE = "\n".join(f"| A{4000 + i} | descriptor number {i} | covered |" for i in range(900))
BODY = "\n\n".join(
    [
        "## Coverage Guidance",
        "A continuous glucose monitor is covered when the beneficiary has diabetes.",
        "The beneficiary must be treated with insulin or have problematic hypoglycemia.",
        "## Coding Information",
        BIG_TABLE,
        "## Documentation Requirements",
        "The treating practitioner must document the clinical need in the medical record.",
    ]
    + [f"Filler paragraph number {i} about unrelated administrative matters." for i in range(25)]
)


@pytest.fixture(autouse=True)
def _clear_cache():
    within.clear_index_cache()
    yield
    within.clear_index_cache()


@pytest.fixture
def document(tmp_path: Path) -> Document:
    text = docmeta.normalize_text(BODY)
    path = tmp_path / "doc_test.txt"
    path.write_text(text, encoding="utf-8", newline="\n")
    return Document(
        doc_id="doc_test",
        url="https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1",
        title="Test LCD",
        source_tier="primary_policy",
        retrieved_at=datetime.now(UTC),
        text_path=str(path),
        paragraph_count=len(docmeta.split_paragraphs(text)),
        fetch_method="extract",
    )


def test_returns_the_relevant_paragraph_with_usable_offsets(document: Document) -> None:
    hits = within.search_within(document, "problematic hypoglycemia insulin")
    assert hits
    text = Path(document.text_path).read_text(encoding="utf-8")
    assert "problematic hypoglycemia" in hits[0].text
    for hit in hits:
        assert text[hit.char_start : hit.char_end] == hit.text


def test_k_is_respected_and_one_window_per_paragraph(document: Document) -> None:
    """`k=3` must not be filled with three slices of the same 900-row table."""
    hits = within.search_within(document, "descriptor covered number", k=3)
    assert len(hits) <= 3
    assert len({hit.paragraph_index for hit in hits}) == len(hits)


def test_oversized_paragraphs_are_windowed_not_returned_whole(document: Document) -> None:
    """docs/04 §2 keeps a table as one paragraph; a deep read must still not push the
    whole table into an agent's context."""
    paragraphs = within.load_paragraphs(document)
    table = max(paragraphs, key=lambda p: len(p.text))
    assert len(table.text) > within.MAX_PASSAGE_CHARS
    hits = within.search_within(document, "A4500 descriptor")
    assert hits
    assert all(len(hit.text) <= within.MAX_PASSAGE_CHARS for hit in hits)


def test_a_term_in_every_paragraph_still_returns_hits(document: Document) -> None:
    """Regression on the negative-score trap: BM25Okapi scores a term appearing in
    more than half the corpus below zero, so relevance cannot mean score > 0."""
    hits = within.search_within(document, "paragraph")
    assert hits


def test_results_are_deterministic(document: Document) -> None:
    first = within.search_within(document, "coverage insulin diabetes")
    second = within.search_within(document, "coverage insulin diabetes")
    assert [(h.paragraph_index, h.char_start) for h in first] == [
        (h.paragraph_index, h.char_start) for h in second
    ]


def test_an_empty_or_stopword_only_query_returns_nothing(document: Document) -> None:
    assert within.search_within(document, "") == []
    assert within.search_within(document, "   !!!   ") == []


def test_location_is_built_from_the_passage(document: Document) -> None:
    hit = within.search_within(document, "problematic hypoglycemia")[0]
    location = hit.location()
    assert location.paragraph_index == hit.paragraph_index
    assert (location.char_start, location.char_end) == (hit.char_start, hit.char_end)


def test_snippet_only_documents_are_refused(tmp_path: Path) -> None:
    """docs/04 §3 rule 1: a snippet is never evidence, so it is never searchable."""
    snippet = Document(
        doc_id="doc_snip",
        url="https://example.gov/x",
        title="x",
        source_tier="unknown",
        retrieved_at=datetime.now(UTC),
        fetch_method="snippet_only",
    )
    with pytest.raises(ValueError, match="call fetch"):
        within.search_within(snippet, "anything")


def test_paragraph_count_drift_is_refused(document: Document) -> None:
    """If the file and the Document disagree, every evidence offset would be wrong."""
    stale = document.model_copy(update={"paragraph_count": document.paragraph_count + 5})
    with pytest.raises(ValueError, match="paragraphs on disk"):
        within.search_within(stale, "insulin")


def test_index_is_rebuilt_when_the_text_changes(document: Document) -> None:
    """The cache is keyed by content hash, so a refetch cannot answer from a stale
    index."""
    within.search_within(document, "insulin")
    new_text = docmeta.normalize_text(BODY + "\n\nA brand new paragraph about tirzepatide.\n")
    Path(document.text_path).write_text(new_text, encoding="utf-8", newline="\n")
    refreshed = document.model_copy(
        update={"paragraph_count": len(docmeta.split_paragraphs(new_text))}
    )
    hits = within.search_within(refreshed, "tirzepatide")
    assert hits and "tirzepatide" in hits[0].text

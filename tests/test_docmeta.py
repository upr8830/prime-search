"""Document metadata and paragraph structure (docs/04 §2) — docs/09 §1.3's required
tests, against text saved from live extracts.

The fixtures are frozen bytes, so these assert exact values; the live check in
tests/test_primitives_live.py asserts invariants only, because the CMS revision date
moves. docs/08 §2 anticipated that, and it has already happened: L33822's current
revision is 10/01/2024 (R16), while the draft answer key still expects 2023-04-16.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from prime_search.primitives import docmeta

FIXTURES = Path(__file__).parent / "fixtures" / "docs"
LCD_URL = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"
ARTICLE_URL = "https://www.cms.gov/medicare-coverage-database/view/article.aspx?articleid=52464"
FDA_URL = (
    "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm"
    "?setid=adec4fd2-6858-4c99-91d4-531f5f2a2d79"
)

CASES = [
    ("cms-lcd-l33822", LCD_URL, "LCD - Glucose Monitors (L33822) - CMS"),
    ("cms-article-a52464", ARTICLE_URL, "Article - Glucose Monitor - Policy Article (A52464)"),
    ("fda-label-ozempic", FDA_URL, "Label: Ozempic- semaglutide injection, solution - DailyMed"),
]


def _text(slug: str) -> str:
    return (FIXTURES / f"{slug}.raw.md").read_text(encoding="utf-8")


def _meta(slug: str, url: str, title: str) -> docmeta.DocMeta:
    return docmeta.extract_meta(url=url, title=title, text=_text(slug))


def test_lcd_l33822() -> None:
    meta = _meta(*CASES[0])
    assert (meta.doc_type, meta.document_id_external) == ("LCD", "L33822")
    assert meta.publisher == "CMS"
    # The header metadata block is JavaScript-rendered and missing from the extract,
    # so the date comes from the Revision History table: latest revision, R16.
    assert meta.revision_date == date(2024, 10, 1)
    # And there is genuinely no "Original Effective Date" in the extracted text.
    # docs/04 §2: fields stay None, and a missing policy date is a critic finding.
    assert meta.effective_date is None
    assert meta.paragraph_count >= 20  # docs/11 R2's threshold
    assert "Coverage Guidance" in meta.sections
    assert "Revision History Information" in meta.sections


def test_article_a52464() -> None:
    meta = _meta(*CASES[1])
    assert (meta.doc_type, meta.document_id_external) == ("Article", "A52464")
    assert meta.revision_date == date(2025, 2, 18)
    assert meta.effective_date is None
    assert meta.paragraph_count >= 20


def test_fda_label() -> None:
    """docs/09 §1.3's FDA page. The SPL id pattern is this build's invention: no spec
    gives one (docs/11 decision log)."""
    meta = _meta(*CASES[2])
    assert meta.doc_type == "Label"
    assert meta.document_id_external == "SPL adec4fd2-6858-4c99-91d4-531f5f2a2d79"
    # "Updated June 1, 2026" — FDA labels do not use any docs/04 §2 label verbatim.
    assert meta.revision_date == date(2026, 6, 1)


def test_external_id_comes_from_the_url_not_the_body() -> None:
    """L33822's body cites A52464, A59330 and A58798, so a text-first search would
    file the LCD as an Article."""
    assert _meta(*CASES[0]).document_id_external == "L33822"


def test_a_date_label_in_a_table_header_is_not_read_as_its_value() -> None:
    """CMS's "Associated Documents" table puts `Effective Dates` in a column header;
    the nearest following date is the *Updated On* cell of the next row. Reading it
    would have given L33822 an effective date of 2024-10-09, which is another
    column's value."""
    assert "| Updated On | Effective Dates | Status |" in _text("cms-lcd-l33822")
    assert _meta(*CASES[0]).effective_date is None


@pytest.mark.parametrize(("slug", "url", "title"), CASES)
def test_paragraph_offsets_round_trip(slug: str, url: str, title: str) -> None:
    """docs/04 §3 validates evidence as a substring of the referenced paragraph, so
    text and offsets must be identical, not merely similar."""
    text = _text(slug)
    assert docmeta.normalize_text(text) == text  # the fixture is already normalized
    assert "\r" not in text  # a CRLF checkout could not shift the offsets

    paragraphs = docmeta.split_paragraphs(text)
    assert paragraphs
    assert [p.index for p in paragraphs] == list(range(len(paragraphs)))
    previous_end = -1
    for paragraph in paragraphs:
        assert text[paragraph.char_start : paragraph.char_end] == paragraph.text
        assert paragraph.text.strip()  # never a blank paragraph
        # Leading indentation is preserved on purpose: DailyMed nests list
        # continuations, and docs/04 §3 compares evidence against this text verbatim.
        assert not paragraph.text.startswith("\n") and not paragraph.text.endswith("\n")
        assert paragraph.char_start > previous_end
        previous_end = paragraph.char_end
    # Re-splitting yields byte-identical offsets: the property within.py and the UI
    # document view both rely on.
    assert docmeta.split_paragraphs(text) == paragraphs


def test_tables_survive_as_single_paragraphs() -> None:
    """docs/04 §2: "Tables are kept as single paragraphs." L33822's revision-history
    table is one 16 KB paragraph, which is why within.py windows for indexing."""
    paragraphs = docmeta.split_paragraphs(_text("cms-lcd-l33822"))
    tables = [p for p in paragraphs if p.text.count("\n|") > 5]
    assert tables
    biggest = max(tables, key=lambda p: len(p.text))
    assert len(biggest.text) > 10_000
    assert biggest.text.count("| --- |") >= 1  # the separator row is inside, not split


def test_normalize_text_is_idempotent_and_folds_punctuation() -> None:
    raw = "A “curly” quote—and a ‐hyphen and nbsp.\n\n\n\nNext."
    once = docmeta.normalize_text(raw)
    assert docmeta.normalize_text(once) == once
    assert '"curly"' in once
    assert "—" not in once and "‐" not in once and " " not in once
    assert "\n\n\n" not in once


def test_dates_ignore_markdown_link_text_and_na() -> None:
    text = docmeta.normalize_text(
        "[Revision Effective Date](https://example.gov/help?x=1)\n\n"
        "Original Effective Date\n\n10/01/2015\n\n"
        "Revision Effective Date\n\n02/18/2025\n\n"
        "Revision Ending Date\n\nN/A\n\nRetirement Date\n\nN/A\n"
    )
    meta = docmeta.extract_meta(url="https://www.cms.gov/x", title="t", text=text)
    assert (meta.effective_date, meta.revision_date) == (date(2015, 10, 1), date(2025, 2, 18))
    assert meta.extra_dates == {}  # both N/A, so neither is invented


def test_revision_effective_date_wins_over_bare_effective_date() -> None:
    """Longest label first, or `Effective Date` swallows `Revision Effective Date`."""
    text = docmeta.normalize_text("Revision Effective Date: 10/01/2024\n")
    meta = docmeta.extract_meta(url="https://www.cms.gov/x", title="t", text=text)
    assert meta.revision_date == date(2024, 10, 1)
    assert meta.effective_date is None


def test_future_dated_revisions_do_not_outrank_the_current_one() -> None:
    text = docmeta.normalize_text(
        "Revision Effective Date: 01/01/2024\n\nRevision Effective Date: 01/01/2099\n"
    )
    meta = docmeta.extract_meta(url="https://www.cms.gov/x", title="t", text=text)
    assert meta.revision_date == date(2024, 1, 1)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("10/01/2024", date(2024, 10, 1)),
        ("2023-04-16", date(2023, 4, 16)),
        ("April 16, 2023", date(2023, 4, 16)),
        ("16 Apr 2023", date(2023, 4, 16)),
        ("5/2026", date(2026, 5, 1)),  # FDA label form; day defaults to the 1st
        ("June/2026", date(2026, 6, 1)),
        ("13/45/2024", None),
        ("L33822", None),  # ids and codes are never dates
        ("A4239", None),
        ("1955-01-01", None),  # before Medicare existed
    ],
)
def test_tolerant_date_parser(token: str, expected: date | None) -> None:
    assert docmeta.parse_date_token(token) == expected


# --- regressions found by the 1.3 spec review ------------------------------------


def test_a_label_does_not_reach_across_an_empty_field_to_the_next_one() -> None:
    """"Notice Period Start Date" is a real CMS LCD header field. An "Effective Date"
    with no value must not borrow the next field's date."""
    text = docmeta.normalize_text(
        "Effective Date\n\nNotice Period Start Date\n\n10/01/2024\n\nRevision Effective Date\n\n02/01/2025\n"
    )
    meta = docmeta.extract_meta(url="https://www.cms.gov/x", title="t", text=text)
    assert meta.effective_date is None
    assert meta.revision_date == date(2025, 2, 1)


def test_the_weak_revised_label_does_not_read_dates_out_of_prose() -> None:
    """A revision-history cell reading "Revised to add code A4239 effective
    07/01/2018" must not book that date as the document's revision."""
    text = docmeta.normalize_text(
        "| 01/15/2020 | Revised to add code A4239 effective 07/01/2018 |\n"
    )
    meta = docmeta.extract_meta(url="https://www.cms.gov/x", title="t", text=text)
    assert meta.revision_date is None


def test_the_weak_revised_label_still_reads_an_fda_label_date() -> None:
    text = docmeta.normalize_text("Revised: 5/2026\n")
    meta = docmeta.extract_meta(url="https://dailymed.nlm.nih.gov/x", title="t", text=text)
    assert meta.revision_date == date(2026, 5, 1)


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        # A non-month word matching the month-name shape must not abandon the search.
        ("Chapter 15, 2024 revised April 16, 2023", date(2023, 4, 16)),
        # A manual reference is not a month-year date.
        ("Pub 100-02/2024", None),
        ("CMS Pub. 100-04/2026 chapter 20", None),
    ],
)
def test_date_parsing_regressions(token: str, expected: date | None) -> None:
    assert docmeta.parse_date_token(token) == expected

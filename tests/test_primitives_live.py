"""docs/09 §1.3's acceptance Check, against the live pages.

Marked `live`: skipped without keys, so `make test` stays offline. Run with

    uv run --env-file .env pytest tests/test_primitives_live.py -m live -q -s

Invariants only, never exact dates. docs/08 §2 expects the CMS revision date to drift
away from the draft answer key, and it already has (L33822 is on R16, 10/01/2024,
while the draft key still says 2023-04-16). A test that pinned the date would fail
for the wrong reason.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from prime_search.primitives import (
    CGM_LCD_URL,
    MIN_PARAGRAPHS,
    PRIMARY_DOMAINS,
    fetch,
    search,
    search_within,
)


@pytest.mark.live
def test_fetch_of_the_cgm_lcd(tmp_path: Path) -> None:
    """The docs/09 §1.3 Check, with the kickoff's stricter paragraph threshold."""
    result = fetch(CGM_LCD_URL, run_dir=tmp_path)
    document = result.document

    assert result.error is None
    assert document.document_id_external == "L33822"
    assert document.doc_type == "LCD"
    assert document.source_tier == "primary_policy"
    assert document.fetch_method in {"extract", "raw_content"}

    # A *valid* revision date, not a specific one.
    assert document.revision_date is not None
    assert 2015 <= document.revision_date.year <= date.today().year + 1

    assert document.paragraph_count >= MIN_PARAGRAPHS  # docs/11 R2
    assert result.sections
    assert Path(document.text_path).read_text(encoding="utf-8").strip()


@pytest.mark.live
def test_deep_read_of_the_cgm_lcd_returns_citable_passages(tmp_path: Path) -> None:
    """Every passage must be a verbatim slice of the persisted text, because docs/04
    §3 validates evidence as a substring of the paragraph it cites."""
    document = fetch(CGM_LCD_URL, run_dir=tmp_path).document
    text = Path(document.text_path).read_text(encoding="utf-8")

    passages = search_within(document, "coverage criteria therapeutic continuous glucose monitor")
    assert passages
    for passage in passages:
        assert text[passage.char_start : passage.char_end] == passage.text
        assert 0 <= passage.paragraph_index < document.paragraph_count


@pytest.mark.live
def test_search_is_cached_on_the_second_call() -> None:
    """docs/04 §6: the cache is what makes bench and GEPA re-runs affordable."""
    query = "Medicare LCD glucose monitors coverage criteria"
    first = search(query, include_domains=PRIMARY_DOMAINS, max_results=3)
    second = search(query, include_domains=PRIMARY_DOMAINS, max_results=3)

    assert first.hits and not first.error
    assert second.cached is True
    assert [hit.url for hit in second.hits] == [hit.url for hit in first.hits]
    assert any(hit.tier == "primary_policy" for hit in first.hits)

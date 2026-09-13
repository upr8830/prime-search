"""The docs/09 §1.8 check, run live: fetch the governing documents, review the diff.

    uv run --env-file .env pytest tests/test_searchbench_live.py -m live -q -s

Asserts the one thing the whole task exists to produce: that the pipeline notices the
draft answer keys are out of date. `docs/08` §2 — "If a draft key turns out to be wrong,
that is expected and is a line for the technical statement."
"""

from __future__ import annotations

import pytest

from eval.searchbench import load_records
from eval.searchbench.fetch_sources import check_dates, resolve
from eval.searchbench.schema import AnswerKey

pytestmark = pytest.mark.live


def test_the_cgm_lcd_resolves_and_its_revision_date_contradicts_the_draft(capsys) -> None:
    """The headline finding: five draft keys assert the CGM criteria changed on
    2023-04-16, and L33822 has been revised since."""
    from prime_search.config import get_settings
    from prime_search.primitives import tavily

    get_settings().export_sdk_env()
    documents: dict = {}

    record = next(r for r in load_records() if r.id == "cgm-elig-001")
    resolution = resolve("L33822", record.answer_key)
    assert resolution.method in {"record_url", "id"}, "L33822 must resolve deterministically"

    result = tavily.fetch(resolution.url, docs=documents)
    resolution.document = result.document
    document = result.document

    with capsys.disabled():
        print(f"\nL33822 -> {document.url}")
        print(f"  tier {document.source_tier} · {document.paragraph_count} paragraphs")
        print(f"  revision_date {document.revision_date} · effective_date {document.effective_date}")

    assert document.source_tier == "primary_policy"
    assert document.paragraph_count > 100, "the LCD did not extract properly"
    assert document.revision_date is not None

    flags = check_dates(record, {"L33822": resolution})
    with capsys.disabled():
        for flag in flags:
            print(f"  {flag}")
    assert flags, "the draft asserts 2023-04-16; a live revision date should contradict it"
    assert "2023-04-16" in flags[0].detail


def test_a_prose_descriptor_resolves_to_a_government_source(capsys) -> None:
    """11 of 30 records name their governing document only in prose. The search is
    restricted to primary domains, so whatever comes back is at least official — which
    is the most that can be claimed for a guess."""
    from prime_search.config import get_settings
    from prime_search.primitives import sources

    get_settings().export_sdk_env()
    resolution = resolve("SSA 1927(d)(2)(A)", AnswerKey(summary=""))

    with capsys.disabled():
        print(f"\n'SSA 1927(d)(2)(A)' -> {resolution.method}: {resolution.url}")

    assert resolution.method == "search"
    assert resolution.needs_review, "a search hit is a guess and must say so"
    assert sources.at_least(sources.tier_for(resolution.url), "official_secondary")

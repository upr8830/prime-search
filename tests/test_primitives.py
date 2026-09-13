"""Tavily parameter choices from docs/01 §5.

These constants define retrieval quality. A silent change to any of them would
only show up much later as a bench regression, so they are pinned here.
"""

from __future__ import annotations

from prime_search.primitives import extract_tool, search_tool
from prime_search.primitives.tavily import CGM_LCD_URL


def test_search_defaults_match_spec(offline_credentials) -> None:
    tool = search_tool()
    assert tool.max_results == 8
    assert tool.search_depth == "advanced"
    assert tool.include_raw_content is False  # docs/01 §5: fetch separately


def test_search_filters_are_optional_and_passed_through(offline_credentials) -> None:
    plain = search_tool()
    assert not plain.include_domains
    assert plain.time_range is None

    filtered = search_tool(include_domains=["cms.gov"], time_range="year", max_results=3)
    assert filtered.include_domains == ["cms.gov"]
    assert filtered.time_range == "year"
    assert filtered.max_results == 3


def test_extract_uses_advanced_depth(offline_credentials) -> None:
    assert extract_tool().extract_depth == "advanced"


def test_cgm_lcd_fixture_url_is_the_coverage_database_lcd() -> None:
    """Every retrieval check in docs/09 §1.2-1.3 uses this document."""
    assert "medicare-coverage-database" in CGM_LCD_URL
    assert "lcdid=33822" in CGM_LCD_URL

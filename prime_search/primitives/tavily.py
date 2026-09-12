"""Tavily-backed retrieval (docs/01 §5).

Task 1.2 defines the configured tool constructors only: the parameter choices from
docs/01 §5 live here so nothing else in the project constructs a Tavily tool, and
`make smoke` can probe the credentials and the endpoint. Task 1.3 adds search(),
fetch(), the on-disk cache keyed by args, and the raw-content fallback.
"""

from __future__ import annotations

from langchain_tavily import TavilyExtract, TavilySearch

# docs/01 §5: primary-source domains. The authoritative tier mapping lands in
# primitives/sources.py at task 1.3 and is shared with the evidence model.
PRIMARY_DOMAINS = ["cms.gov", "fda.gov"]

# The Medicare LCD for glucose monitors: the fixture every retrieval check uses
# (docs/09 §1.2-1.3, docs/11 A6).
CGM_LCD_URL = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"


def search_tool(
    *,
    max_results: int = 8,
    include_domains: list[str] | None = None,
    time_range: str | None = None,
) -> TavilySearch:
    """docs/01 §5: advanced depth, 8 results, raw content fetched separately."""
    kwargs = {
        "max_results": max_results,
        "search_depth": "advanced",
        "include_raw_content": False,
    }
    if include_domains:
        kwargs["include_domains"] = include_domains
    if time_range:
        kwargs["time_range"] = time_range
    return TavilySearch(**kwargs)


def extract_tool(*, extract_depth: str = "advanced") -> TavilyExtract:
    """docs/01 §5: advanced extract depth; results are cached by the caller."""
    return TavilyExtract(extract_depth=extract_depth)

"""Retrieval primitives. Every Tavily call in the project goes through this package
(CLAUDE.md); docs/01 §5 defines the contract.

Task 1.3: `search`/`fetch` with the args-keyed cache and the raw-content fallback
(tavily.py), source tiers and URL identity (sources.py), document metadata and
paragraph structure (docmeta.py), BM25 over paragraphs (within.py). The budget-aware
tools the sub-agent actually sees are task 1.6 (docs/03 §4).
"""

from prime_search.primitives.docmeta import (
    DocMeta,
    Paragraph,
    extract_meta,
    find_date_token,
    normalize_text,
    parse_date_token,
    split_paragraphs,
)
from prime_search.primitives.sources import (
    OFFICIAL_DOMAINS,
    PRIMARY_DOMAINS,
    SOURCE_QUALITY,
    TIER_RANK,
    Tier,
    at_least,
    classify,
    doc_id_for,
    domains_for,
    normalize_url,
    quality,
    refine_tier,
    tier_for,
    tier_rank,
)
from prime_search.primitives.tavily import (
    CGM_LCD_URL,
    MAX_RESULTS,
    MIN_PARAGRAPHS,
    FetchResult,
    SearchHit,
    SearchResult,
    extract_tool,
    fetch,
    search,
    search_tool,
)
from prime_search.primitives.within import Passage, load_paragraphs, search_within

__all__ = [  # grouped by module rather than alphabetized
    "CGM_LCD_URL",
    "MAX_RESULTS",
    "MIN_PARAGRAPHS",
    "OFFICIAL_DOMAINS",
    "PRIMARY_DOMAINS",
    "SOURCE_QUALITY",
    "TIER_RANK",
    "DocMeta",
    "FetchResult",
    "Paragraph",
    "Passage",
    "SearchHit",
    "SearchResult",
    "Tier",
    "at_least",
    "classify",
    "doc_id_for",
    "domains_for",
    "extract_meta",
    "extract_tool",
    "fetch",
    "find_date_token",
    "load_paragraphs",
    "normalize_text",
    "normalize_url",
    "parse_date_token",
    "quality",
    "refine_tier",
    "search",
    "search_tool",
    "search_within",
    "split_paragraphs",
    "tier_for",
    "tier_rank",
]

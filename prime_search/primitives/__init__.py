"""Retrieval primitives. Every Tavily call in the project goes through this package
(CLAUDE.md); docs/01 §5 defines the contract.

Task 1.2 provides only the configured tool constructors, which `make smoke` probes.
Task 1.3 adds search/fetch with the on-disk cache, source tiers, document metadata
and BM25 over paragraphs.
"""

from prime_search.primitives.tavily import extract_tool, search_tool

__all__ = ["search_tool", "extract_tool"]

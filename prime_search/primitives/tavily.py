"""Tavily-backed retrieval (docs/01 §5).

Everything that touches the Tavily API lives here (CLAUDE.md): the configured tool
constructors, `search`, `fetch`, the on-disk cache keyed by args (docs/04 §6) and the
raw-content fallback (docs/01 §5).

Three behaviours worth knowing before reading:

* **Errors never raise.** docs/01 §9: a Tavily error returns an empty result with
  `error` set, the sub-agent may retry with a reformulated query, and the budget
  still counted the call. `langchain_tavily` sets `handle_tool_error=True`, so a
  failed invoke arrives as a *string* or as `{"error": exc}`; `_invoke` normalizes
  both into `(response, error)`.
* **`fetch` takes a URL or a doc_id.** docs/01 §5 says `fetch(url)` and docs/03 §4
  says `fetch(doc_id)`; one implementation serves both, resolving ids against the
  caller's document mapping (`ws.documents`, docs/02 §3).
* **`fetch` falls back on thin extracts.** docs/11 R2's trigger is "fetch yields
  < 20 paragraphs on L33822", so an extract below `MIN_PARAGRAPHS` re-issues `search`
  with `include_raw_content=True` restricted to the URL's own domain and keeps
  whichever text has more paragraphs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_tavily import TavilyExtract, TavilySearch

from prime_search.config import get_settings
from prime_search.primitives import docmeta
from prime_search.primitives.sources import (
    OFFICIAL_DOMAINS,
    PRIMARY_DOMAINS,
    Tier,
    classify,
    doc_id_for,
    host_of,
    normalize_url,
    refine_tier,
)
from prime_search.schemas import Document

MAX_RESULTS = 8  # docs/01 §5, docs/03 §4
MIN_PARAGRAPHS = 20  # docs/11 R2's quality trigger
_CACHE_VERSION = 1  # bump to invalidate every entry when canonicalization changes

# The Medicare LCD for glucose monitors: the fixture every retrieval check uses
# (docs/09 §1.2-1.3, docs/11 A6).
CGM_LCD_URL = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"

__all__ = [
    "CGM_LCD_URL",
    "MAX_RESULTS",
    "MIN_PARAGRAPHS",
    "OFFICIAL_DOMAINS",
    "PRIMARY_DOMAINS",
    "FetchResult",
    "SearchHit",
    "SearchResult",
    "cache_key_for_search",
    "extract_tool",
    "fetch",
    "search",
    "search_tool",
]


def search_tool(
    *,
    max_results: int = MAX_RESULTS,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    time_range: str | None = None,
    include_raw_content: bool = False,
    api_key: str | None = None,
) -> TavilySearch:
    """docs/01 §5: advanced depth, 8 results, raw content fetched separately.

    `include_raw_content` has to be set at construction — langchain_tavily rejects it
    at invoke time — and is only ever True on the fallback path. The key comes from
    Settings rather than the ambient environment, so a tool built here never depends
    on whether `export_sdk_env()` has run yet.
    """
    kwargs: dict[str, Any] = {
        "max_results": max_results,
        "search_depth": "advanced",
        "include_raw_content": include_raw_content,
        "tavily_api_key": api_key or get_settings().tavily_api_key,
    }
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains
    if time_range:
        kwargs["time_range"] = time_range
    return TavilySearch(**kwargs)


def extract_tool(*, extract_depth: str = "advanced", api_key: str | None = None) -> TavilyExtract:
    """docs/01 §5: advanced extract depth; results are cached by the caller.

    `format="markdown"` is the vendor default, pinned because docmeta's section
    detection reads markdown heading markers.
    """
    return TavilyExtract(
        extract_depth=extract_depth,
        format="markdown",
        tavily_api_key=api_key or get_settings().tavily_api_key,
    )


# --- results ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One row of docs/03 §4's search tool output."""

    doc_id: str
    url: str
    title: str
    snippet: str
    tier: Tier
    date_hint: str | None
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Exactly the six keys docs/03 §4 promises the sub-agent; score is internal."""
        return {
            "doc_id": self.doc_id,
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "tier": self.tier,
            "date_hint": self.date_hint,
        }


@dataclass(slots=True)
class SearchResult:
    query: str
    hits: list[SearchHit] = field(default_factory=list)
    cached: bool = False
    error: str | None = None

    @property
    def n_results(self) -> int:
        return len(self.hits)

    def event(self, task_id: str) -> dict[str, Any]:
        """docs/02 §4's `search` event payload."""
        return {
            "task_id": task_id,
            "query": self.query,
            "n_results": self.n_results,
            "cached": self.cached,
        }


@dataclass(slots=True)
class FetchResult:
    document: Document
    sections: list[str] = field(default_factory=list)
    cached: bool = False
    error: str | None = None

    def event(self, task_id: str) -> dict[str, Any]:
        """docs/02 §4's `fetch` event payload."""
        return {
            "task_id": task_id,
            "doc_id": self.document.doc_id,
            "url": self.document.url,
            "title": self.document.title,
            "tier": self.document.source_tier,
            "effective_date": (
                self.document.effective_date.isoformat()
                if self.document.effective_date
                else None
            ),
        }


# --- cache (docs/04 §6) ----------------------------------------------------------


def _cache_dir() -> Path:
    return Path(get_settings().tavily_cache_dir)


def _canonical_search_args(
    query: str,
    *,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    time_range: str | None = None,
    max_results: int = MAX_RESULTS,
    include_raw_content: bool = False,
) -> dict[str, Any]:
    """Everything that changes the response, nothing that does not.

    The query is casefolded and whitespace-collapsed and domain lists are sorted, so
    two agents phrasing the same call differently share one entry. The API key is
    never part of the key.
    """
    return {
        "query": re.sub(r"\s+", " ", query).strip().casefold(),
        "include_domains": sorted({domain.lower() for domain in include_domains or []}),
        "exclude_domains": sorted({domain.lower() for domain in exclude_domains or []}),
        "time_range": time_range,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_raw_content": include_raw_content,
    }


def _canonical_extract_args(url: str) -> dict[str, Any]:
    return {"url": normalize_url(url), "extract_depth": "advanced", "format": "markdown"}


def _cache_key(op: str, args: dict[str, Any]) -> str:
    payload = json.dumps(
        {"v": _CACHE_VERSION, "op": op, "args": args},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def cache_key_for_search(query: str, **kwargs: Any) -> str:
    """Exposed for the cache tests and for `make bench` cache-hit accounting."""
    return _cache_key("search", _canonical_search_args(query, **kwargs))


def _cache_read(op: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """docs/04 §6: `.cache/tavily/<sha1(args)>.json`.

    Any problem is a miss, never a failure. The entry stores its own args and a
    mismatch is treated as a miss, so a hash collision or a stale file cannot answer
    for a different call.
    """
    if not get_settings().tavily_cache:
        return None
    path = _cache_dir() / f"{_cache_key(op, args)}.json"
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if entry.get("op") != op or entry.get("args") != args:
        return None
    response = entry.get("response")
    return response if isinstance(response, dict) else None


def _cache_write(op: str, args: dict[str, Any], response: dict[str, Any]) -> None:
    if not get_settings().tavily_cache:
        return
    directory = _cache_dir()
    path = directory / f"{_cache_key(op, args)}.json"
    entry = {
        "op": op,
        "args": args,
        "cached_at": datetime.now(UTC).isoformat(),
        "response": response,
    }
    try:
        directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8", newline="\n")
        temporary.replace(path)  # atomic: a crashed write never leaves half an entry
    except OSError:
        pass  # the cache is an optimization (docs/04 §6), never a dependency


def _invoke(tool: Any, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize every langchain_tavily failure mode into (response, error).

    The tools carry `handle_tool_error=True`, so "no results" comes back as a string
    and transport errors as `{"error": exc}`. docs/01 §9 wants both as an empty
    result with `error` set.
    """
    try:
        raw = tool.invoke(payload)
    except Exception as exc:  # network, auth, validation
        return None, f"{type(exc).__name__}: {exc}"
    if isinstance(raw, str):
        return None, raw.strip()[:300]
    if not isinstance(raw, dict):
        return None, f"unexpected Tavily response type {type(raw).__name__}"
    if raw.get("error"):
        return None, str(raw["error"])[:300]
    return raw, None


def _cached_call(
    op: str,
    args: dict[str, Any],
    call: Any,
) -> tuple[dict[str, Any] | None, bool, str | None]:
    """Cache-read, else invoke and cache-write. Returns (response, cached, error)."""
    response = _cache_read(op, args)
    if response is not None:
        return response, True, None
    response, error = call()
    if response is not None:
        _cache_write(op, args, response)
    return response, False, error


# --- search ----------------------------------------------------------------------


def search(
    query: str,
    *,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    time_range: str | None = None,
    max_results: int = MAX_RESULTS,
    docs: MutableMapping[str, Document] | None = None,
    api_key: str | None = None,
) -> SearchResult:
    """docs/03 §4: up to 8 hits, each registered in `docs` as `snippet_only`.

    `docs` is the caller's `ws.documents` (docs/02 §3). An already-fetched document is
    never downgraded back to a snippet, which is what makes repeated searches
    idempotent. Budget accounting belongs to the tool wrapper (task 1.6), so this
    function's only side effects are the cache and `docs`.
    """
    args = _canonical_search_args(
        query,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        time_range=time_range,
        max_results=max_results,
    )
    response, cached, error = _cached_call(
        "search",
        args,
        lambda: _invoke(
            search_tool(
                max_results=max_results,
                include_domains=include_domains,
                exclude_domains=exclude_domains,
                time_range=time_range,
                api_key=api_key,
            ),
            {"query": query},
        ),
    )
    if response is None:
        return SearchResult(query=query, hits=[], cached=False, error=error)

    hits: list[SearchHit] = []
    for raw in response.get("results", []):
        url = raw.get("url") or ""
        if not url:
            continue
        title = raw.get("title") or url
        snippet = raw.get("content") or ""
        tier, publisher = classify(url)
        date_hint = raw.get("published_date") or None
        if not date_hint:
            found = docmeta.find_date_token(f"{title}\n{snippet}")
            date_hint = found.isoformat() if found else None
        hit = SearchHit(
            doc_id=doc_id_for(url),
            url=url,
            title=title,
            snippet=snippet,
            tier=tier,
            date_hint=date_hint,
            score=float(raw.get("score") or 0.0),
        )
        hits.append(hit)
        if docs is None:
            continue
        existing = docs.get(hit.doc_id)
        if existing is None or not existing.is_fetched:
            docs[hit.doc_id] = Document(
                doc_id=hit.doc_id,
                url=url,
                title=title,
                source_tier=tier,
                publisher=publisher,
                retrieved_at=datetime.now(UTC),
                fetch_method="snippet_only",  # text_path="", paragraph_count=0
            )
    return SearchResult(query=query, hits=hits, cached=cached, error=None)


# --- fetch -----------------------------------------------------------------------


def _resolve_target(
    target: str, docs: MutableMapping[str, Document] | None
) -> tuple[str, Document | None]:
    """docs/01 §5's `fetch(url)` and docs/03 §4's `fetch(doc_id)` in one entry point."""
    if not target.startswith("doc_"):
        return target, (docs or {}).get(doc_id_for(target))
    known = (docs or {}).get(target)
    if known is None:
        raise ValueError(
            f"unknown doc_id {target!r}: search first, or pass the URL. doc_ids only "
            "exist for documents already in ws.documents (docs/03 §4)."
        )
    return known.url, known


def _fallback_query(url: str, title: str | None) -> str:
    """A query narrow enough to surface the target page (docs/01 §5's fallback)."""
    if title:
        return title
    parts = re.split(r"[/?&=._-]+", url)
    return " ".join(part for part in parts[-6:] if part and not part.isdigit()) or url


def _extract_text(url: str, api_key: str | None) -> tuple[str, str | None, bool, str | None]:
    """(raw_text, title, cached, error) via Tavily Extract."""
    args = _canonical_extract_args(url)
    response, cached, error = _cached_call(
        "extract", args, lambda: _invoke(extract_tool(api_key=api_key), {"urls": [url]})
    )
    if response is None:
        return "", None, False, error
    results = response.get("results") or []
    if not results:
        failed = response.get("failed_results")
        return "", None, cached, f"extract returned no results (failed={str(failed)[:150]})"
    return results[0].get("raw_content") or "", results[0].get("title"), cached, None


def _raw_content_text(
    url: str, title: str | None, api_key: str | None
) -> tuple[str, str | None, bool, str | None]:
    """docs/01 §5's fallback: re-issue `search` with raw content, restricted to the
    URL's own domain.

    Only an exact normalized-URL match is accepted, so `doc_id` keeps pointing at the
    page the text actually came from.
    """
    query = _fallback_query(url, title)
    domain = host_of(url)
    args = _canonical_search_args(
        query, include_domains=[domain], max_results=5, include_raw_content=True
    )
    response, cached, error = _cached_call(
        "search_raw",
        args,
        lambda: _invoke(
            search_tool(
                max_results=5,
                include_domains=[domain],
                include_raw_content=True,
                api_key=api_key,
            ),
            {"query": query},
        ),
    )
    if response is None:
        return "", None, False, error
    wanted = normalize_url(url)
    for raw in response.get("results", []):
        if normalize_url(raw.get("url") or "") == wanted and raw.get("raw_content"):
            return raw["raw_content"], raw.get("title"), cached, None
    return "", None, cached, f"raw-content fallback found no exact match for {wanted}"


def _sections_from_sidecar(document: Document) -> list[str]:
    """Section headings recorded at fetch time; empty if the sidecar is unreadable."""
    sidecar = Path(document.text_path).with_suffix(".meta.json")
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    sections = payload.get("sections")
    return sections if isinstance(sections, list) else []


def _text_root(run_dir: Path | None) -> Path:
    """docs/04 §6 persists to `runs/<run_id>/docs/`.

    Outside a run — tests, bench fixtures, `fetch_sources.py` — text goes under the
    gitignored Tavily cache, so `text_path` is always a real file and docs/04 §3 has
    something to validate evidence against.
    """
    return (run_dir / "docs") if run_dir else (_cache_dir() / "docs")


def fetch(
    target: str,
    *,
    docs: MutableMapping[str, Document] | None = None,
    run_dir: Path | None = None,
    title: str | None = None,
    min_paragraphs: int = MIN_PARAGRAPHS,
    api_key: str | None = None,
) -> FetchResult:
    """Fetch, parse, tier-refine and persist one document (docs/01 §5, docs/04 §2, §6).

    Idempotent within a run (docs/03 §13): an already-fetched document whose text is
    still on disk comes back without an API call.
    """
    url, known = _resolve_target(target, docs)
    doc_id = known.doc_id if known else doc_id_for(url)
    if known is not None and known.is_fetched and Path(known.text_path).is_file():
        # docs/03 §4: fetch returns section headings. The cached path must return the
        # same shape as the first call, so read them back from the sidecar.
        return FetchResult(document=known, sections=_sections_from_sidecar(known), cached=True)

    hint_title = title or (known.title if known else None)
    text_raw, extracted_title, cached, error = _extract_text(url, api_key)
    text = docmeta.normalize_text(text_raw)
    paragraphs = docmeta.split_paragraphs(text)
    method = "extract"

    # docs/11 R2: a thin extract is a quality failure, not merely an error.
    thin = len(paragraphs) < min_paragraphs
    if error or thin:
        alt_raw, alt_title, alt_cached, alt_error = _raw_content_text(url, hint_title, api_key)
        alt_text = docmeta.normalize_text(alt_raw)
        alt_paragraphs = docmeta.split_paragraphs(alt_text)
        if len(alt_paragraphs) > len(paragraphs):
            text, paragraphs, method = alt_text, alt_paragraphs, "raw_content"
            extracted_title = alt_title or extracted_title
            cached = cached and alt_cached
            # Improved, but "better" is not the bar: R2's trigger is the threshold.
            # Clearing `error` here whenever the fallback helped *at all* would hide a
            # document that is still too thin to cite.
            error = (
                None
                if len(alt_paragraphs) >= min_paragraphs
                else (
                    f"raw-content fallback improved this to {len(alt_paragraphs)} "
                    f"paragraphs, still under {min_paragraphs}"
                )
            )
        else:
            # The fallback did not help. Say so: a document that stays under the
            # threshold is the R2 trigger the operator needs to see, and a silent
            # `error=None` here would hide it.
            reason = (
                f"extract yielded {len(paragraphs)} paragraphs (< {min_paragraphs})"
                if thin
                else error
            )
            error = f"{reason}; raw-content fallback did not improve it: {alt_error}"

    url_tier, rule_publisher = classify(url)
    if not paragraphs:
        # docs/01 §9: an empty result with `error` set; the document stays a snippet.
        document = known or Document(
            doc_id=doc_id,
            url=url,
            title=hint_title or url,
            source_tier=url_tier,
            publisher=rule_publisher,
            retrieved_at=datetime.now(UTC),
            fetch_method="snippet_only",
        )
        if docs is not None:
            docs[document.doc_id] = document
        return FetchResult(
            document=document, sections=[], cached=False, error=error or "no text extracted"
        )

    meta = docmeta.extract_meta(
        url=url,
        title=extracted_title or hint_title or url,
        text=text,
        publisher_hint=rule_publisher,
    )
    tier = refine_tier(
        url,
        url_tier,
        doc_type=meta.doc_type,
        document_id_external=meta.document_id_external,
    )

    root = _text_root(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    text_path = root / f"{doc_id}.txt"
    # newline="\n" explicitly: on Windows the default would rewrite every LF, and
    # every character offset with it.
    text_path.write_text(text, encoding="utf-8", newline="\n")

    document = Document(
        doc_id=doc_id,
        url=url,
        title=meta.title,
        source_tier=tier,
        publisher=meta.publisher,
        doc_type=meta.doc_type,
        document_id_external=meta.document_id_external,
        effective_date=meta.effective_date,
        revision_date=meta.revision_date,
        retrieved_at=datetime.now(UTC),
        text_path=str(text_path),
        paragraph_count=meta.paragraph_count,
        fetch_method=method,  # type: ignore[arg-type]
    )
    _write_sidecar(text_path, document, meta, text)
    if docs is not None:
        docs[doc_id] = document
    return FetchResult(document=document, sections=meta.sections, cached=cached, error=error)


def _write_sidecar(
    text_path: Path, document: Document, meta: docmeta.DocMeta, text: str
) -> None:
    """`<doc_id>.meta.json` (docs/04 §6).

    Carries the paragraph offsets so `within.py` and the UI slice the persisted text
    instead of re-splitting it, the sha1 that proves the two match, and the dates
    docs/02 has no field for (`Revision Ending Date`, `Retirement Date`).
    """
    payload = {
        "document": json.loads(document.model_dump_json()),
        "text_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
        "extra_dates": meta.extra_dates,
        "sections": meta.sections,
        "paragraphs": [
            {
                "index": paragraph.index,
                "char_start": paragraph.char_start,
                "char_end": paragraph.char_end,
                "section": paragraph.section,
                "boilerplate": paragraph.boilerplate,
            }
            for paragraph in meta.paragraphs
        ],
    }
    text_path.with_suffix(".meta.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )

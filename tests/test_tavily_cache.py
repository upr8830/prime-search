"""search/fetch behaviour: the args-keyed cache (docs/04 §6), error handling
(docs/01 §9) and the raw-content fallback (docs/01 §5).

Offline. The Tavily tools are replaced with stubs, so these assert the wiring rather
than the vendor's behaviour; the live checks are in test_primitives_live.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from prime_search.config import get_settings
from prime_search.primitives import docmeta, tavily
from prime_search.schemas import Document

PAGE = "# Policy\n\n" + "\n\n".join(f"Paragraph {i} about coverage of insulin." for i in range(40))
THIN = "# Policy\n\nOnly one paragraph."


@pytest.fixture
def cache_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Real credentials never touch these tests, and the cache is per-test."""
    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-" + "x" * 24)
    monkeypatch.setenv("NEBIUS_API_KEY", "n" * 24)
    monkeypatch.setenv("PRIME_TAVILY_CACHE_DIR", str(tmp_path / "cache"))
    yield tmp_path
    get_settings.cache_clear()


class _StubTool:
    """Counts invocations so a cache hit is provable, not assumed."""

    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls = 0

    def invoke(self, payload: dict[str, Any]) -> Any:
        self.calls += 1
        return self.response() if callable(self.response) else self.response


def _search_response(url: str = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1"):
    return {"results": [{"url": url, "title": "Glucose Monitors", "content": "snippet", "score": 0.9}]}


def _extract_response(text: str):
    return {"results": [{"raw_content": text, "title": "Glucose Monitors"}]}


# --- cache keys ------------------------------------------------------------------


def test_equivalent_calls_share_a_cache_key(cache_env) -> None:
    """Two agents phrasing the same call differently must not pay twice."""
    a = tavily.cache_key_for_search("  Glucose  MONITORS ", include_domains=["CMS.gov", "fda.gov"])
    b = tavily.cache_key_for_search("glucose monitors", include_domains=["fda.gov", "cms.gov"])
    assert a == b


@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_range": "year"},
        {"max_results": 3},
        {"include_domains": ["cms.gov"]},
        {"include_raw_content": True},
    ],
)
def test_response_changing_arguments_change_the_key(cache_env, kwargs) -> None:
    base = tavily.cache_key_for_search("glucose monitors")
    assert tavily.cache_key_for_search("glucose monitors", **kwargs) != base


# --- search ----------------------------------------------------------------------


def test_second_search_is_served_from_cache(cache_env, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _StubTool(_search_response())
    monkeypatch.setattr(tavily, "search_tool", lambda **_: stub)

    first = tavily.search("glucose monitors")
    second = tavily.search("glucose monitors")

    assert (first.cached, second.cached) == (False, True)
    assert stub.calls == 1  # the second call never reached Tavily
    assert second.hits[0].url == first.hits[0].url


def test_cache_can_be_disabled(cache_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRIME_TAVILY_CACHE", "false")
    get_settings.cache_clear()
    stub = _StubTool(_search_response())
    monkeypatch.setattr(tavily, "search_tool", lambda **_: stub)

    tavily.search("glucose monitors")
    tavily.search("glucose monitors")
    assert stub.calls == 2


def test_a_corrupt_cache_entry_is_a_miss_not_a_crash(
    cache_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _StubTool(_search_response())
    monkeypatch.setattr(tavily, "search_tool", lambda **_: stub)
    tavily.search("glucose monitors")
    for entry in Path(get_settings().tavily_cache_dir).glob("*.json"):
        entry.write_text("{not json", encoding="utf-8")

    result = tavily.search("glucose monitors")
    assert result.cached is False and result.hits
    assert stub.calls == 2


@pytest.mark.parametrize(
    "response",
    [
        "No search results found for the query.",  # langchain_tavily's ToolException text
        {"error": "rate limit exceeded"},
    ],
)
def test_tavily_failures_return_an_empty_result_with_error(
    cache_env, monkeypatch: pytest.MonkeyPatch, response
) -> None:
    """docs/01 §9: the primitive returns an empty result with `error` set so the
    sub-agent can retry; it never raises."""
    monkeypatch.setattr(tavily, "search_tool", lambda **_: _StubTool(response))
    result = tavily.search("glucose monitors")
    assert result.hits == []
    assert result.error
    assert result.n_results == 0


def test_search_registers_snippet_only_documents(cache_env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tavily, "search_tool", lambda **_: _StubTool(_search_response()))
    docs: dict[str, Document] = {}
    result = tavily.search("glucose monitors", docs=docs)

    document = docs[result.hits[0].doc_id]
    assert document.fetch_method == "snippet_only"
    assert not document.is_fetched
    assert (document.text_path, document.paragraph_count) == ("", 0)
    assert document.source_tier == "primary_policy"


def test_search_never_downgrades_an_already_fetched_document(
    cache_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(tavily, "search_tool", lambda **_: _StubTool(_search_response()))
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: _StubTool(_extract_response(PAGE)))
    docs: dict[str, Document] = {}
    fetched = tavily.fetch(
        "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1",
        docs=docs,
        run_dir=tmp_path,
    )
    assert fetched.document.is_fetched

    tavily.search("glucose monitors", docs=docs)
    assert docs[fetched.document.doc_id].is_fetched


# --- fetch -----------------------------------------------------------------------


def test_fetch_persists_text_and_a_sidecar(cache_env, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: _StubTool(_extract_response(PAGE)))
    result = tavily.fetch(
        "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1", run_dir=tmp_path
    )
    document = result.document
    text_path = Path(document.text_path)

    assert document.fetch_method == "extract"
    assert text_path.is_file()
    assert text_path.read_text(encoding="utf-8") == docmeta.normalize_text(PAGE)
    sidecar = text_path.with_suffix(".meta.json")
    assert sidecar.is_file()
    assert document.paragraph_count == len(docmeta.split_paragraphs(text_path.read_text("utf-8")))


def test_fetch_is_idempotent_within_a_run(cache_env, monkeypatch, tmp_path: Path) -> None:
    """docs/03 §13: the same document is never fetched twice in one run."""
    stub = _StubTool(_extract_response(PAGE))
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: stub)
    docs: dict[str, Document] = {}
    url = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1"

    first = tavily.fetch(url, docs=docs, run_dir=tmp_path)
    second = tavily.fetch(first.document.doc_id, docs=docs, run_dir=tmp_path)

    assert second.cached is True
    assert stub.calls == 1
    assert second.document.doc_id == first.document.doc_id


def test_a_thin_extract_triggers_the_raw_content_fallback(
    cache_env, monkeypatch, tmp_path: Path
) -> None:
    """docs/11 R2's trigger is a quality threshold, not an error: Extract can succeed
    and still return too little to cite."""
    url = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1"
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: _StubTool(_extract_response(THIN)))
    monkeypatch.setattr(
        tavily,
        "search_tool",
        lambda **_: _StubTool({"results": [{"url": url, "title": "t", "raw_content": PAGE}]}),
    )

    result = tavily.fetch(url, run_dir=tmp_path)
    assert result.document.fetch_method == "raw_content"
    assert result.document.paragraph_count >= tavily.MIN_PARAGRAPHS


def test_the_fallback_rejects_a_different_page_from_the_same_domain(
    cache_env, monkeypatch, tmp_path: Path
) -> None:
    """Accepting a near-miss would leave doc_id pointing at a page the text did not
    come from, and every citation built on it would be wrong."""
    url = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1"
    other = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=999"
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: _StubTool(_extract_response(THIN)))
    monkeypatch.setattr(
        tavily,
        "search_tool",
        lambda **_: _StubTool({"results": [{"url": other, "title": "t", "raw_content": PAGE}]}),
    )

    result = tavily.fetch(url, run_dir=tmp_path)
    assert result.document.fetch_method == "extract"  # kept the thin text, did not lie
    assert "did not improve" in (result.error or "")  # the R2 trigger is surfaced
    assert "no exact match" in (result.error or "")


def test_fetch_of_an_unknown_doc_id_names_the_fix(cache_env) -> None:
    with pytest.raises(ValueError, match="search first, or pass the URL"):
        tavily.fetch("doc_deadbeef00", docs={})


def test_fetch_with_no_text_stays_a_snippet_and_reports_the_error(
    cache_env, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: _StubTool({"results": []}))
    monkeypatch.setattr(tavily, "search_tool", lambda **_: _StubTool({"results": []}))
    result = tavily.fetch("https://example.gov/missing", run_dir=tmp_path)
    assert result.document.fetch_method == "snippet_only"
    assert result.error


def test_event_payloads_match_the_sse_contract(cache_env, monkeypatch, tmp_path: Path) -> None:
    """docs/02 §4's `search` and `fetch` events."""
    monkeypatch.setattr(tavily, "search_tool", lambda **_: _StubTool(_search_response()))
    monkeypatch.setattr(tavily, "extract_tool", lambda **_: _StubTool(_extract_response(PAGE)))

    search_event = tavily.search("glucose monitors").event("t1")
    assert set(search_event) == {"task_id", "query", "n_results", "cached"}

    fetch_event = tavily.fetch(
        "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=1", run_dir=tmp_path
    ).event("t1")
    assert set(fetch_event) == {"task_id", "doc_id", "url", "title", "tier", "effective_date"}

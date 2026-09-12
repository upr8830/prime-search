"""Shared fixtures. Tests marked `live` need real keys; skip them when absent so a
reviewer without credentials can still run `make test` (docs/11 R8)."""

from __future__ import annotations

import os

import pytest

_LIVE_KEYS = ("TAVILY_API_KEY", "NEBIUS_API_KEY")


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("live"):
        missing = [k for k in _LIVE_KEYS if not os.getenv(k)]
        if missing:
            pytest.skip(f"live test needs {', '.join(missing)}")


@pytest.fixture
def offline_credentials(monkeypatch: pytest.MonkeyPatch):
    """Dummy credentials for offline tests that construct a client or tool.

    get_settings() is lru_cached, so the cache is cleared on both sides to keep a
    fake key from leaking into another test — or a real one into this one.
    """
    from prime_search.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-" + "x" * 24)
    monkeypatch.setenv("NEBIUS_API_KEY", "n" * 24)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    yield
    get_settings.cache_clear()

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

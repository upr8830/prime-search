"""Task 1.1 acceptance: the package installs, the console script resolves, and
secret redaction works (docs/01 §7, §8).

The fake keys below are built by concatenation on purpose: a literal key-shaped
string in a tracked file would be blocked by .claude/hooks/guard-commit.sh.
"""

from __future__ import annotations

from importlib.metadata import entry_points, version

import prime_search
from prime_search.tracing import REDACTED, redact_secrets

FAKE_TAVILY = "tvly-" + "A" * 32
FAKE_LANGSMITH = "lsv2_" + "b" * 36


def test_version_matches_installed_distribution() -> None:
    """Catches a stale or broken editable install, and version drift."""
    assert prime_search.__version__ == version("prime-search")


def test_console_script_entry_point_resolves() -> None:
    """`[project.scripts] prime-search = "prime_search.cli:app"` is the 1.1 deliverable."""
    (script,) = [
        ep for ep in entry_points(group="console_scripts") if ep.name == "prime-search"
    ]
    assert script.value == "prime_search.cli:app"
    assert callable(script.load())


def test_redact_secrets_masks_key_shaped_values() -> None:
    out = redact_secrets(None, "info", {"url": f"https://x/?k={FAKE_TAVILY}"})
    assert FAKE_TAVILY not in out["url"]
    assert REDACTED in out["url"]

    nested = redact_secrets(None, "info", {"payload": {"trace": [FAKE_LANGSMITH]}})
    assert nested["payload"]["trace"] == [REDACTED]


def test_redact_secrets_masks_key_shaped_field_names() -> None:
    out = redact_secrets(
        None,
        "info",
        {"tavily_api_key": FAKE_TAVILY, "Authorization": "Bearer abc", "query": "cgm"},
    )
    assert out["tavily_api_key"] == REDACTED
    assert out["Authorization"] == REDACTED
    assert out["query"] == "cgm"  # non-secret fields survive untouched

"""Task 1.2: Settings resolves credentials and overrides as docs/01 §3 specifies.

docs/01 §3 asks for two things a single env_prefix cannot give: unprefixed
credentials in .env.example, and PRIME_MODELS__ROOT-style overrides. These tests
pin both halves so a later refactor cannot quietly break one of them.

_env_file=None everywhere: the real .env must not leak into a unit test.
"""

from __future__ import annotations

import pytest

from prime_search.config import Budget, ModelRouting, Settings


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key in (
        "TAVILY_API_KEY",
        "NEBIUS_API_KEY",
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
        "PRIME_TAVILY_API_KEY",
        "PRIME_NEBIUS_API_KEY",
        "PRIME_MODELS__ROOT",
        "PRIME_BUDGET_DEEP__MAX_SEARCHES",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-" + "t" * 20)
    monkeypatch.setenv("NEBIUS_API_KEY", "n" * 20)
    return monkeypatch


def test_unprefixed_credentials_are_read(env: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None)
    assert settings.tavily_api_key.startswith("tvly-")
    assert settings.langsmith_api_key is None  # optional
    assert settings.langsmith_project == "prime-search"


def test_prefixed_credential_wins_over_unprefixed(env: pytest.MonkeyPatch) -> None:
    env.setenv("PRIME_TAVILY_API_KEY", "tvly-" + "p" * 20)
    settings = Settings(_env_file=None)
    assert settings.tavily_api_key == "tvly-" + "p" * 20


def test_nested_model_override(env: pytest.MonkeyPatch) -> None:
    """The PRIME_MODELS__ROOT form docs/01 §4 documents for applying a fallback."""
    env.setenv("PRIME_MODELS__ROOT", "deepseek-ai/DeepSeek-R1-0528")
    settings = Settings(_env_file=None)
    assert settings.models.root == "deepseek-ai/DeepSeek-R1-0528"
    assert settings.models.subagent == ModelRouting().subagent  # others untouched


def test_nested_budget_override(env: pytest.MonkeyPatch) -> None:
    env.setenv("PRIME_BUDGET_DEEP__MAX_SEARCHES", "7")
    settings = Settings(_env_file=None)
    assert settings.budget_deep.max_searches == 7


def test_missing_required_key_names_the_field(env: pytest.MonkeyPatch) -> None:
    env.delenv("NEBIUS_API_KEY")
    with pytest.raises(Exception, match="nebius_api_key|NEBIUS_API_KEY"):
        Settings(_env_file=None)


def test_budget_defaults_match_spec(env: pytest.MonkeyPatch) -> None:
    """docs/01 §3. budget_fast overrides five fields and inherits the rest."""
    settings = Settings(_env_file=None)
    assert (settings.budget_deep.max_searches, settings.budget_deep.max_seconds) == (30, 180)
    assert settings.budget_fast.max_searches == 3
    assert settings.budget_fast.max_seconds == 30
    assert settings.budget_fast.max_deep_reads == Budget().max_deep_reads  # inherited
    assert settings.budget("fast") is settings.budget_fast
    assert settings.budget("deep") is settings.budget_deep


def test_export_sdk_env_does_not_clobber_a_real_shell_value(env: pytest.MonkeyPatch) -> None:
    """The langsmith SDK reads os.environ directly, so .env values are pushed out —
    but a value already in the environment must win."""
    import os

    env.setenv("LANGSMITH_PROJECT", "already-set")
    settings = Settings(_env_file=None)
    settings.export_sdk_env()
    assert os.environ["LANGSMITH_PROJECT"] == "already-set"
    assert os.environ["NEBIUS_API_KEY"] == "n" * 20


# --- unknown PRIME_ overrides ------------------------------------------------------


def test_a_mistyped_override_is_reported_with_the_name_it_meant(env: pytest.MonkeyPatch) -> None:
    """`extra="ignore"` drops an unrecognized override in silence, which is how
    PRIME_MODELS__SUB sat in a .env doing nothing while looking deliberate."""
    from prime_search.config import unknown_overrides

    env.setenv("PRIME_MODELS__SUB", "moonshotai/Kimi-K2.6")
    found = unknown_overrides()
    assert found["PRIME_MODELS__SUB"] == "PRIME_MODELS__SUBAGENT"


def test_valid_overrides_are_not_reported(env: pytest.MonkeyPatch) -> None:
    from prime_search.config import unknown_overrides

    env.setenv("PRIME_MODELS__SUBAGENT", "x")
    env.setenv("PRIME_BUDGET_DEEP__MAX_SEARCHES", "7")
    env.setenv("PRIME_TAVILY_CACHE", "false")
    assert unknown_overrides() == {}


def test_get_settings_warns_rather_than_raising(env: pytest.MonkeyPatch) -> None:
    """A stale variable in someone's shell should not stop a run, but it must not be
    invisible either."""
    import warnings

    from prime_search.config import get_settings

    get_settings.cache_clear()
    env.setenv("PRIME_MODELS__SUB", "moonshotai/Kimi-K2.6")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = get_settings()
        assert settings.models.subagent == ModelRouting().subagent  # override had no effect
        assert any("PRIME_MODELS__SUBAGENT" in str(w.message) for w in caught)
    finally:
        get_settings.cache_clear()

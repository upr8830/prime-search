"""Where the API listens (docs/01 §2): `ServerSettings` and `python -m prime_search.api`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prime_search.api import __main__ as server_main
from prime_search.config import ServerSettings, unknown_overrides


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("PRIME_API_HOST", "PRIME_API_PORT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_the_default_is_localhost_8765_without_any_keys(clean_env) -> None:
    # No TAVILY/NEBIUS keys needed: the API must start and serve past runs without them.
    settings = ServerSettings(_env_file=None)
    assert (settings.api_host, settings.api_port) == ("127.0.0.1", 8765)


def test_the_port_is_configurable_and_validated(clean_env) -> None:
    clean_env.setenv("PRIME_API_PORT", "9123")
    assert ServerSettings(_env_file=None).api_port == 9123
    clean_env.setenv("PRIME_API_PORT", "70000")
    with pytest.raises(ValidationError):
        ServerSettings(_env_file=None)


def test_the_server_variables_are_not_reported_as_typos() -> None:
    assert unknown_overrides({"PRIME_API_PORT": "8765", "PRIME_API_HOST": "127.0.0.1"}) == {}
    assert unknown_overrides({"PRIME_API_PROT": "8765"}) == {"PRIME_API_PROT": "PRIME_API_PORT"}


def test_python_m_prime_search_api_uses_the_setting_and_a_flag_overrides_it(clean_env, monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(server_main.uvicorn, "run", lambda app, **kwargs: calls.append({"app": app, **kwargs}))
    monkeypatch.setattr(server_main, "ServerSettings", lambda: ServerSettings(_env_file=None))

    clean_env.setenv("PRIME_API_PORT", "9200")
    server_main.main([])
    server_main.main(["--port", "9300", "--reload"])

    assert calls[0] == {"app": "prime_search.api.main:app", "host": "127.0.0.1", "port": 9200, "reload": False}
    assert (calls[1]["port"], calls[1]["reload"]) == (9300, True)

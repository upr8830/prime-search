"""Shared fixtures. Tests marked `live` need real keys; skip them when absent so a
reviewer without credentials can still run `make test` (docs/11 R8)."""

from __future__ import annotations

import os

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

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


class ScriptedChatModel(BaseChatModel):
    """A chat model that returns a scripted list of AIMessages.

    `create_agent` needs a real BaseChatModel — it calls `bind_tools` and then
    `invoke`. Both are satisfied here without a network call, so the agent loop, the
    tool-call cap, the rejection path and TaskResult assembly are all testable
    offline. `seen` keeps every message list the agent built, which is how a test
    asserts what a tool actually put in front of the model.
    """

    script: list[AIMessage] = []
    seen: list[list[BaseMessage]] = []
    bound_tools: list[str] = []
    exhausted: str = "No more scripted turns."

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # type: ignore[no-untyped-def]
        # create_agent binds on every request; returning self rather than a
        # RunnableBinding keeps `script`/`seen` on the one object the test holds.
        self.bound_tools = [getattr(t, "name", str(t)) for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
        self.seen.append(list(messages))
        message = self.script.pop(0) if self.script else AIMessage(content=self.exhausted)
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call(name: str, **args) -> dict:
    """One tool call for a scripted AIMessage; ids only need to be unique."""
    tool_call.n = getattr(tool_call, "n", 0) + 1  # type: ignore[attr-defined]
    return {"name": name, "args": args, "id": f"call_{tool_call.n}", "type": "tool_call"}  # type: ignore[attr-defined]


@pytest.fixture
def sandboxed_run(tmp_path, offline_credentials, monkeypatch):
    """A workspace whose documents and events live under tmp_path.

    PRIME_TAVILY_CACHE_DIR matters more than it looks: Workspace._assert_readable
    only reads documents under the Tavily cache dir or ./runs, so a fixture document
    written anywhere else makes search_within refuse.
    """
    from prime_search import events
    from prime_search.config import get_settings
    from prime_search.workspace import Workspace

    monkeypatch.setenv("PRIME_TAVILY_CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    events.set_runs_root(tmp_path / "runs")
    try:
        yield Workspace(objective="test objective")
    finally:
        events.set_runs_root("runs")
        get_settings.cache_clear()

"""The docs/01 §4 rule-3 ladder in models.structured().

This is the code path that catches Kimi-K2.6 returning None from
with_structured_output (measured 3 of 20 identical calls on 2026-09-12). It only
runs when the model misbehaves, so a live smoke run usually answers "via native"
and never exercises it — hence a stub model here.
"""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from prime_search import models
from prime_search.schemas import Verdict

VALID = {
    "round": 1,
    "sufficient": False,
    "coverage": {"b1": "unresolved"},
    "missing": ["the LCD coverage criteria"],
    "reasoning": "nothing has been searched yet",
}


class _StubStructured:
    def __init__(self, results: list[object]) -> None:
        self._results = results

    def invoke(self, _prompt: str) -> object:
        return self._results.pop(0) if self._results else None


class _StubModel:
    """Stands in for a ChatNebius. `native` is the queue of with_structured_output
    results; `text` is what a plain invoke returns for the fenced rung."""

    def __init__(self, native: list[object], text: str = "") -> None:
        self.native = native
        self.text = text
        self.plain_invocations = 0
        self.structured_invocations = 0

    def with_structured_output(self, _schema: type) -> _StubStructured:
        self.structured_invocations += 1
        return _StubStructured(self.native)

    def invoke(self, prompt: str) -> AIMessage:
        self.plain_invocations += 1
        self.last_prompt = prompt
        return AIMessage(content=self.text)


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch):
    def _install(native: list[object], text: str = "") -> _StubModel:
        model = _StubModel(native, text)
        monkeypatch.setattr(models, "_build", lambda role, **kw: model)
        return model

    return _install


def test_native_success_is_the_first_rung(stub) -> None:
    model = stub([Verdict(**VALID)])
    caller = models.structured("judge", Verdict)
    assert caller.invoke("judge this").sufficient is False
    assert caller.last_mode == "native"
    assert model.plain_invocations == 0  # the fenced rung was never needed


def test_a_single_none_is_repaired_by_the_retry(stub) -> None:
    """docs/01 §9 allows one repair attempt with the same model."""
    stub([None, Verdict(**VALID)])
    caller = models.structured("judge", Verdict)
    assert isinstance(caller.invoke("judge this"), Verdict)
    assert caller.last_mode == "native_retry_1"


def test_persistent_none_falls_through_to_fenced_json(stub) -> None:
    model = stub([None, None], text=f"here you go\n```json\n{json.dumps(VALID)}\n```")
    caller = models.structured("judge", Verdict)
    verdict = caller.invoke("judge this")
    assert verdict.coverage == {"b1": "unresolved"}
    assert caller.last_mode == "fenced_json"
    assert model.plain_invocations == 1
    # The fenced rung must send the schema, and from the prompt file (CLAUDE.md).
    assert "JSON Schema" in model.last_prompt
    assert '"sufficient"' in model.last_prompt


def test_an_exception_skips_straight_to_the_fenced_rung(stub) -> None:
    """A bad key or missing model is not flakiness: do not burn retries on it."""

    class _Boom:
        def invoke(self, _prompt: str) -> object:
            raise RuntimeError("401 unauthorized")

    model = stub([], text=f"```json\n{json.dumps(VALID)}\n```")
    model.with_structured_output = lambda _schema: _Boom()  # type: ignore[method-assign]
    caller = models.structured("judge", Verdict, attempts=5)
    assert isinstance(caller.invoke("judge this"), Verdict)
    assert caller.last_mode == "fenced_json"
    assert model.plain_invocations == 1


def test_both_rungs_failing_raises_and_names_the_role(stub) -> None:
    """The third rung of rule 3 (switch models) is deliberately a human decision,
    so exhausting the ladder must surface rather than silently swap."""
    stub([None, None], text="I cannot help with that.")
    caller = models.structured("judge", Verdict)
    with pytest.raises(RuntimeError, match="judge: structured output failed in both modes"):
        caller.invoke("judge this")


def test_schema_violating_json_is_rejected_not_coerced(stub) -> None:
    stub([None, None], text='```json\n{"round": "not-an-int"}\n```')
    caller = models.structured("judge", Verdict)
    with pytest.raises(RuntimeError, match="ValidationError"):
        caller.invoke("judge this")

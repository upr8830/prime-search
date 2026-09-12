"""Task 1.2: the two guarantees models.py makes to its callers (docs/01 §4).

Offline. The live per-role probes are `make smoke`.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_nebius import ChatNebius

from prime_search.models import (
    FALLBACKS,
    ReasoningNormalizedChatNebius,
    _reasoning_text,
    parse_fenced_json,
)


@pytest.fixture
def normalize(monkeypatch: pytest.MonkeyPatch):
    """Run a canned AIMessage through the real ReasoningNormalizedChatNebius
    override by stubbing only what the parent class would have parsed."""

    def _normalize(message: AIMessage) -> AIMessage:
        monkeypatch.setattr(
            ChatNebius,
            "_create_chat_result",
            lambda self, response, generation_info=None: ChatResult(
                generations=[ChatGeneration(message=message)]
            ),
        )
        model = ReasoningNormalizedChatNebius(model="x", api_key="k")
        return model._create_chat_result({}).generations[0].message  # type: ignore[return-value]

    return _normalize


def test_reasoning_content_is_promoted_when_content_is_empty(normalize) -> None:
    """docs/11 A12: a reasoning model may answer in reasoning_content."""
    out = normalize(
        AIMessage(content="", additional_kwargs={"reasoning_content": "```python\nx=1\n```"})
    )
    assert "```python" in out.text
    assert out.additional_kwargs["reasoning_normalized"] is True


def test_existing_content_is_never_overwritten(normalize) -> None:
    out = normalize(
        AIMessage(content="real answer", additional_kwargs={"reasoning_content": "scratch work"})
    )
    assert out.text == "real answer"
    assert "reasoning_normalized" not in out.additional_kwargs


def test_reasoning_text_reads_nested_and_alternate_keys() -> None:
    assert _reasoning_text(AIMessage(content="", additional_kwargs={"reasoning": "a"})) == "a"
    assert (
        _reasoning_text(AIMessage(content="", additional_kwargs={"reasoning": {"content": "b"}}))
        == "b"
    )
    assert _reasoning_text(AIMessage(content="", additional_kwargs={"reasoning": "   "})) is None
    assert _reasoning_text(AIMessage(content="")) is None


@pytest.mark.parametrize(
    "text",
    [
        '```json\n{"sufficient": false}\n```',
        'prose before\n```\n{"sufficient": false}\n```\nprose after',
        '{"sufficient": false}',
    ],
)
def test_parse_fenced_json_accepts_the_shapes_models_emit(text: str) -> None:
    assert parse_fenced_json(text) == {"sufficient": False}


def test_parse_fenced_json_rejects_empty_output() -> None:
    with pytest.raises(ValueError, match="no JSON"):
        parse_fenced_json("")


def test_root_falls_back_to_a_tool_calling_model_not_the_generic_fallback() -> None:
    """docs/01 §4: DeepSeek-V3.2 is the fallback for non-root roles; root, being a
    reasoning role, falls back to the starter's known-good model."""
    assert FALLBACKS["root"] == "moonshotai/Kimi-K2.6"
    assert FALLBACKS["critic"] == "moonshotai/Kimi-K2.6"
    assert FALLBACKS["subagent"] == "deepseek-ai/DeepSeek-V3.2"

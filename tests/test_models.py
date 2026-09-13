"""Task 1.2: the two guarantees models.py makes to its callers (docs/01 §4).

Offline. The live per-role probes are `make smoke`.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_nebius import ChatNebius

from prime_search.config import ModelRouting
from prime_search.models import (
    fallback_model,
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


def test_fallback_table_departs_from_the_spec_only_where_the_model_is_gone() -> None:
    """docs/01 §4 sends root to Kimi-K2.6 (rule 1) and every other role to
    DeepSeek-V3.2 — but Nebius no longer offers V3.2 or R1-0528, so those five
    entries would have raised model-not-found the moment a role needed rescuing.
    They point at the V4 line now, each chosen on a measured result for that role's
    own call shape (reports/model-selection.md).

    `test_every_routed_model_exists_in_the_live_catalog` (live) is the guard that
    catches the next such disappearance.
    """
    assert FALLBACKS["root"] == "moonshotai/Kimi-K2.6"  # still offered, 5/5 measured
    assert "deepseek-ai/DeepSeek-V3.2" not in FALLBACKS.values()
    assert FALLBACKS["critic"] == "deepseek-ai/DeepSeek-V4-Pro"  # 3/3 fenced JSON
    for role in ("subagent", "extractor", "evaluator"):
        assert FALLBACKS[role] == "deepseek-ai/DeepSeek-V4-Flash-0731"
    # The judge moved to V4-Flash on 2026-09-13, so its fallback is the report's
    # runner-up on structured output (3/3 valid Verdict, 1.9s).
    assert FALLBACKS["judge"] == "Qwen/Qwen3-30B-A3B-Instruct-2507"
    # Every fallback is a different vendor line from its role's primary, so one
    # vendor's outage cannot take a role and its fallback down together.
    routing = ModelRouting()
    for role, fallback in FALLBACKS.items():
        assert fallback.split("/")[0] != getattr(routing, role).split("/")[0]


def test_baseline_has_no_fallback() -> None:
    """docs/01 §3 marks the baseline model "do not change" and CLAUDE.md rests the
    whole comparison on baseline parity, so switching it must be impossible, not
    merely discouraged."""
    assert "baseline" not in FALLBACKS
    with pytest.raises(ValueError, match="no fallback model"):
        fallback_model("baseline")


@pytest.mark.live
def test_every_routed_model_exists_in_the_live_catalog() -> None:
    """docs/01 §4's fallbacks named deepseek-ai/DeepSeek-V3.2, which Nebius no longer
    offers — so every fallback would have raised model-not-found the first time one
    was needed. This is the check that would have caught it.

        uv run --env-file .env pytest tests/test_models.py -m live
    """
    import httpx

    from prime_search.config import get_settings

    settings = get_settings()
    response = httpx.get(
        "https://api.studio.nebius.ai/v1/models",
        headers={"Authorization": f"Bearer {settings.nebius_api_key}"},
        timeout=60,
    )
    response.raise_for_status()
    offered = {model["id"] for model in response.json()["data"]}

    routed = {role: getattr(settings.models, role) for role in ModelRouting.model_fields}
    missing = {
        **{f"models.{role}": model for role, model in routed.items() if model not in offered},
        **{f"FALLBACKS[{role}]": m for role, m in FALLBACKS.items() if m not in offered},
    }
    assert not missing, f"models routed to ids Nebius does not offer: {missing}"

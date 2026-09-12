"""ChatNebius factories, one per role (docs/01 §4).

This is the only module in the project that constructs a ChatNebius (CLAUDE.md).

Two things every caller can rely on:

* **Text is always in `content`.** Reasoning models on the Nebius endpoint may put
  the answer in `reasoning_content` and leave `content` empty (docs/11 A12). The
  subclass below moves it, so the root planner and critic can parse fenced blocks
  out of `content` without knowing which model answered.
* **Roles are indirected through config.** `PRIME_MODELS__ROOT=...` repoints a role
  without a code change, which is how a `make smoke` fallback is applied.
"""

from __future__ import annotations

import json
import re
from typing import Any, Generic, Literal, TypeVar

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_nebius import ChatNebius
from pydantic import BaseModel

from prime_search.config import Settings, get_settings
from prime_search.prompts import render

Role = Literal["root", "critic", "subagent", "judge", "extractor", "evaluator", "baseline"]
_S = TypeVar("_S", bound=BaseModel)

# docs/01 §4 names `deepseek-ai/DeepSeek-V3.2` as the fallback for every non-root
# role. **That model is no longer offered** — the live catalog moved to the V4 line
# (checked 2026-09-12), so those five entries would have raised model-not-found the
# first time anything needed them: a dead switch in the mechanism meant to rescue a
# failing role. Replacements are the V4 models measured on each role's own call shape
# in reports/model-selection.md, not picked from a leaderboard:
#
#   critic     V4-Pro    3/3 parseable fenced JSON, 2.5s
#   subagent   V4-Flash  5/5 native tool calls, 1.7s
#   judge etc. V4-Flash  3/3 valid Verdict from with_structured_output
#
# Root keeps rule 1's Kimi-K2.6, which is still offered and went 5/5 on code-as-action.
# Each fallback is a different vendor line from the role's primary, so one vendor's
# outage cannot take both down.
#
# `baseline` is deliberately absent: docs/01 §3 marks it "starter default; do not
# change", and baseline parity is what the whole comparison rests on (CLAUDE.md).
# A baseline that silently switched models would invalidate every bench row.
FALLBACKS: dict[Role, str] = {
    "root": "moonshotai/Kimi-K2.6",
    "critic": "deepseek-ai/DeepSeek-V4-Pro",
    "subagent": "deepseek-ai/DeepSeek-V4-Flash-0731",
    "judge": "deepseek-ai/DeepSeek-V4-Flash-0731",
    "extractor": "deepseek-ai/DeepSeek-V4-Flash-0731",
    "evaluator": "deepseek-ai/DeepSeek-V4-Flash-0731",
}

# Keys a reasoning model may use for out-of-band reasoning text, in priority order.
_REASONING_KEYS = ("reasoning_content", "reasoning")


def _reasoning_text(message: AIMessage) -> str | None:
    for source in (message.additional_kwargs, message.response_metadata):
        for key in _REASONING_KEYS:
            value = source.get(key) if isinstance(source, dict) else None
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):  # e.g. {"content": "..."}
                inner = value.get("content")
                if isinstance(inner, str) and inner.strip():
                    return inner
    return None


class ReasoningNormalizedChatNebius(ChatNebius):
    """ChatNebius that guarantees non-empty `content` when the model emitted
    reasoning text instead (docs/01 §4, docs/11 A12).

    The original text stays in `additional_kwargs['reasoning_content']`, so nothing
    is lost and the UI can still show the reasoning separately.
    """

    def _create_chat_result(self, response: Any, generation_info: dict | None = None) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        for generation in result.generations:
            message = generation.message
            if not isinstance(message, AIMessage) or not isinstance(generation, ChatGeneration):
                continue
            if message.text:
                continue
            recovered = _reasoning_text(message)
            if recovered:
                message.content = recovered
                message.additional_kwargs.setdefault("reasoning_normalized", True)
        return result

    def _convert_chunk_to_generation_chunk(
        self, chunk: dict, default_chunk_class: type, base_generation_info: dict | None
    ) -> Any:
        """Same guarantee on the streaming path.

        docs/01 §4 says callers *always* get text in `content`, and task 1.7 streams
        the answer to the console and over SSE. Without this, a reasoning model's
        stream would deliver empty content chunks and the fenced-block parsers would
        see nothing.
        """
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if generation_chunk is None:
            return None
        message = generation_chunk.message
        if not message.text:
            recovered = _reasoning_text(message)
            if recovered:
                message.content = recovered
                message.additional_kwargs.setdefault("reasoning_normalized", True)
        return generation_chunk


def _build(role: Role, settings: Settings | None = None, **overrides: Any) -> ChatNebius:
    settings = settings or get_settings()
    model = getattr(settings.models, role)
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": settings.nebius_api_key,
        # Deterministic by default so bench re-runs are comparable (docs/00 FR-16).
        # The baseline keeps the provider default to stay starter-equivalent.
        "temperature": None if role == "baseline" else 0.0,
        "max_retries": 2,
        "timeout": 120,
    }
    kwargs.update(overrides)
    return ReasoningNormalizedChatNebius(**{k: v for k, v in kwargs.items() if v is not None})


_FENCE = re.compile(r"```(?:json)?\s*\n(.+?)```", re.DOTALL)


def parse_fenced_json(text: str) -> Any:
    """Parse the first fenced JSON block in `text`, else the whole string.

    The code-as-action path (docs/01 §4, docs/03 §3, §7): models that cannot be
    relied on for native structured output still emit parseable fenced JSON.
    """
    block = _FENCE.search(text or "")
    payload = (block.group(1) if block else text or "").strip()
    if not payload:
        raise ValueError("no JSON found in model output")
    return json.loads(payload)


class StructuredCaller(Generic[_S]):
    """Structured output with the docs/01 §4 rule-3 ladder.

    1. Native `with_structured_output`, with `attempts` tries. Kimi-K2.6 returns
       None on roughly 15% of calls (measured over 20 identical calls, 2026-09-12),
       which a single repair attempt clears; docs/01 §9 allows "one repair attempt
       with the same model", so the default is 2, not an unbounded retry.
    2. Fenced JSON from the same model, parsed by the harness.

    An *exception* (bad key, model not found, timeout) is not flakiness, so it does
    not consume further native attempts — it drops straight to the fenced rung and,
    failing that, surfaces. Retrying a bad API key three times just costs round
    trips.

    docs/01 §4 rule 3 has a third rung, "then fallback model". It is deliberately
    not automatic: KICKOFF_PROMPT requires asking a human before applying a model
    fallback, so both rungs failing raises and the human decides. `last_mode`
    records which rung answered, so smoke output and traces show when the ladder
    was used.
    """

    def __init__(self, role: Role, schema: type[_S], *, attempts: int = 2) -> None:
        self.role = role
        self.schema = schema
        self.attempts = attempts
        self.last_mode: str = "unused"

    def invoke(self, prompt: str) -> _S:
        model = _build(self.role)
        errors: list[str] = []
        for attempt in range(self.attempts):
            try:
                result = model.with_structured_output(self.schema).invoke(prompt)
                if isinstance(result, self.schema):
                    self.last_mode = "native" if attempt == 0 else f"native_retry_{attempt}"
                    return result
                errors.append(f"attempt {attempt}: returned {type(result).__name__}")
            except Exception as exc:
                errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                break  # not flakiness; go straight to the fenced rung

        message = model.invoke(
            render(
                "fenced_json",
                prompt=prompt,
                schema=json.dumps(self.schema.model_json_schema(), indent=2),
            )
        )
        try:
            value = self.schema.model_validate(parse_fenced_json(message.text))
        except Exception as exc:
            raise RuntimeError(
                f"{self.role}: structured output failed in both modes "
                f"({'; '.join(errors)}); fenced JSON: {type(exc).__name__}: {exc}"
            ) from exc
        self.last_mode = "fenced_json"
        return value


def structured(role: Role, schema: type[_S], *, attempts: int = 2) -> StructuredCaller[_S]:
    """Structured output for a role, with the docs/01 §4 rule-3 fallback ladder."""
    return StructuredCaller(role, schema, attempts=attempts)


def model_for(role: Role, **overrides: Any) -> ChatNebius:
    """The model for a role by name. The per-role factories below are the normal
    entry points; this exists for code that iterates roles, such as `make smoke`."""
    return _build(role, **overrides)


def root_model(**overrides: Any) -> ChatNebius:
    """Planner. Emits fenced Python (code-as-action), never native tool calls."""
    return _build("root", **overrides)


def critic_model(**overrides: Any) -> ChatNebius:
    """Critic. Emits fenced JSON (code-as-action), never native tool calls."""
    return _build("critic", **overrides)


def subagent_model(**overrides: Any) -> ChatNebius:
    """Search sub-agent. Needs working native tool calling."""
    return _build("subagent", **overrides)


def judge_model(**overrides: Any) -> ChatNebius:
    """Sufficiency judge. Needs with_structured_output(Verdict)."""
    return _build("judge", **overrides)


def extractor_model(**overrides: Any) -> ChatNebius:
    """Evidence extraction over selected paragraphs."""
    return _build("extractor", **overrides)


def evaluator_model(**overrides: Any) -> ChatNebius:
    """LLM-judge evaluators in the bench (docs/05 §2)."""
    return _build("evaluator", **overrides)


def baseline_model(**overrides: Any) -> ChatNebius:
    """Starter-equivalent model. Configuration must match starter_agent.py (docs/03 §8)."""
    return _build("baseline", **overrides)


def fallback_model(role: Role, **overrides: Any) -> ChatNebius:
    """The docs/01 §4 fallback for a role, for use when `make smoke` fails it.

    Raises for `baseline`, which has no fallback: it must stay starter-equivalent.
    """
    if role not in FALLBACKS:
        raise ValueError(
            f"{role!r} has no fallback model: docs/01 §3 marks the baseline model "
            "'do not change', and baseline parity is what the comparison rests on"
        )
    return _build(role, model=FALLBACKS[role], **overrides)

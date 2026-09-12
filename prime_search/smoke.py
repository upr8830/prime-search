"""`make smoke` — the task 1.2 gate (docs/01 §4 fallback rule, docs/09 §1.2).

Probes each model role with the *exact call shape that role uses in production*,
plus one Tavily search, one Tavily extract on the CGM LCD, and one LangSmith trace.
Each role prints PASS, or FALLBACK with the model it would switch to.

A FALLBACK is a finding, not a fix: applying it means repointing the role in
config (or PRIME_MODELS__<ROLE>) and recording the change in the docs/11 decision
log. Nothing here mutates configuration.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from prime_search.config import get_settings
from prime_search.models import FALLBACKS, Role, model_for, parse_fenced_json, structured
from prime_search.primitives.tavily import CGM_LCD_URL, PRIMARY_DOMAINS, extract_tool, search_tool
from prime_search.prompts import render
from prime_search.tracing import trace_run
from prime_search.schemas import Verdict

FENCED_PYTHON = re.compile(r"```(?:python)?\s*\n(.+?)```", re.DOTALL)

PLAN_QUESTION = (
    "Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
)
TOOL_QUESTION = (
    "What are the current Medicare LCD coverage criteria for therapeutic continuous "
    "glucose monitors? Search for the primary source."
)

# Collected during the run and printed under the table by cli.py.
_TRACE_URLS: list[str] = []


@dataclass
class Probe:
    """One smoke check. `role` is set for model probes, None for service probes."""

    name: str
    role: Role | None = None
    status: str = "PENDING"
    detail: str = ""
    seconds: float = 0.0
    url: str | None = None  # rendered under the table: URLs do not fold readably

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


def _run(probe: Probe, check: Callable[[], str]) -> Probe:
    started = time.monotonic()
    try:
        probe.detail = check()
        probe.status = "PASS"
    except Exception as exc:  # a probe failure is data, not a crash
        fallback = FALLBACKS.get(probe.role) if probe.role else None
        # No fallback exists for `baseline` (starter parity), so a baseline failure
        # is a hard FAIL that needs a human, not a switchable role.
        probe.status = "FALLBACK" if fallback else "FAIL"
        suffix = f" -> would switch to {fallback}" if fallback else ""
        probe.detail = f"{type(exc).__name__}: {str(exc)[:200]}{suffix}"
    probe.seconds = time.monotonic() - started
    return probe


# --------------------------------------------------------------------------- probes


def _probe_code_as_action(role: Role) -> str:
    """Rule 1: planning prompt must yield a fenced Python block in `content`.

    Covers root and critic, the two code-as-action roles: neither may depend on
    native tool calling (docs/01 §4).
    """
    model = model_for(role)
    message = model.invoke(render("smoke_plan", question=PLAN_QUESTION))
    text = message.text
    normalized = message.additional_kwargs.get("reasoning_normalized")
    block = FENCED_PYTHON.search(text or "")
    if not block:
        raise AssertionError(
            f"no fenced python block in content (len={len(text or '')}, "
            f"keys={sorted(message.additional_kwargs)[:5]})"
        )
    body = block.group(1).strip().splitlines()
    return (
        f"fenced python block, {len(body)} lines"
        + (", recovered from reasoning_content" if normalized else "")
    )


def _probe_fenced_json(role: Role) -> str:
    """The critic's production shape: fenced *JSON* in plain text (docs/01 §4).

    Deliberately not the same probe as root's. Root emits fenced Python and critic
    fenced JSON, so a shared probe would pass a model that could produce one and
    not the other.
    """
    model = model_for(role)
    message = model.invoke(render("smoke_critic", draft="Therapeutic CGMs are always covered."))
    payload = parse_fenced_json(message.text)  # raises if the block is absent or invalid
    if not isinstance(payload, dict):
        raise AssertionError(f"expected a JSON object, got {type(payload).__name__}")
    normalized = message.additional_kwargs.get("reasoning_normalized")
    return (
        f"fenced json object, keys={sorted(payload)[:4]}"
        + (", recovered from reasoning_content" if normalized else "")
    )


def _probe_native_tool_call(role: Role) -> str:
    """Rule 2: sub-agent must emit a native tool call on a search-needing question."""
    model = model_for(role).bind_tools([search_tool(include_domains=PRIMARY_DOMAINS)])
    message = model.invoke(TOOL_QUESTION)
    calls = getattr(message, "tool_calls", None) or []
    if not calls:
        raise AssertionError(
            f"no tool_calls (content={(message.text or '')[:80]!r})"
        )
    return f"tool_call {calls[0]['name']}({list(calls[0].get('args', {}))})"


def _probe_structured_output(role: Role) -> str:
    """Rule 3: judge/extractor must return a valid object.

    Probes the production call shape — `structured()`, which is native
    with_structured_output backed by the fenced-JSON rung of the docs/01 §4 ladder —
    and reports which rung answered, because Kimi-K2.6 returns None intermittently.
    """
    caller = structured(role, Verdict)
    verdict = caller.invoke(
        "You are judging whether a research round is sufficient. Nothing has been "
        "searched yet, so it is not. Branch b1 is unresolved. Return a Verdict for "
        "round 1 with sufficient=false."
    )
    if not isinstance(verdict, Verdict):
        raise AssertionError(f"expected Verdict, got {type(verdict).__name__}")
    return (
        f"Verdict(round={verdict.round}, sufficient={verdict.sufficient}) "
        f"via {caller.last_mode}"
    )


def _probe_tavily_search() -> str:
    result = search_tool(include_domains=PRIMARY_DOMAINS, max_results=3).invoke(
        {"query": "Medicare LCD L33822 glucose monitors coverage criteria"}
    )
    results = result.get("results", []) if isinstance(result, dict) else []
    if not results:
        raise AssertionError(f"no results ({str(result)[:120]})")
    return f"{len(results)} results, top: {results[0].get('url', '?')}"


def _probe_tavily_extract() -> str:
    result = extract_tool().invoke({"urls": [CGM_LCD_URL]})
    results = result.get("results", []) if isinstance(result, dict) else []
    if not results:
        failed = result.get("failed_results") if isinstance(result, dict) else None
        raise AssertionError(f"extract returned no results (failed={str(failed)[:150]})")
    content = results[0].get("raw_content") or ""
    paragraphs = [p for p in content.split("\n") if p.strip()]
    if len(content) < 500:
        raise AssertionError(f"extract returned {len(content)} chars; too thin to cite")
    return f"{len(content)} chars, {len(paragraphs)} non-empty lines from the CGM LCD"


def _probe_langsmith() -> str:
    """docs/01 §6: tracing is enabled programmatically, so it does not depend on
    env load order. The tracer also gives us the run URL to paste into evidence."""
    settings = get_settings()
    if not settings.langsmith_api_key:
        raise AssertionError("LANGSMITH_API_KEY not set; tracing disabled")

    from langchain_core.tracers.langchain import wait_for_all_tracers

    with trace_run(
        "smoke", project_name=settings.langsmith_project, tags=["smoke"], inputs={"probe": "judge"}
    ) as trace:
        model_for("judge").invoke("Reply with the single word: ok")
        children = len(trace.run_tree.child_runs)
    wait_for_all_tracers()  # the run must be submitted before we claim it exists
    if not children:
        raise AssertionError("trace opened but the model call did not nest under it")
    _TRACE_URLS.append(trace.url)
    return f"{children} nested run under project {settings.langsmith_project!r}"


# --------------------------------------------------------------------------- runner


def run_smoke() -> list[Probe]:
    """Run every probe in order. Never raises; failures are recorded in the Probes."""
    get_settings()  # fail fast and loudly on a missing credential
    _TRACE_URLS.clear()

    probes = [
        # One probe per role in ModelRouting (docs/09 §1.2: "for each role"), each
        # in the call shape that role actually uses in production.
        _run(Probe("root: code-as-action -> fenced python", "root"),
             lambda: _probe_code_as_action("root")),
        _run(Probe("critic: code-as-action -> fenced json", "critic"),
             lambda: _probe_fenced_json("critic")),
        _run(Probe("subagent: native tool call", "subagent"),
             lambda: _probe_native_tool_call("subagent")),
        _run(Probe("judge: structured output (Verdict)", "judge"),
             lambda: _probe_structured_output("judge")),
        _run(Probe("extractor: structured output (Verdict)", "extractor"),
             lambda: _probe_structured_output("extractor")),
        _run(Probe("evaluator: structured output (Verdict)", "evaluator"),
             lambda: _probe_structured_output("evaluator")),
        _run(Probe("baseline: native tool call (starter shape)", "baseline"),
             lambda: _probe_native_tool_call("baseline")),
        _run(Probe("tavily: search (cms.gov, fda.gov)"), _probe_tavily_search),
        _run(Probe("tavily: extract (CGM LCD L33822)"), _probe_tavily_extract),
        _run(Probe("langsmith: trace created"), _probe_langsmith),
    ]
    for probe in probes:
        if probe.name.startswith("langsmith") and _TRACE_URLS:
            probe.url = _TRACE_URLS[0]
    return probes

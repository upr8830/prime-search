"""Console rendering (docs/09 §1.7).

Three of these are regressions from the first live 1.7 run, where the rendering layer
managed to lose information and then end a run outright.
"""

from __future__ import annotations

import io

from prime_search.render import _Renderer, _console_safe
from rich.console import Console


class _Stream:
    """A stdout stand-in with a fixed encoding; io.StringIO.encoding is read-only."""

    def __init__(self, encoding: str) -> None:
        self.encoding = encoding


def _renderer() -> tuple[_Renderer, io.StringIO]:
    buffer = io.StringIO()
    console = Console(file=buffer, width=100, force_terminal=False, no_color=True)
    return _Renderer(console), buffer


def test_a_fetch_event_shows_the_real_tier() -> None:
    """primitives/tavily.py's FetchResult.event() uses `tier`; reading `source_tier`
    silently rendered every primary_policy document as "unknown"."""
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "fetch",
            "payload": {"tier": "primary_policy", "title": "LCD - Glucose Monitors (L33822)"},
        }
    )
    assert "primary_policy" in buffer.getvalue()
    assert "unknown" not in buffer.getvalue()


def test_a_task_done_event_reads_the_nested_task_result() -> None:
    """The sub-agent's own event nests the whole TaskResult under "result" (docs/02
    §4). Reading only the flat keys printed every branch as "?: 0 evidence"."""
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "task.done",
            "payload": {
                "task_id": "b1-r0",
                "result": {
                    "evidence_ids": ["ev1", "ev2", "ev3"],
                    "unresolved": None,
                    "summary": "s",
                },
            },
        }
    )
    output = buffer.getvalue()
    assert "b1" in output
    assert "3 evidence" in output


def test_a_task_done_event_reads_the_flat_failure_shape() -> None:
    """The graph emits this one only for a branch that died before the sub-agent could
    report."""
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "task.done",
            "payload": {
                "task_id": "b2-r0",
                "branch_id": "b2",
                "evidence": 0,
                "unresolved": "this branch failed: RuntimeError: tavily down",
            },
        }
    )
    output = buffer.getvalue()
    assert "b2" in output and "0 evidence" in output and "tavily down" in output


def test_an_unencodable_character_is_replaced_not_raised() -> None:
    """U+202F in "50 mg/dL" killed a live run writing to a cp1252 console."""
    out = _console_safe("under 50\u202fmg/dL", _Stream("cp1252"))
    out.encode("cp1252")  # must not raise
    assert "mg/dL" in out


def test_utf8_text_is_passed_through_untouched() -> None:
    assert _console_safe("under 50\u202fmg/dL", _Stream("utf-8")) == "under 50\u202fmg/dL"


def test_a_renderer_failure_never_escapes_into_the_run() -> None:
    """Everything watching a run is downstream of the answer."""
    renderer, _ = _renderer()
    renderer.event({"type": "fetch", "payload": "not a dict at all"})  # must not raise


def test_the_trace_url_is_captured_even_with_events_off() -> None:
    """--no-events still has to print the trace URL; the gate asks for it."""
    buffer = io.StringIO()
    console = Console(file=buffer, width=100)
    renderer = _Renderer(console, show_events=False)
    renderer.event(
        {"type": "run.started", "payload": {"trace_url": "https://smith.langchain.com/x"}}
    )
    assert renderer.trace_url == "https://smith.langchain.com/x"
    assert buffer.getvalue() == ""  # and nothing was rendered


def test_a_verdict_event_prints_the_round_and_how_many_tasks_it_added() -> None:
    """docs/07 §3: "Round separators show the judge's verdict and how many tasks it added"."""
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "verdict",
            "payload": {
                "round": 0, "sufficient": False,
                "coverage": {"b1": "resolved", "b2": "partial"},
                "missing": ["the revision date [of L33822]"],
                "new_tasks": [{"task_id": "b2-r1"}, {"task_id": "b2-r1-2"}],
                "reasoning": "r",
            },
        }
    )
    out = buffer.getvalue()
    assert "round 0: judge -> insufficient -> 2 new tasks" in out
    assert "b2 partial" in out
    assert "the revision date [of L33822]" in out  # printed, not swallowed as markup


def test_a_critic_task_is_labelled_critic() -> None:
    """docs/07 §3: "Critic-triggered tasks are labeled `critic`"."""
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "task.started",
            "payload": {"task_id": "b2-r1-critic1", "branch_id": "b2", "round": 1, "instruction": "Fetch the article"},
        }
    )
    out = buffer.getvalue()
    assert "start r1 critic b2" in out


def test_a_plan_task_is_not_labelled_critic() -> None:
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "task.started",
            "payload": {"task_id": "b1-r0", "branch_id": "b1", "round": 0, "instruction": "Find the LCD"},
        }
    )
    assert "critic" not in buffer.getvalue()
    assert "start b1" in buffer.getvalue()


def test_a_critique_event_prints_completion_and_first_findings() -> None:
    renderer, buffer = _renderer()
    renderer.event(
        {
            "type": "critique",
            "payload": {
                "completion_probability": 0.62,
                "recommended_searches": [{"task_id": "a"}, {"task_id": "b"}],
                "contradictions": ["A web guide says X; L33822 requires Y; the LCD governs"],
                "outdated_sources": [], "missing_interpretations": ["Part B versus Part D"],
            },
        }
    )
    out = buffer.getvalue()
    assert "critic completion 0.62, 2 recommended searches" in out
    assert "A web guide says X; L33822 requires Y; the LCD governs" in out
    assert "Part B versus Part D" in out

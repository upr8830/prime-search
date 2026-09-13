"""Logging configuration, secret redaction, and the LangSmith trace helper.

The trace test is marked `live`: it posts a real run. It is skipped unless keys are
in the environment, which is also the first exercise of the conftest skip
machinery and the `-m "not live"` default in pyproject.toml. To run it:

    uv run pytest tests/test_tracing.py -m live
"""

from __future__ import annotations

import logging

import pytest
import structlog

from prime_search.tracing import REDACTED, configure_logging, get_logger, trace_run

FAKE_TAVILY = "tvly-" + "A" * 32


def test_configure_logging_is_idempotent_and_sets_the_level() -> None:
    configure_logging(level="WARNING", json_logs=True)
    configure_logging(level="WARNING", json_logs=True)  # must not raise or double-wrap
    assert structlog.is_configured()
    logger = get_logger()
    assert not logger.is_enabled_for(logging.DEBUG)
    assert logger.is_enabled_for(logging.WARNING)


def test_an_unknown_level_name_falls_back_to_info_rather_than_crashing() -> None:
    configure_logging(level="NOT_A_LEVEL", json_logs=True)
    assert get_logger().is_enabled_for(logging.INFO)


def test_a_logged_secret_never_reaches_the_renderer(capsys: pytest.CaptureFixture) -> None:
    """docs/01 §8: API keys are never logged. This is the end-to-end path, not just
    the processor in isolation."""
    configure_logging(level="INFO", json_logs=True)
    get_logger().info("tavily.search", url=f"https://x/?k={FAKE_TAVILY}", api_key=FAKE_TAVILY)
    err = capsys.readouterr().err
    assert FAKE_TAVILY not in err
    assert REDACTED in err
    assert "tavily.search" in err  # the event itself still gets through


def test_logs_go_to_stderr_leaving_stdout_for_answers(capsys: pytest.CaptureFixture) -> None:
    """stdout carries CLI answers and the SSE stream, so nothing may log there."""
    configure_logging(level="INFO", json_logs=True)
    get_logger().info("run.finished", run_id="abc")
    captured = capsys.readouterr()
    assert "run.finished" in captured.err
    assert captured.out == ""


@pytest.mark.live
def test_trace_run_creates_a_real_run_and_exposes_its_url() -> None:
    """docs/01 §6. Replaces tracing_v2_enabled, whose get_run_url() never works
    under langchain-core 1.6 (see the docs/11 decision log)."""
    from prime_search.config import get_settings

    settings = get_settings()
    if not settings.langsmith_api_key:
        pytest.skip("LANGSMITH_API_KEY not set")

    with trace_run("test", tags=["pytest"], inputs={"probe": "tracing"}) as trace:
        assert trace.url.startswith("https://")
        assert trace.trace_id in trace.url  # url is valid before the block exits


def test_trace_run_with_tracing_off_touches_no_langsmith(monkeypatch) -> None:
    """docs/07 §9-10: the API and UI work with tracing off. A keyless run used to post
    a RunTree and read its project to build the URL, failing inside `trace_run`."""
    import langsmith

    from prime_search import config

    class TracingOff:
        tracing_enabled = False

    def no_langsmith(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise AssertionError("RunTree must not be built with tracing off")

    monkeypatch.setattr(config, "get_settings", lambda: TracingOff())
    monkeypatch.setattr(langsmith, "RunTree", no_langsmith)

    with trace_run("test", tags=["pytest"]) as trace:
        assert trace.url is None and trace.trace_id is None
        trace.add_tags("domain:cgm")  # a no-op, not an error

    with pytest.raises(ValueError, match="boom"), trace_run("test"):
        raise ValueError("boom")

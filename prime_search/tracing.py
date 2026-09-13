"""Structured logging and (from task 1.2) LangSmith tracing helpers.

Logging is configured here rather than in a logging.py because docs/01 §10 lists no
such module, and §8 already assigns the tvly-/lsv2_ redaction to this file. Every
event passes through redact_secrets before rendering.

Logs go to stderr. stdout belongs to CLI answers and the SSE stream, so nothing
here may write to it.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog

REDACTED = "***redacted***"

# The character class sits immediately after each prefix so these source lines
# cannot themselves trip .claude/hooks/guard-commit.sh.
_SECRET_VALUE = re.compile(r"(tvly-[\w\-]{6,}|lsv2_[\w\-]{6,}|sk-[\w\-]{16,})")
_SECRET_KEY = re.compile(r"(api_?key|secret|token|password|authorization)", re.IGNORECASE)


def _scrub(value: Any) -> Any:
    """Mask key-shaped values, and key-shaped field names, at any nesting depth."""
    if isinstance(value, str):
        return _SECRET_VALUE.sub(REDACTED, value)
    if isinstance(value, dict):
        return {
            k: (REDACTED if _SECRET_KEY.search(str(k)) else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(_scrub(v) for v in value)
    return value


def redact_secrets(_logger: Any, _method: str, event_dict: dict) -> dict:
    """structlog processor. docs/01 §8: API keys are never logged."""
    return {
        k: (REDACTED if _SECRET_KEY.search(str(k)) else _scrub(v))
        for k, v in event_dict.items()
    }


def configure_logging(level: str | None = None, json_logs: bool | None = None) -> None:
    """Idempotent; called from cli.py and from the FastAPI startup hook.

    PRIME_LOG_LEVEL / PRIME_LOG_JSON are read from the environment directly rather
    than through Settings, so logging works even when config validation fails.
    Output is JSON when stderr is not a TTY, so piped bench runs stay parseable.
    """
    level_name = (level or os.getenv("PRIME_LOG_LEVEL", "INFO")).upper()
    level_no = getattr(logging, level_name, logging.INFO)
    tty = sys.stderr.isatty()
    if json_logs is None:
        json_logs = os.getenv("PRIME_LOG_JSON", "").lower() in {"1", "true", "yes"} or not tty
    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=tty)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # events.py binds run_id per run
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            redact_secrets,  # last gate before rendering
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_no),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(stream=sys.stderr, level=level_no, format="%(message)s")


def get_logger(**initial: Any) -> Any:
    return structlog.get_logger(**initial)


# --------------------------------------------------------------------------- tracing


class TraceHandle:
    """A live LangSmith trace. `url` is valid as soon as the block is entered, so it
    can be streamed to the UI and stored on the RunRecord before the run finishes.

    With tracing off the handle is null: `run_tree`, `url` and `trace_id` are None and
    `add_tags` does nothing (docs/07 §9: "tracing off" instead of a link)."""

    __slots__ = ("run_tree", "url", "trace_id")

    def __init__(self, run_tree: Any | None) -> None:
        self.run_tree = run_tree
        self.url: str | None = run_tree.get_url() if run_tree is not None else None
        self.trace_id: str | None = str(run_tree.trace_id) if run_tree is not None else None

    def add_tags(self, *tags: str) -> None:
        """Add tags to the live root run.

        docs/06 §2 puts `domain:` and `qtype:` on the *root* run, but they are only
        known once `understand` has run — by which time the trace is already open and
        its tags already posted. Patching is the only way to get them onto the run the
        filter query actually looks at; adding them to the `understand` child instead
        would make "all cgm runs" unfindable.

        Never raises: a tracing failure must not end a run that is otherwise fine.
        """
        if self.run_tree is None:
            return
        new = [tag for tag in tags if tag and tag not in (self.run_tree.tags or [])]
        if not new:
            return
        try:
            self.run_tree.tags = list(self.run_tree.tags or []) + new
            self.run_tree.patch()
        except Exception as exc:  # noqa: BLE001 - see docstring
            get_logger(component="tracing").warning("trace.add_tags_failed", error=str(exc))


def _tracing_on() -> bool:
    """Settings decide, not the environment: `.env` supplies the key (docs/01 §3)."""
    try:
        from prime_search.config import get_settings

        return get_settings().tracing_enabled
    except Exception:  # noqa: BLE001 - unreadable settings: run untraced rather than fail
        return False


@contextmanager
def trace_run(
    name: str,
    *,
    project_name: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
) -> Iterator[TraceHandle]:
    """Open a LangSmith trace and yield a handle carrying its URL.

    docs/01 §6 specifies tracing enabled programmatically so it does not depend on
    env load order. It names langchain-core's `tracing_v2_enabled`, but under
    langchain-core 1.6 that tracer never populates `latest_run`, so `get_run_url()`
    always raises "No traced run found." An explicit RunTree parent is the working
    equivalent and additionally makes the URL available *before* the run ends.

    Everything invoked inside the block nests under this run.

    With no LangSmith key the block runs untraced under a null handle. It used to post
    a RunTree anyway, and `get_url()` then read the project over the network, so a
    keyless run failed inside `trace_run` instead of running (docs/11).
    """
    if not _tracing_on():
        yield TraceHandle(None)
        return

    from langsmith import RunTree, tracing_context

    run_tree = RunTree(
        name=name,
        run_type="chain",
        project_name=project_name or os.getenv("LANGSMITH_PROJECT", "prime-search"),
        tags=tags or [],
        extra={"metadata": metadata or {}},  # RunTree rejects extra=None
        inputs=inputs or {},
    )
    run_tree.post()
    handle = TraceHandle(run_tree)
    try:
        with tracing_context(enabled=True, parent=run_tree):
            yield handle
    except Exception as exc:
        run_tree.end(error=f"{type(exc).__name__}: {exc}")
        run_tree.patch()
        raise
    else:
        if run_tree.end_time is None:
            run_tree.end(outputs={})
        run_tree.patch()

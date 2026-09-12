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

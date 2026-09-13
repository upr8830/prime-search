"""`GET /run/{run_id}/events`: what is on disk, then what happens next (docs/02 §4).

Ordering is what makes this correct:

1. Subscribe first, so nothing emitted from here on is missed.
2. Replay `events.jsonl` past the client's `Last-Event-ID`.
3. Drain live events, dropping any `seq` already sent.

`emit` appends and publishes under one lock, so subscribers receive events in `seq` order.
An event can still arrive both in the replay and in the queue (appended before the replay
read, published after the subscription), and `seq` removes that duplicate.

The stream ends at `run.finished`, including one the client already has: a browser
EventSource reconnects on its own after a close, and must not be told a completed run
failed. A run that never finished, and that nobody is still writing to, ends with a
synthetic `error` and `run.finished`. These are sent but never written, so the record on
disk stays exactly as the run left it.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from starlette.concurrency import run_in_threadpool

from prime_search import events
from prime_search.api import runs

__all__ = ["event_stream"]

# How long to wait for a live event before checking whether anyone is still running the
# run. Not a latency: live events arrive as soon as they are emitted.
POLL_SECONDS = 1.0
# A run this process did not start (the CLI, an earlier API process) is streamed from its
# file. It counts as interrupted only once that file has been quiet this long, because a
# prime model call can take minutes between events.
STALE_SECONDS = 180.0
INTERRUPTED = "run interrupted: the process running it stopped before it finished"


async def event_stream(
    run_id: str,
    relative: str,
    registry: runs.RunRegistry,
    last_event_id: int | None,
) -> AsyncIterator[dict[str, Any]]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def on_event(record: dict[str, Any]) -> None:
        # Called on whichever thread emitted (a LangGraph worker); hand it to the loop.
        loop.call_soon_threadsafe(queue.put_nowait, record)

    unsubscribe = events.subscribe(run_id, on_event)
    last = -1 if last_event_id is None else last_event_id
    try:
        for record in await _replay(relative):
            if record["seq"] <= last:
                if record["type"] == "run.finished":
                    return  # the client already has the end
                continue
            last = record["seq"]
            yield _frame(record)
            if record["type"] == "run.finished":
                return

        while True:
            try:
                record = await asyncio.wait_for(queue.get(), timeout=POLL_SECONDS)
            except TimeoutError:
                if registry.is_active(run_id):
                    continue
                # Finished just now, or not this process's run: the file is the source.
                for record in await _replay(relative):
                    if record["seq"] <= last:
                        if record["type"] == "run.finished":
                            return
                        continue
                    last = record["seq"]
                    yield _frame(record)
                    if record["type"] == "run.finished":
                        return
                if not registry.knows(run_id) and _recently_written(relative):
                    continue  # another process is still writing it
                for frame in _interrupted(run_id):
                    yield frame
                return
            seq = record.get("seq")
            if seq is not None:
                if seq <= last:
                    if record["type"] == "run.finished":
                        return
                    continue
                last = seq
            yield _frame(record)
            if record["type"] == "run.finished":
                return
    finally:
        unsubscribe()


async def _replay(relative: str) -> list[dict[str, Any]]:
    return await run_in_threadpool(lambda: list(events.replay(relative)))


def _recently_written(relative: str) -> bool:
    try:
        modified = (events.runs_root() / relative / "events.jsonl").stat().st_mtime
    except OSError:
        return False
    return time.time() - modified < STALE_SECONDS


def _frame(record: dict[str, Any]) -> dict[str, Any]:
    """`event: <type>`, `id: <seq>`, `data: <payload json>` (docs/02 §4)."""
    frame: dict[str, Any] = {
        "event": record["type"],
        "data": json.dumps(record.get("payload"), ensure_ascii=False, default=str),
    }
    if record.get("seq") is not None:
        frame["id"] = str(record["seq"])
    return frame


def _interrupted(run_id: str) -> list[dict[str, Any]]:
    saved = runs.load_record(run_id)
    url = saved.langsmith_run_url if saved is not None else None
    # No `id`: these are not in the file, so they must not move a client's Last-Event-ID.
    return [
        {"event": "error", "data": json.dumps({"message": INTERRUPTED, "node": "api"})},
        {"event": "run.finished", "data": json.dumps({"status": "failed", "langsmith_run_url": url})},
    ]

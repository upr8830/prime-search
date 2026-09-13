"""`GET /run/{run_id}/events`: what is on disk, then what happens next (docs/02 §4).

Ordering is what makes this correct:

1. Subscribe first, so nothing emitted from here on is missed.
2. Replay `events.jsonl` past the client's `Last-Event-ID`.
3. Drain live events, dropping any `seq` already sent.

`emit` appends under a lock and publishes after releasing it, so an event can arrive in
both the replay and the queue; `seq` (assigned under that lock) removes the duplicate.
The stream ends at `run.finished`. A run that no worker here is running and that never
finished (the API restarted mid-run) ends with a synthetic `error` and `run.finished`
that are sent but never written: the record on disk stays exactly as the run left it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from starlette.concurrency import run_in_threadpool

from prime_search import events
from prime_search.api import runs

__all__ = ["event_stream"]

# How long to wait for a live event before checking whether anyone is still running
# the run. Not a latency: live events arrive as soon as they are emitted.
POLL_SECONDS = 1.0
INTERRUPTED = "run interrupted: the API process running it stopped before it finished"


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
        for record in await run_in_threadpool(lambda: list(events.replay(relative))):
            if record["seq"] <= last:
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
                # Finished just now, or not this process's run: whatever is on disk
                # past `last` is all there will be.
                for record in await run_in_threadpool(lambda: list(events.replay(relative))):
                    if record["seq"] <= last:
                        continue
                    last = record["seq"]
                    yield _frame(record)
                    if record["type"] == "run.finished":
                        return
                for frame in _interrupted(run_id):
                    yield frame
                return
            seq = record.get("seq")
            if seq is not None:
                if seq <= last:
                    continue
                last = seq
            yield _frame(record)
            if record["type"] == "run.finished":
                return
    finally:
        unsubscribe()


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

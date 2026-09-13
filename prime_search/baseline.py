"""The baseline agent (docs/03 §9): the starter, reproduced.

This is the control arm. Every number in the Day 2 bench is a delta against it, so the
only correct implementation is the least impressive one — the starter's model, the
starter's three-line prompt, one `TavilySearch` tool, and nothing else. §9 is explicit:
"Nothing else is added, so the comparison is fair."

`starter_agent.py` itself is never copied into or committed to this repo (CLAUDE.md);
what is reproduced here is its configuration.

Three places where §9's code sketch and CLAUDE.md's conventions disagree, and how each
is resolved:

* §9 writes `ChatNebius(...)` inline; CLAUDE.md says every ChatNebius is built in
  `models.py`. Resolved in favour of CLAUDE.md — `models.baseline_model()` already
  pins the starter's model id and leaves temperature at the provider default, and
  docs/01 §3 marks that role "do not change".
* §9 puts `STARTER_SYSTEM_PROMPT` in Python; CLAUDE.md says prompts are `.md` files.
  Resolved in favour of CLAUDE.md: `prompts/baseline.md`, the three lines verbatim.
* §9 uses a raw `TavilySearch()`; CLAUDE.md says every Tavily call goes through
  `primitives/`. **Resolved in favour of docs/03 §9** — this is the one deliberate
  exception in the codebase. Our primitives add a cache, tier classification, URL
  normalization and a raw-content fallback; routing the baseline through them would
  make the control arm better than the thing it is a control for, and would shrink
  every reported improvement by however much our retrieval layer contributes. A
  dishonest baseline is worse than an inconvenient one. Logged in docs/11.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_tavily import TavilySearch

from prime_search import events
from prime_search.config import get_settings
from prime_search.agents.synthesizer import safe_token_sink
from prime_search.models import baseline_model, token_usage
from prime_search.prompts import load
from prime_search.schemas import Answer, Citation, RunRecord, RunRequest
from prime_search.tracing import get_logger, trace_run
from prime_search.workspace import Workspace

_log = get_logger(component="baseline")

__all__ = ["STARTER_SYSTEM_PROMPT", "build_baseline_agent", "run_baseline"]

# The starter's three-line prompt, held in prompts/baseline.md. Loaded rather than
# inlined so a diff of the prompts folder shows every prompt the system uses.
STARTER_SYSTEM_PROMPT = load("baseline")

_URL = re.compile(r"https?://[^\s<>\)\]\"']+")


def build_baseline_agent(model: BaseChatModel | None = None) -> Any:
    """The starter's agent: one model, one search tool, one prompt."""
    settings = get_settings()
    settings.export_sdk_env()  # TavilySearch reads TAVILY_API_KEY from the environment
    return create_agent(
        # `stream_usage` asks the endpoint to report token usage on the stream; without
        # it every streamed reply carried none and the baseline logged input_tokens=0.
        # Measurement only: the model, prompt and tool are the starter's (docs/11).
        model=model or baseline_model(streaming=True, stream_usage=True),
        tools=[TavilySearch()],
        system_prompt=STARTER_SYSTEM_PROMPT,
    )


def run_baseline(
    request: RunRequest,
    *,
    on_event: Callable[[dict], None] | None = None,
    on_token: Callable[[str], None] | None = None,
    model: BaseChatModel | None = None,
    source: str = "cli",
    extra_tags: Sequence[str] = (),
    project_name: str | None = None,
    ws: Workspace | None = None,
) -> RunRecord:
    """Run the baseline once and return a `RunRecord`, so both modes are comparable.

    `source`, `extra_tags` and `project_name` label the root trace as for `run_prime`;
    `ws` lets a caller (the bench) know the run id even when the run raises.

    The starter prints and exits; the bench needs a record with usage and an `Answer`.
    Wrapping its output is not adding capability to the agent — the agent sees exactly
    what the starter's agent saw.
    """
    settings = get_settings()
    ws = ws or Workspace(objective=request.question, budget=settings.budget(request.depth))
    started = datetime.now(UTC)
    unsubscribe = events.subscribe(ws.run_id, on_event) if on_event else None
    # Same rule as synthesis: whatever is watching a run is downstream of the answer,
    # and a console that cannot encode a character must not end the run.
    on_token = safe_token_sink(on_token)

    agent = build_baseline_agent(model)
    tags = [
        "mode:baseline",
        f"depth:{request.depth}",
        f"model:{settings.models.baseline}",
        f"source:{source}",
        *extra_tags,
    ]
    text_parts: list[str] = []
    status = "completed"
    error: str | None = None
    trace_url: str | None = None
    trace_id: str | None = None

    try:
        with trace_run(
            "baseline",
            project_name=project_name,
            tags=tags,
            metadata={
                "run_id": ws.run_id,
                "question_id": request.question_id,
                "question": request.question,
                "provider": "nebius",
                "model": settings.models.baseline,
                "source": source,
                # Raw TavilySearch, never through primitives/ (docs/03 §9): uncached.
                "tavily_cache": False,
            },
            inputs={"question": request.question},
        ) as handle:
            trace_url, trace_id = handle.url, handle.trace_id
            events.emit(
                ws.run_id,
                "run.started",
                {
                    "run_id": ws.run_id,
                    "question": request.question,
                    "mode": "baseline",
                    "depth": request.depth,
                    "trace_url": handle.url,
                },
            )
            for stream_mode, chunk in agent.stream(
                {"messages": [{"role": "user", "content": request.question}]},
                stream_mode=["messages", "updates"],
                config={"run_name": "baseline", "tags": tags},
            ):
                if stream_mode == "messages":
                    _on_message_chunk(chunk, ws, text_parts, on_token)
                else:
                    _on_update(chunk, ws)
    except Exception as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
        _log.warning("baseline.failed", error=error)
        events.emit(ws.run_id, "error", {"message": error[:500], "node": "baseline"})
        raise
    finally:
        # Everything below is inside the `finally` and ordered deliberately:
        # `answer`, then `usage`, then `run.finished`, and only then unsubscribe.
        # docs/06 §4 has `emit()` push to the in-process subscriber queue, and docs/02
        # §4 makes `run.finished` the footer link - the point an SSE client closes on.
        # With the answer emitted after it, a client saw the run end and then the
        # answer; with `unsubscribe()` first, it saw neither. Being in the `finally`
        # also means a failed run persists a record, as a prime run does.
        body = "".join(text_parts).strip()
        answer = _wrap_answer(body)
        ws.usage.wall_seconds = round((datetime.now(UTC) - started).total_seconds(), 1)
        if body:
            events.emit(ws.run_id, "answer", answer)
        events.emit(ws.run_id, "usage", ws.usage)
        record = ws.to_record(
            request,
            started_at=started,
            finished_at=datetime.now(UTC),
            langsmith_run_url=trace_url,
            langsmith_trace_id=trace_id,
            answer=answer if body else None,
            status=status,
            error=error,
        )
        # docs/02 §5's layout, same as a prime run. The baseline returned a record and
        # wrote nothing, so `runs/<run_id>/` held events but no state — and the Day 2
        # bench compares the two modes row by row from exactly these files.
        # Written BEFORE `run.finished`: a client acts on that event (the UI opens
        # feedback, and `POST /feedback` needs the record), so the record must exist.
        events.write_run_artifacts(record)
        events.emit(
            ws.run_id,
            "run.finished",
            {"status": status, "langsmith_run_url": trace_url, "usage": ws.usage},
        )
        if unsubscribe:
            unsubscribe()
    return record


def _on_message_chunk(
    chunk: Any, ws: Workspace, parts: list[str], on_token: Callable[[str], None] | None
) -> None:
    """`stream_mode="messages"` yields `(message_chunk, metadata)`, as the starter's
    renderer assumes.

    Only the assistant's own chunks are the answer. The same stream also carries
    `ToolMessage`s, and a Tavily result is a 4 KB JSON blob: taking every chunk's text
    put that blob into `body_markdown`, printed it to the console as if the model had
    written it, and made `_wrap_answer` parse ten "citations" out of the URLs inside
    the search results the model had not yet read.
    """
    message = chunk[0] if isinstance(chunk, tuple) else chunk
    if not isinstance(message, (AIMessage, AIMessageChunk)):
        return
    text = getattr(message, "text", "") or ""
    if not text:
        return
    parts.append(text)
    # docs/02 §4: "Baseline mode emits `run.started`, `search` (per tool call),
    # `token`, `answer`, `usage`, `run.finished` so the two panes share one renderer."
    events.emit(ws.run_id, "token", {"text": text})
    if on_token is not None:
        on_token(text)


def _on_update(chunk: Any, ws: Workspace) -> None:
    """docs/03 §9: "Tool calls are captured as `search` events".

    The payload is docs/02 §4's `{task_id, query, n_results, cached}` so the UI's two
    panes really do share one renderer. `task_id` is null and `cached` is False by
    construction — the baseline has no tasks and no cache, and saying so is more honest
    than omitting the keys and making the client guess which shape it received.
    """
    if not isinstance(chunk, dict):
        return
    for payload in chunk.values():
        for message in (payload or {}).get("messages", []) if isinstance(payload, dict) else []:
            for call in getattr(message, "tool_calls", []) or []:
                query = (call.get("args") or {}).get("query", "")
                ws.usage.searches += 1
                events.emit(
                    ws.run_id,
                    "search",
                    {
                        "task_id": None,
                        "query": str(query)[:300],
                        "n_results": None,  # filled in below when the result arrives
                        "cached": False,
                        "tool": call.get("name", "tavily_search"),
                    },
                )
            if isinstance(message, AIMessage):
                input_tokens, output_tokens, estimated = token_usage(message)
                ws.usage.input_tokens += input_tokens
                ws.usage.output_tokens += output_tokens
                ws.tokens_estimated = ws.tokens_estimated or estimated
            elif isinstance(message, ToolMessage):
                # The count the `search` event could not know when the call was made.
                events.emit(
                    ws.run_id,
                    "search",
                    {
                        "task_id": None,
                        "query": "",
                        "n_results": _result_count(message),
                        "cached": False,
                        "tool": getattr(message, "name", "tavily_search"),
                    },
                )


def _result_count(message: Any) -> int | None:
    """How many results a Tavily tool message carried, if it can be read cheaply."""
    import json

    try:
        payload = json.loads(str(getattr(message, "content", "")))
    except (ValueError, TypeError):
        return None
    results = payload.get("results") if isinstance(payload, dict) else None
    return len(results) if isinstance(results, list) else None


def _wrap_answer(body: str) -> Answer:
    """docs/03 §9: "the final text is wrapped into `Answer` with URL-parsed citations".

    The URLs are parsed out of the prose because that is the only place the starter
    puts them — it has no evidence store, no documents and no verbatim passages, so
    `Citation.evidence_id` and `doc_id` are empty here by construction. That absence is
    itself a finding the bench reports: a baseline citation cannot be checked against a
    passage, which is what the docs/04 §7 citation evaluator measures.
    """
    citations: list[Citation] = []
    seen: set[str] = set()
    for url in _URL.findall(body):
        cleaned = url.rstrip(".,;:)")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        citations.append(
            Citation(n=len(citations) + 1, evidence_id="", doc_id="", url=cleaned, label=cleaned)
        )
    summary = re.sub(r"\s+", " ", body).strip()
    return Answer(
        summary=summary[:1000],
        body_markdown=body,
        claims=[],
        citations=citations,
        effective_dates=[],
        contradictions=[],
        unknowns=[],
        confidence=0.0,  # the starter reports none and none can be derived
        scope_warning=None,
    )

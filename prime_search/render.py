"""Console rendering for `prime-search ask` (docs/09 §1.7: "Rich rendering modeled on
the starter (tool calls, streaming answer, trace URL)").

Kept out of `cli.py` because the CLI is a thin argument parser (docs/01 §7) and because
this file is the reference for what a run *looks like* — the SSE stream at 2.4 renders
the same events into the UI, and having one place that names each event type makes the
two hard to drift apart.

The starter's shapes are reproduced: `Panel.fit` for the question, a rule before the
stream, yellow panels for tool calls, the answer under a green heading, and the trace
URL printed from a `finally` so it survives a crash. What PRIME adds is what PRIME has:
the classification, the plan, and a line per branch as it finishes.

ASCII only in anything printed: the Windows default console codepage renders an em dash
as a replacement character.
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from prime_search.schemas import Answer, RunRecord, RunRequest

__all__ = ["render_ask"]

_TIER_STYLE = {
    "primary_policy": "bold green",
    "official_secondary": "green",
    "professional": "yellow",
    "trade": "yellow",
    "web": "dim",
    "unknown": "dim",
}


def render_ask(
    *,
    question: str,
    mode: str,
    depth: str,
    prompt_set: str = "base",
    show_events: bool = True,
) -> int:
    """Run one question and render it. Returns the process exit code."""
    _make_stdout_lenient()
    console = Console()
    console.print(Panel.fit(question, title=f"{mode} / {depth}", border_style="blue"))

    request = RunRequest(question=question, mode=mode, depth=depth, prompt_set=prompt_set)
    state = _Renderer(console, show_events=show_events)
    record: RunRecord | None = None
    try:
        if mode == "baseline":
            from prime_search.baseline import run_baseline

            record = run_baseline(request, on_event=state.event, on_token=state.token)
        else:
            from prime_search.agents.graph import run_prime

            record = run_prime(request, on_event=state.event, on_token=state.token)
    except Exception as exc:  # noqa: BLE001 - the URL below is the point of the finally
        state.close()
        console.print(f"[bold red]run failed:[/] {type(exc).__name__}: {exc}")
        return 1
    finally:
        state.close()
        if state.trace_url:
            console.print(f"\n[dim]trace:[/] [link]{state.trace_url}[/]")

    if record is None or record.answer is None:
        console.print("[bold red]no answer was produced[/]")
        return 1
    _print_answer(console, record.answer, mode=mode)
    _print_footer(console, record)
    return 0


class _Renderer:
    """Turns the event stream into console output.

    Stateful because the answer streams in tokens: the first token has to close the
    progress section and open the answer heading, and only the event stream knows when
    that happens.
    """

    def __init__(self, console: Console, *, show_events: bool = True) -> None:
        self.console = console
        self.show_events = show_events
        self.trace_url: str | None = None
        self.evidence_count = 0
        self._streaming = False
        self._ruled = False

    # --- events -------------------------------------------------------------------

    def event(self, record: dict) -> None:
        payload = record.get("payload") or {}
        handler = getattr(self, f"_on_{record.get('type', '').replace('.', '_')}", None)
        if record.get("type") in {"run.started", "run.finished"}:
            self.trace_url = (
                payload.get("trace_url") or payload.get("langsmith_run_url") or self.trace_url
            )
        if handler is None or not self.show_events:
            return
        self._rule()
        try:
            handler(payload)
        except Exception:  # noqa: BLE001, S110 - rendering must never end a run
            pass

    def _rule(self) -> None:
        if not self._ruled:
            self.console.rule("[bold blue]Agent stream")
            self._ruled = True

    def _on_understanding(self, payload: dict) -> None:
        entities = ", ".join(payload.get("entities") or []) or "-"
        self.console.print(
            f"[cyan]understood[/] {payload.get('domain', '?')} / "
            f"{payload.get('question_type', '?')} "
            f"[dim](time sensitivity: {payload.get('time_sensitivity', '?')})[/]"
        )
        self.console.print(f"  [dim]entities: {entities}[/]")
        if payload.get("scope_warning"):
            self.console.print(f"  [yellow]scope: {payload['scope_warning']}[/]")

    def _on_plan(self, payload: dict) -> None:
        """docs/02 §4's `plan` payload is a whole `SearchPlan`, so the tree can be drawn
        from the stream alone - which is what the UI at 2.4 does with the same event."""
        branches = payload.get("branches") or []
        self.console.print(f"[cyan]planned[/] {len(branches)} branches")
        for branch in branches:
            hypothesis = branch.get("hypothesis")
            self.console.print(
                f"  [bold]{branch.get('branch_id', '?')}[/] {branch.get('question', '')}"
            )
            self.console.print(
                f"      [dim]{branch.get('source_hint', 'any')}"
                + (f" - expects: {hypothesis}" if hypothesis else "")
                + "[/]"
            )
        if criteria := payload.get("stop_criteria"):
            self.console.print(f"  [dim]done when: {criteria}[/]")

    def _on_task_started(self, payload: dict) -> None:
        # docs/07 §3: "Critic-triggered tasks are labeled `critic`" - their task id ends
        # in `-critic{k}` (docs/02 §2.3). A re-search task shows its round.
        task_id = str(payload.get("task_id", ""))
        origin = " [magenta]critic[/]" if task_id.rsplit("-", 1)[-1].startswith("critic") else ""
        round_ = payload.get("round") or 0
        label = f" r{round_}" if round_ else ""
        self.console.print(
            f"[cyan]start{label}[/]{origin} {payload.get('branch_id', '?')}: "
            f"{str(payload.get('instruction', ''))[:90]}"
        )

    def _on_search(self, payload: dict) -> None:
        query = payload.get("query", "")
        results = payload.get("results")
        tail = f" [dim]-> {results} results[/]" if results is not None else ""
        self.console.print(
            Panel(f"{query}{tail}", title="search", border_style="yellow", expand=False)
        )

    def _on_fetch(self, payload: dict) -> None:
        # `tier`, not `source_tier`: primitives/tavily.py's FetchResult.event() is
        # docs/02 §4's payload and that is the key it uses. Reading the wrong one
        # silently rendered every primary_policy document as "unknown".
        tier = payload.get("tier", "unknown")
        style = _TIER_STYLE.get(tier, "dim")
        title = str(payload.get("title") or payload.get("url") or "")[:90]
        self.console.print(f"  [yellow]fetch[/] [{style}]{tier}[/] {title}")

    def _on_evidence(self, payload: dict) -> None:
        """docs/02 §4: an `evidence` event carries an `Evidence`. Counting them here is
        what gives the round summary its numbers - the graph no longer emits a second
        payload shape under this name."""
        self.evidence_count += 1
        self.console.print(f"  [green]evidence[/] {str(payload.get('claim_text', ''))[:100]}")

    def _on_usage(self, payload: dict) -> None:
        self.console.print(
            f"[cyan]round {payload.get('rounds', '?')} done[/] "
            f"{self.evidence_count} evidence, {payload.get('searches', 0)} searches, "
            f"{payload.get('fetches', 0)} fetches, {payload.get('deep_reads', 0)} deep reads"
        )

    def _on_task_done(self, payload: dict) -> None:
        # Two shapes reach here. The sub-agent's own event (docs/02 §4) nests the whole
        # TaskResult under "result"; the graph emits a flat one for the branch that
        # failed before the sub-agent could report. Both are read rather than forcing
        # one shape, because the nested one is the contract docs/02 §4 specifies.
        result = payload.get("result") or {}
        evidence = result.get("evidence_ids")
        count = len(evidence) if evidence is not None else payload.get("evidence", 0)
        unresolved = result.get("unresolved") or payload.get("unresolved")
        task_id = str(payload.get("task_id") or "")
        branch = payload.get("branch_id") or task_id.split("-")[0] or "?"

        style = "green" if count else "yellow"
        line = f"[{style}]done[/] {branch}: {count} evidence"
        if unresolved:
            line += f" [dim](unresolved: {str(unresolved)[:80]})[/]"
        self.console.print(line)

    def _on_verdict(self, payload: dict) -> None:
        """docs/07 §3's round separator: the judge's verdict and how many tasks it added."""
        tasks = payload.get("new_tasks") or []
        state = "sufficient" if payload.get("sufficient") else "insufficient"
        added = f" -> {len(tasks)} new task{'' if len(tasks) == 1 else 's'}" if tasks else ""
        self.console.print(f"[bold cyan]-- round {payload.get('round', '?')}: judge -> {state}{added}[/]")
        coverage = ", ".join(f"{branch} {status}" for branch, status in (payload.get("coverage") or {}).items())
        if coverage:
            self.console.print(f"  coverage: {coverage}", markup=False, style="dim")
        for item in (payload.get("missing") or [])[:2]:
            self.console.print(f"  missing: {item}", markup=False, style="dim")

    def _on_critique(self, payload: dict) -> None:
        """docs/07 §3's critic panel, in one line plus its first findings."""
        searches = payload.get("recommended_searches") or []
        probability = payload.get("completion_probability")
        shown = f"{probability:.2f}" if isinstance(probability, int | float) else "?"
        tail = (
            f", {len(searches)} recommended search{'' if len(searches) == 1 else 'es'}" if searches else ""
        )
        self.console.print(f"[bold magenta]critic[/] completion {shown}{tail}")
        for label, key in (
            ("contradiction", "contradictions"),
            ("outdated", "outdated_sources"),
            ("missed", "missing_interpretations"),
        ):
            for item in (payload.get(key) or [])[:3]:
                self.console.print(f"  {label}: {str(item)[:160]}", markup=False, style="dim")

    def _on_error(self, payload: dict) -> None:
        self.console.print(f"  [red]error[/] {str(payload.get('message', ''))[:200]}")

    # --- the streamed answer ------------------------------------------------------

    def token(self, text: str) -> None:
        if not self._streaming:
            self._rule()
            self.console.print("\n[bold green]Assistant[/]")
            self._streaming = True
        # Written raw: Rich markup in a model's own words would be interpreted, and a
        # policy answer that happens to contain [brackets] is exactly the case.
        self.console.file.write(_console_safe(text, self.console.file))
        self.console.file.flush()

    def close(self) -> None:
        if self._streaming:
            self.console.file.write("\n")
            self.console.file.flush()
            self._streaming = False


# --- final output -------------------------------------------------------------------


def _print_answer(console: Console, answer: Answer, *, mode: str) -> None:
    console.rule("[bold green]Answer")
    if answer.scope_warning:
        console.print(Panel(answer.scope_warning, border_style="yellow", title="scope"))
    console.print(Markdown(answer.body_markdown or answer.summary))

    # The baseline has no evidence and therefore no dates section; printing an empty
    # one would imply it tried.
    if mode == "prime" and answer.effective_dates:
        console.rule("[bold]Effective dates relied on")
        for line in answer.effective_dates:
            console.print(f"  {line}")

    if mode == "prime" and answer.contradictions:
        console.rule("[bold]Contradictions")
        for line in answer.contradictions:
            console.print(f"  {line}", markup=False)


def _print_footer(console: Console, record: RunRecord) -> None:
    usage = record.usage
    answer = record.answer
    bits = [
        f"{len(answer.citations) if answer else 0} citations",
        f"{usage.searches} searches",
        f"{usage.fetches} fetches",
        f"{usage.deep_reads} deep reads",
        f"{usage.input_tokens + usage.output_tokens} tokens",
    ]
    if answer and answer.confidence:
        bits.append(f"confidence {answer.confidence:.2f}")
    console.print(f"\n[dim]{' | '.join(bits)}[/]")


def _make_stdout_lenient() -> None:
    """Never let an un-encodable character end a run.

    Covers Rich's own writes as well as the raw token stream — `Markdown` rendering of
    the finished answer goes through Rich, and it would raise on the same U+202F. Best
    effort: a captured or replaced stdout may not support reconfigure, which is why
    `_console_safe` still guards the token path.
    """
    import sys

    # UTF-8 first: the answers are full of non-breaking hyphens, thin spaces and the
    # micro sign, and on cp1252 every one of them renders as "?" - "insulin?treated",
    # "glucose < 54?mg/dL". Modern Windows terminals handle UTF-8, so ask for it and
    # keep errors="replace" as the floor for the ones that do not.
    for kwargs in ({"encoding": "utf-8", "errors": "replace"}, {"errors": "replace"}):
        try:
            sys.stdout.reconfigure(**kwargs)  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError, LookupError):
            continue
        return


def _console_safe(text: str, stream: Any) -> str:
    """Drop characters the console's codepage cannot encode.

    The Windows default codepage is cp1252, and a model writing "50 mg/dL" with a
    narrow no-break space (U+202F) raised UnicodeEncodeError from the raw write — which
    killed a live run that had already gathered all ten of its evidence items. Only the
    *rendering* is sanitized; `Answer.body_markdown` keeps the original text, so the
    run record and the UI are unaffected.
    """
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    return text

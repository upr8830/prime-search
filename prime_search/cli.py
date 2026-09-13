"""Console entry point: `prime-search` (docs/01 §7, §2; docs/03 §8, §9).

`ask` renders a run as it happens, modeled on the starter's console output: the
question in a panel, a rule before the stream, tool activity in yellow, the answer
in green, the trace URL last and from a `finally` so a crash still prints it.

Everything it shows comes from `events.subscribe` rather than from reaching into
the graph, so task 2.4's SSE stream renders the same run from the same events
without a second rendering path.
"""

from __future__ import annotations

import typer

from prime_search import __version__
from prime_search.tracing import configure_logging

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    # ASCII only in console-visible strings: the Windows default codepage renders
    # an em dash as a replacement character.
    help="PRIME Search - agentic coverage-determination search over primary CMS/FDA sources.",
)


@app.callback()
def main() -> None:
    configure_logging()


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def ask(
    question: str = typer.Argument(..., help="The coverage question to investigate."),
    mode: str = typer.Option("prime", "--mode", help="prime | baseline"),
    depth: str = typer.Option("deep", "--depth", help="deep | fast"),
    prompt_set: str = typer.Option("base", "--prompt-set", help="base | optimized"),
    show_events: bool = typer.Option(True, "--events/--no-events", help="Render progress."),
) -> None:
    """Run one investigation and print a cited answer (docs/03 §8, §9)."""
    from prime_search.render import render_ask

    if mode not in {"prime", "baseline"}:
        typer.secho(f"unknown mode {mode!r}: use prime or baseline", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    if depth not in {"deep", "fast"}:
        typer.secho(f"unknown depth {depth!r}: use deep or fast", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    raise typer.Exit(
        render_ask(
            question=question, mode=mode, depth=depth, prompt_set=prompt_set, show_events=show_events
        )
    )


@app.command()
def smoke() -> None:
    """Verify each model role, Tavily search/extract, and LangSmith tracing.

    Exits non-zero if any probe fails, so `make setup && make smoke && make ask`
    stops at the first real problem (docs/01 §4, docs/09 §1.2).
    """
    from rich.console import Console
    from rich.table import Table

    from prime_search.smoke import run_smoke

    console = Console()
    probes = run_smoke()

    table = Table(title="PRIME Search smoke", title_style="bold", show_lines=False)
    table.add_column("check", no_wrap=True)
    table.add_column("status", no_wrap=True)
    table.add_column("s", justify="right", no_wrap=True)
    table.add_column("detail", overflow="fold")
    styles = {"PASS": "green", "FALLBACK": "yellow", "FAIL": "red"}
    for probe in probes:
        table.add_row(
            probe.name,
            f"[{styles.get(probe.status, 'white')}]{probe.status}[/]",
            f"{probe.seconds:.1f}",
            probe.detail,
        )
    console.print(table)
    for probe in probes:
        if probe.url:
            console.print(f"  {probe.name.split(':')[0]} trace: [link]{probe.url}[/]")

    failed = [p for p in probes if not p.ok]
    if failed:
        console.print(
            f"[bold red]{len(failed)} of {len(probes)} checks did not pass.[/] "
            "A FALLBACK is a finding, not a fix: repoint the role in config and record "
            "it in the docs/11 decision log."
        )
        raise typer.Exit(1)
    console.print(f"[bold green]all {len(probes)} checks passed[/]")

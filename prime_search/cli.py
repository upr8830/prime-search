"""Console entry point: `prime-search` (docs/01 §7, §2; docs/03 §9).

At task 1.1 this exists to make the console script real. `ask` is implemented in
task 1.7 with Rich rendering modeled on the starter; `smoke` in task 1.2.
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
) -> None:
    """Run one investigation and print a cited answer. (Task 1.7.)"""
    typer.secho("ask: not implemented yet - task 1.7", fg=typer.colors.YELLOW, err=True)
    raise typer.Exit(2)


@app.command()
def smoke() -> None:
    """Verify each model role, Tavily search/extract, and LangSmith tracing. (Task 1.2.)"""
    typer.secho("smoke: not implemented yet - task 1.2", fg=typer.colors.YELLOW, err=True)
    raise typer.Exit(2)

"""Prompt loading. Every prompt in the project is a Markdown file in this package
(CLAUDE.md), so they can be diffed, reviewed, and optimized by GEPA.

`prompt_set="optimized"` reads from prompts/optimized/, which GEPA writes on Day 3
(docs/05 §5), and falls back to the base prompt when GEPA did not produce one.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=64)
def load(name: str, prompt_set: str = "base") -> str:
    """Return the text of prompts/<name>.md (or prompts/optimized/<name>.md)."""
    stem = name[:-3] if name.endswith(".md") else name
    candidates = (
        [_DIR / "optimized" / f"{stem}.md", _DIR / f"{stem}.md"]
        if prompt_set == "optimized"
        else [_DIR / f"{stem}.md"]
    )
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"prompt {stem!r} not found in {_DIR} (prompt_set={prompt_set!r})"
    )


def render(name: str, prompt_set: str = "base", **values: object) -> str:
    """Load a prompt and substitute {placeholders}.

    str.format would choke on the literal braces in the prompts' code examples, so
    only the named placeholders are replaced.
    """
    text = load(name, prompt_set)
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text

"""Prompt loading. Every prompt in the project is a Markdown file in this package
(CLAUDE.md), so they can be diffed, reviewed, and optimized by GEPA.

`prompt_set="optimized"` reads from prompts/optimized/, which GEPA writes on Day 3
(docs/05 §5), and falls back to the base prompt when GEPA did not produce one.

A registered set (`register_prompt_set`) is held in memory: GEPA registers each candidate
under its own name, so concurrent runs of different candidates never read each other's
text, and nothing is written to disk until a candidate wins.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent
_FILE_SETS = ("base", "optimized")
_registered: dict[str, dict[str, str]] = {}
_registered_lock = threading.Lock()


def _stem(name: str) -> str:
    return name[:-3] if name.endswith(".md") else name


def register_prompt_set(name: str, texts: Mapping[str, str]) -> None:
    """Hold `texts` (prompt name -> text) as prompt set `name`; any prompt it does not
    name falls back to base."""
    if name in _FILE_SETS:
        raise ValueError(f"{name!r} is a file-backed prompt set and cannot be registered")
    with _registered_lock:
        _registered[name] = {_stem(key): value for key, value in texts.items()}


def unregister_prompt_set(name: str) -> None:
    with _registered_lock:
        _registered.pop(name, None)


def load(name: str, prompt_set: str = "base") -> str:
    """Return the text of prompts/<name>.md, prompts/optimized/<name>.md, or the text a
    registered set holds for it."""
    stem = _stem(name)
    with _registered_lock:
        registered = _registered.get(prompt_set)
    if registered is not None:
        text = registered.get(stem)
        return text if text is not None else _load_file(stem, "base")
    return _load_file(stem, prompt_set)


@lru_cache(maxsize=64)
def _load_file(stem: str, prompt_set: str) -> str:
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


# Tests clear the file cache through `load`, as they did when `load` itself was cached.
load.cache_clear = _load_file.cache_clear  # type: ignore[attr-defined]


def render(name: str, prompt_set: str = "base", **values: object) -> str:
    """Load a prompt and substitute {placeholders}.

    str.format would choke on the literal braces in the prompts' code examples, so
    only the named placeholders are replaced.
    """
    text = load(name, prompt_set)
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text

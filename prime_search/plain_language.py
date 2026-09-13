"""Plain words for the notes a reader of an answer sees (docs/11, customer-facing wording).

The prompts ask sub-agents to write unresolved items for a patient or clinician, and a
model does not always comply: a live run's note said "I exhausted my tool-call budget".
This is the code guard behind that rule. It runs where a note enters a task result,
the workspace's unknowns and the answer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

__all__ = [
    "DEADLINE_NOTE",
    "STOPPED_NOTE",
    "STOPPED_ON_ERROR_NOTE",
    "plain_doc_refs",
    "plain_note",
    "plain_notes",
]

STOPPED_NOTE = "This line of research stopped before it was finished."
STOPPED_ON_ERROR_NOTE = "This line of research stopped early because of a technical problem."
DEADLINE_NOTE = "This line of research did not start because the research reached its time limit."

# Words that only mean something to whoever built the system.
_ENGINEER_WORDS = re.compile(
    r"\b(?:budgets?|tool[- ]?calls?|tokens?|max_\w+|add_evidence|search_within|note_unresolved|doc_ids?)\b"
    r"|\bran out of calls\b|\bcalls? (?:left|remaining)\b",
    re.IGNORECASE,
)
# docs/02 §2.4's document id.
_DOC_REF = re.compile(r"\b(doc_[0-9a-f]{10})\b")
_NOTHING = re.compile(r"(?i)^(?:none|nothing|n/?a)\.?$")
# A sentence ends at . ! or ? followed by space, or at a line break (a bulleted note).
_BREAK = re.compile(r"(?<=[.!?])\s+|\s*\n\s*")
_BULLET = re.compile(r"^[-*\u2022]\s+")


def plain_doc_refs(text: str, documents: Mapping[str, Any] | None) -> str:
    """Replace internal document ids with the document's title, or "a source document"."""

    def title(match: re.Match[str]) -> str:
        document = (documents or {}).get(match.group(1))
        name = (getattr(document, "title", "") or "").strip()
        return f'"{name}"' if name else "a source document"

    return _DOC_REF.sub(title, text)


def plain_notes(notes: Iterable[str | None], documents: Mapping[str, Any] | None = None) -> list[str]:
    """Each note without its engineer sentences, in order and without duplicates.

    A sentence that mentions budgets, tool calls or tokens is dropped, and the list ends
    with one `STOPPED_NOTE` in its place: a reader needs to know the research stopped,
    not how it counted. Notes that only say "None." are dropped; document ids become
    titles.
    """
    kept: list[str] = []
    stopped = False
    for note in notes:
        if not note:
            continue
        sentences: list[str] = []
        for part in _BREAK.split(note.strip()):
            sentence = _BULLET.sub("", part.strip())
            if not sentence or _NOTHING.match(sentence):
                continue
            if sentence == STOPPED_NOTE or _ENGINEER_WORDS.search(sentence):
                stopped = True
                continue
            sentences.append(plain_doc_refs(sentence, documents))
        text = " ".join(sentences)
        if text and text not in kept:
            kept.append(text)
    if stopped:
        kept.append(STOPPED_NOTE)
    return kept


def plain_note(text: str, documents: Mapping[str, Any] | None = None) -> str:
    """`plain_notes` for one note, joined back into one string ("" when nothing is left)."""
    return " ".join(plain_notes([text], documents))

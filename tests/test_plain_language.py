"""Plain words for the notes a reader sees (docs/11, customer-facing wording)."""

from __future__ import annotations

import re
from types import SimpleNamespace

from prime_search.plain_language import (
    DEADLINE_NOTE,
    STOPPED_NOTE,
    STOPPED_ON_ERROR_NOTE,
    plain_note,
    plain_notes,
)

ENGINEER = re.compile(r"budget|tool[- ]?call|token|max_|add_evidence|doc_[0-9a-f]{10}", re.IGNORECASE)


def test_the_live_b3_note_keeps_its_finding_and_loses_the_budget() -> None:
    """Sub-agent b3-r0 of a live deep run ignored the prompt rule."""
    note = (
        "I could not record verbatim evidence because I exhausted my tool-call budget when the final "
        "`add_evidence` call was rejected for a paraphrased quote. I also could not confirm from the "
        "revision history exactly when the hypoglycemia alternative criterion was first introduced."
    )
    assert plain_note(note) == (
        "I also could not confirm from the revision history exactly when the hypoglycemia "
        "alternative criterion was first introduced. " + STOPPED_NOTE
    )


def test_a_note_only_about_running_out_becomes_the_stop_note() -> None:
    assert plain_note("Ran out of tool calls before recording evidence.") == STOPPED_NOTE


def test_the_stop_note_appears_once_and_none_is_dropped() -> None:
    notes = [
        STOPPED_NOTE,
        "None.",
        "- The ICD-10 code list was not confirmed.\n- I had no calls left.",
        "The ICD-10 code list was not confirmed.",
    ]
    assert plain_notes(notes) == ["The ICD-10 code list was not confirmed.", STOPPED_NOTE]


def test_doc_ids_become_titles() -> None:
    documents = {"doc_7e7be1abff": SimpleNamespace(title="Dexcom community post")}
    assert plain_note("doc_7e7be1abff and doc_0123456789 could not be read.", documents) == (
        '"Dexcom community post" and a source document could not be read.'
    )


def test_a_plain_note_is_left_alone() -> None:
    note = "Whether the criteria apply across all DME MAC jurisdictions was not confirmed."
    assert plain_notes([note]) == [note]


def test_the_fixed_notes_have_no_engineer_words() -> None:
    for note in (STOPPED_NOTE, STOPPED_ON_ERROR_NOTE, DEADLINE_NOTE):
        assert not ENGINEER.search(note), note
        assert plain_notes([note]) == [note]

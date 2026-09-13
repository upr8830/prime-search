"""SearchBench loading and drift detection (docs/08 §2, docs/05 §1).

The drift checks are the point of task 1.8, and two of them were wrong on their first
live run in ways that would have corrupted the answer keys during task 2.1's human
pass — a check that reports drift where there is none is worse than no check, because a
human acting on it edits a correct key into a wrong one. Those two cases are pinned
first.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from eval.searchbench import load_records
from eval.searchbench.fetch_sources import (
    Resolution,
    _distinctive_phrases,
    _has_operative_match,
    _mcd_url,
    _slugify,
    check_authoring,
    check_dates,
    check_forbidden,
    check_key_phrases,
    check_resolution,
    resolve,
)
from eval.searchbench.schema import SPLIT_SIZES, AnswerKey, BenchRecord
from prime_search.schemas import Document

# The exact shape of L33822's revision history, which is what broke the first version
# of the forbidden-claim check: CMS quotes the text it removed, verbatim.
REVISION_HISTORY = (
    "Revision Effective Date: 04/16/2023\n"
    "COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY:\n"
    'Removed: "with multiple (three or more) daily administrations of insulin or a '
    'continuous subcutaneous insulin infusion (CSII) pump" from CGM coverage criterion\n'
)
OPERATIVE = (
    "The beneficiary has a history of problematic hypoglycemia with documentation.\n"
    "The beneficiary is insulin-treated; or,\n"
)


def _document(**kwargs) -> Document:
    payload = {
        "doc_id": "doc_lcd",
        "url": "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822",
        "title": "LCD - Glucose Monitors (L33822)",
        "source_tier": "primary_policy",
        "publisher": "CMS",
        "doc_type": "LCD",
        "document_id_external": "L33822",
        "revision_date": date(2024, 10, 1),
        "retrieved_at": datetime.now(UTC),
        "text_path": "",
        "paragraph_count": 275,
        "fetch_method": "extract",
    }
    payload.update(kwargs)
    return Document(**payload)


def _record(**kwargs) -> BenchRecord:
    key = {
        "summary": "s",
        "required_claims": [],
        "required_evidence": [],
        "governing_documents": ["L33822"],
        "forbidden_claims": [],
        "sources": [],
    }
    key.update(kwargs.pop("answer_key", {}))
    payload = {
        "id": "cgm-elig-001",
        "domain": "cgm",
        "tier": 2,
        "question_type": "eligibility",
        "question": "q",
        "split": "train",
        "answer_key": key,
    }
    payload.update(kwargs)
    return BenchRecord.model_validate(payload)


def _resolved(descriptor: str = "L33822", **kwargs) -> dict[str, Resolution]:
    resolution = Resolution(descriptor, kwargs.pop("method", "id"), url="https://x")
    resolution.document = kwargs.pop("document", _document())
    for name, value in kwargs.items():
        setattr(resolution, name, value)
    return {descriptor: resolution}


# --- the two checks that were wrong on their first live run -------------------------


def test_a_removal_notice_is_not_evidence_the_text_is_still_operative() -> None:
    """L33822's Revision History quotes what it removed, so a plain substring test finds
    "three or more" in a document that no longer requires it. The first live run flagged
    `cgm-elig-001` f1 as drift when the draft was right — and a human acting on that
    would have edited a correct key into a wrong one."""
    record = _record(
        answer_key={
            "forbidden_claims": [
                {
                    "id": "f1",
                    "text": 'Multiple daily injections ("three or more") are required',
                    "reason": "requirement removed by the 2023 revision",
                }
            ]
        }
    )
    flags = check_forbidden(record, _resolved(), {"l33822": REVISION_HISTORY + OPERATIVE})
    assert flags == []


def test_the_same_phrase_in_operative_text_is_flagged() -> None:
    """The check still has to fire when a supposedly retired requirement is live."""
    record = _record(
        answer_key={
            "forbidden_claims": [
                {
                    "id": "f1",
                    "text": 'The beneficiary must be ("insulin-treated")',
                    "reason": "the draft believes this was dropped",
                }
            ]
        }
    )
    flags = check_forbidden(record, _resolved(), {"l33822": OPERATIVE})
    assert len(flags) == 1
    assert flags[0].kind == "forbidden"
    assert "insulin-treated" in flags[0].detail


def test_operative_match_scans_every_occurrence() -> None:
    """One occurrence inside a removal notice must not mask another in live text."""
    assert not _has_operative_match(REVISION_HISTORY, "three or more")
    assert _has_operative_match(REVISION_HISTORY + "The pump must deliver three or more.", "three or more")
    assert _has_operative_match(OPERATIVE, "insulin-treated")


def test_evidence_naming_a_document_outside_governing_documents_is_a_key_defect() -> None:
    """Measured on `glp1-path-001`: `e1` cites `Section 1927(d)(2)(A)` while
    `governing_documents` holds only a CMS guidance descriptor, so the statute would
    never be fetched. That is a broken key, not a failed fetch, and the two need
    different fixes."""
    record = _record(
        answer_key={
            "governing_documents": ["CMS March 2024 Part D guidance"],
            "required_evidence": [
                {
                    "id": "e1",
                    "document_id_external": "Section 1927(d)(2)(A)",
                    "doc_type": "Statute",
                    "key_phrases": ["weight loss"],
                    "must": False,
                }
            ],
        }
    )
    flags = check_key_phrases(record, {}, {})
    assert len(flags) == 1
    assert "not in governing_documents" in flags[0].detail
    assert "not fetched" not in flags[0].detail


# --- the dataset --------------------------------------------------------------------


def test_every_shipped_record_validates() -> None:
    """The file is hand-edited during task 2.1; a typo should fail here, naming the
    line and the record, rather than surfacing as an evaluator failure on Day 2."""
    records = load_records()
    assert len(records) == 30
    assert len({r.id for r in records}) == 30


def test_the_splits_match_the_spec() -> None:
    """docs/08 §6: train 15, dev 5, holdout 10."""
    records = load_records()
    for split, expected in SPLIT_SIZES.items():
        assert sum(1 for r in records if r.split == split) == expected


def test_every_shipped_key_is_still_a_draft() -> None:
    """docs/08 §9. If this ever fails, someone validated keys and this test should be
    the thing that notices."""
    assert all(not r.answer_key.is_validated for r in load_records())


def test_the_authoring_check_catches_an_out_of_scope_record_with_evidence() -> None:
    """docs/08 §4: "Out-of-scope questions must have an `expected_scope_warning` and no
    `required_evidence`". Requiring evidence for a question the system should decline
    asks it to research and refuse at the same time."""
    record = _record(
        question_type="out_of_scope",
        domain="other",
        answer_key={
            "expected_scope_warning": "This is outside Medicare coverage policy.",
            "required_evidence": [
                {
                    "id": "e1",
                    "document_id_external": "L33822",
                    "doc_type": "LCD",
                    "key_phrases": [],
                    "must": False,
                }
            ],
        },
    )
    flags = check_authoring(record)
    assert all(f.kind == "authoring" for f in flags)
    assert any("no required_evidence" in f.detail for f in flags)


def test_a_missing_scope_warning_is_flagged() -> None:
    record = _record(question_type="out_of_scope", domain="other")
    assert any("expected_scope_warning" in f.detail for f in check_authoring(record))


def test_the_shipped_dataset_authoring_violations_are_known() -> None:
    """Documents the state 1.8 found, rather than asserting the drafts are clean.

    `fetch_sources` is forbidden from editing the keys (docs/08 §1's provenance
    argument), so every one of these is task 2.1's to fix — and this test is what says
    when they are. The PHI one is the serious one: CLAUDE.md's "no patient records, not
    even synthetic" is a hard constraint, not a style rule.
    """
    from eval.searchbench.fetch_sources import check_authoring

    found = {
        record.id: sorted(flag.detail for flag in check_authoring(record))
        for record in load_records()
        if check_authoring(record)
    }
    assert set(found) == {
        "oos-002",     # required_evidence on an out-of-scope record, plus PHI
        "oos-003",     # required_evidence, no scope warning, and only 1 required claim
        "chg-cgm-002", "chg-glp1-001",  # change-detection keys that date nothing
    }, f"authoring violations changed: {sorted(found)}"
    assert any("patient-level detail" in d for d in found["oos-002"])


def test_a_question_carrying_patient_detail_is_flagged() -> None:
    """CLAUDE.md: "No PHI, no patient records, not even synthetic." An out-of-scope
    record testing that the system declines individual questions can do that without a
    name, a date of birth and a lab value."""
    from eval.searchbench.fetch_sources import _patient_details

    assert _patient_details("My patient Placeholder, DOB 1/1/1900, A1c 9.9, on metformin")
    # A policy population is not a patient, and must not be flagged.
    assert _patient_details("Is a CGM covered for a type 2 diabetic not on insulin?") == []
    assert _patient_details("What A1c threshold applies to CGM coverage?") == []


# --- resolution ---------------------------------------------------------------------


def test_a_url_in_the_record_wins_over_a_search(monkeypatch) -> None:
    """Deterministic beats a guess; 19 of 30 records carry their document's URL."""
    from prime_search.primitives import tavily

    monkeypatch.setattr(
        tavily, "search", lambda *a, **k: pytest.fail("should not have searched")
    )
    key = AnswerKey(
        summary="",
        sources=["https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"],
    )
    resolution = resolve("L33822", key)
    assert resolution.method == "record_url"
    assert not resolution.needs_review or resolution.document is None


def test_an_mcd_id_resolves_without_a_search(monkeypatch) -> None:
    from prime_search.primitives import tavily

    monkeypatch.setattr(tavily, "search", lambda *a, **k: pytest.fail("should not search"))
    assert resolve("L33822", AnswerKey(summary="")).method == "id"
    assert resolve("A52464", AnswerKey(summary="")).method == "id"


def test_mcd_urls_are_built_from_the_id() -> None:
    assert "lcdid=33822" in _mcd_url("L33822")
    assert "articleId=52464" in _mcd_url("A52464")
    assert _mcd_url("FDA Wegovy label") is None
    assert _mcd_url("SSA 1927(d)(2)(A)") is None


def test_a_prose_descriptor_is_searched_and_marked_a_guess(monkeypatch) -> None:
    """11 of 30 records name their governing document only in prose. The top hit is a
    guess and the output has to say so - "CMS/HHS 2025 announcements" has no canonical
    document, and presenting whatever Tavily returned as governing text would be the
    mistake the bench exists to catch."""
    from eval.searchbench import fetch_sources
    from prime_search.primitives.tavily import SearchHit, SearchResult

    hits = [
        SearchHit("d1", "https://example.com/x", "blog", "s", "web", None, 0.9),
        SearchHit("d2", "https://www.cms.gov/x", "CMS", "s", "official_secondary", None, 0.2),
    ]
    monkeypatch.setattr(
        fetch_sources.tavily, "search", lambda *a, **k: SearchResult("q", hits=hits)
    )
    resolution = resolve("CMS/HHS 2025 announcements", AnswerKey(summary=""))

    assert resolution.method == "search"
    assert resolution.needs_review
    # Tier beats score: an official page outranks a higher-scoring blog.
    assert resolution.url == "https://www.cms.gov/x"


def test_a_search_that_finds_nothing_is_unresolved_not_a_crash(monkeypatch) -> None:
    from eval.searchbench import fetch_sources
    from prime_search.primitives.tavily import SearchResult

    monkeypatch.setattr(fetch_sources.tavily, "search", lambda *a, **k: SearchResult("q"))
    resolution = resolve("CMS 2026 announcements", AnswerKey(summary=""))
    assert resolution.method == "unresolved"
    assert resolution.needs_review

    record = _record(answer_key={"governing_documents": ["CMS 2026 announcements"]})
    flags = check_resolution(record, {"CMS 2026 announcements": resolution})
    assert len(flags) == 1 and flags[0].kind == "resolution"


def test_offline_never_touches_the_network(monkeypatch) -> None:
    from eval.searchbench import fetch_sources

    monkeypatch.setattr(
        fetch_sources.tavily, "search", lambda *a, **k: pytest.fail("offline searched")
    )
    assert resolve("FDA Wegovy label", AnswerKey(summary=""), offline=True).method == "unresolved"


# --- dates and phrases --------------------------------------------------------------


def test_a_stale_date_in_the_draft_is_reported_against_the_live_one() -> None:
    """docs/08 §2's worked example, and the headline finding of the first run: the
    draft asserts April 16, 2023 six times; L33822 is on 2024-10-01."""
    record = _record(
        answer_key={
            "summary": "The non-insulin pathway was added April 16, 2023.",
            "governing_documents": ["L33822"],
        }
    )
    flags = check_dates(record, _resolved(), {})
    assert len(flags) == 1
    assert "2024-10-01" in flags[0].detail and "2023-04-16" in flags[0].detail


def test_all_three_date_spellings_in_the_seed_file_are_read() -> None:
    for text in ("April 16, 2023", "2023-04-16", "04/16/2023"):
        record = _record(answer_key={"summary": f"Effective {text}."})
        assert check_dates(record, _resolved(), {}) != [], text


def test_a_draft_date_that_matches_the_live_document_is_not_flagged() -> None:
    record = _record(answer_key={"summary": "Revised 2024-10-01."})
    assert check_dates(record, _resolved(), {}) == []


def test_a_key_without_dates_is_not_flagged() -> None:
    assert check_dates(_record(), _resolved(), {}) == []


def test_a_missing_key_phrase_is_flagged() -> None:
    """Measured: the draft puts "level 2"/"level 3" on L33822, but the LCD defers the
    definition to article A52464 and contains neither phrase."""
    record = _record(
        answer_key={
            "required_evidence": [
                {
                    "id": "e1",
                    "document_id_external": "L33822",
                    "doc_type": "LCD",
                    "key_phrases": ["problematic hypoglycemia", "level 2"],
                    "must": True,
                }
            ]
        }
    )
    flags = check_key_phrases(record, _resolved(), {"l33822": OPERATIVE})
    assert len(flags) == 1
    assert "level 2" in flags[0].detail
    assert "problematic hypoglycemia" not in flags[0].detail  # that one is present


def test_key_phrase_matching_ignores_case() -> None:
    record = _record(
        answer_key={
            "required_evidence": [
                {
                    "id": "e1",
                    "document_id_external": "L33822",
                    "doc_type": "LCD",
                    "key_phrases": ["INSULIN-TREATED"],
                    "must": True,
                }
            ]
        }
    )
    assert check_key_phrases(record, _resolved(), {"l33822": OPERATIVE}) == []


def test_only_quoted_or_parenthesised_wording_is_matched() -> None:
    """A whole sentence never appears verbatim in a policy document, so matching on one
    would flag nothing; the seed file quotes the superseded wording."""
    assert _distinctive_phrases('Injections ("three or more") are required') == ["three or more"]
    assert _distinctive_phrases("No quoted fragment here at all") == []


def test_slugs_are_filesystem_safe() -> None:
    assert _slugify("SSA 1927(d)(2)(A)") == "ssa-1927-d-2-a"
    assert _slugify("CMS/HHS 2025 announcements") == "cms-hhs-2025-announcements"
    assert len(_slugify("x" * 200)) <= 60


# --- the contract that matters most -------------------------------------------------


def test_the_dataset_file_is_never_written(monkeypatch, tmp_path: Path) -> None:
    """docs/08 §1: keys are data with provenance. A script that corrected the file it
    is auditing would erase what the draft claimed. Correcting keys is task 2.1, by
    hand."""
    from eval.searchbench.schema import DATASET

    before = DATASET.read_bytes()
    record = _record(answer_key={"summary": "Effective April 16, 2023."})
    check_dates(record, _resolved(), {})
    check_key_phrases(record, _resolved(), {"l33822": OPERATIVE})
    check_forbidden(record, _resolved(), {"l33822": OPERATIVE})
    check_resolution(record, _resolved())
    assert DATASET.read_bytes() == before


# --- regressions from the 1.8 spec review -------------------------------------------


def test_a_key_phrase_is_checked_against_this_records_document_only() -> None:
    """`resolutions` is the run-wide map. An exact-key lookup matched a document another
    record had named: `glp1-path-001`'s e2 hit a premium fact sheet resolved for
    `adv-glp1-002`, and the report then said the correct statutory term was missing from
    a document that record never names — while suppressing the flag that should fire."""
    record = _record(
        answer_key={
            "governing_documents": ["CMS March 2024 Part D guidance on anti-obesity"],
            "required_evidence": [
                {
                    "id": "e2",
                    "document_id_external": "CMS 2024 Part D guidance",
                    "doc_type": "Guidance",
                    "key_phrases": ["medically accepted indication"],
                    "must": True,
                }
            ],
        }
    )
    # A *different* record's descriptor is in the run-wide map and must not be used.
    other = Resolution("CMS 2024 Part D guidance", "search", url="https://other")
    other.document = _document(doc_id="doc_other", document_id_external=None)

    flags = check_key_phrases(record, {"CMS 2024 Part D guidance": other}, {"doc_other": ""})
    assert len(flags) == 1
    assert "not in governing_documents" in flags[0].detail


def test_a_date_still_in_the_revision_history_is_not_called_drift() -> None:
    """`cgm-elig-001` c3 says the non-insulin pathway "was added by the revision
    effective April 16, 2023". That is correct — the 2023 row is still in L33822's
    revision history — yet the flag read "draft expected 2023-04-16", which invites a
    reviewer to overwrite a right answer."""
    record = _record(
        answer_key={"summary": "The pathway was added April 16, 2023."},
    )
    history = "Revision Effective Date: 04/16/2023\nAdded: the hypoglycemia criterion\n"
    flags = check_dates(record, _resolved(), {"l33822": history})

    assert len(flags) == 1
    assert "still in the document's revision history" in flags[0].detail
    assert "which does not appear in the document at all" not in flags[0].detail


def test_a_date_absent_from_the_document_is_still_drift() -> None:
    record = _record(answer_key={"summary": "Effective January 2, 2019."})
    flags = check_dates(record, _resolved(), {"l33822": "no such date here"})
    assert len(flags) == 1
    assert "does not appear in the document at all" in flags[0].detail


def test_month_precision_dates_count_as_dating_a_change() -> None:
    """`chg-glp1-002` says "the November 2024 proposed rule" and "the April 2025 final
    rule"; checking only day-precision dates reported those keys as dateless."""
    from eval.searchbench.fetch_sources import _any_date_in

    record = _record(
        question_type="change_detection",
        answer_key={"summary": "CMS did not finalize it in the April 2025 final rule."},
    )
    assert _any_date_in(record.answer_key)
    assert not any("with dates" in f.detail for f in check_authoring(record))
    # ...but a month is not comparable to a revision date, so it is not asserted as one.
    assert check_dates(record, _resolved(), {}) == []


def test_a_forbidden_claim_with_nothing_quotable_says_so() -> None:
    """9 of the 10 shipped forbidden claims are plain sentences, so the check was
    silently inert for almost all of them while the report's legend implied it ran. A
    record reported "no drift detected" whose only real assertion was never tested is
    worse than one reported as unchecked."""
    record = _record(
        answer_key={
            "forbidden_claims": [
                {"id": "f1", "text": "Bill CGM supplies with K0553", "reason": "retired"}
            ]
        }
    )
    flags = check_forbidden(record, _resolved(), {"l33822": OPERATIVE})
    assert len(flags) == 1
    assert "could not be checked automatically" in flags[0].detail


def test_a_retired_code_still_in_the_document_is_flagged() -> None:
    """The check `forbidden_claims` could not make: `cgm-code-001` calls K0553/K0554
    retired, and they appear 19 and 16 times in the live A52464."""
    from eval.searchbench.fetch_sources import check_codes

    record = _record(
        answer_key={
            "forbidden_claims": [
                {"id": "f1", "text": "Bill CGM supplies with K0553", "reason": "retired"}
            ]
        }
    )
    flags = check_codes(record, _resolved(), {"l33822": "Use K0553 for the supply allowance."})
    assert any("still appears in the live document" in f.detail for f in flags)


def test_a_code_the_key_asserts_but_the_document_lacks_is_flagged() -> None:
    record = _record(
        answer_key={
            "required_claims": [{"id": "c1", "text": "Bill with E2103", "must": True}]
        }
    )
    from eval.searchbench.fetch_sources import check_codes

    flags = check_codes(record, _resolved(), {"l33822": "nothing about that code"})
    assert any("E2103" in f.detail and "absent" in f.detail for f in flags)


def test_flags_say_when_the_document_was_only_a_search_guess() -> None:
    """Five key_phrase flags were computed against `method: search` documents with no
    signal in the report that the text searched was a guess."""
    guess = Resolution("CMS 2026 announcements", "search", url="https://x")
    guess.document = _document(doc_id="doc_guess")
    record = _record(
        answer_key={
            "governing_documents": ["CMS 2026 announcements"],
            "required_evidence": [
                {
                    "id": "e1",
                    "document_id_external": "CMS 2026 announcements",
                    "doc_type": "Guidance",
                    "key_phrases": ["GLP-1"],
                    "must": True,
                }
            ],
        }
    )
    flags = check_key_phrases(record, {"CMS 2026 announcements": guess}, {"doc_guess": ""})
    assert "resolved by search" in flags[0].detail


def test_text_added_by_a_revision_row_is_not_treated_as_removed() -> None:
    """CMS renders a whole revision row on one line: `Removed: "..." ... Added: "..."`.
    Asking only whether "Removed" appears before the match treated text the same row
    *added* as retired — the mirror image of the bug the line-scoping fixed."""
    row = (
        'Removed: "with multiple (three or more) daily administrations" from the '
        'criterion Added: "history of problematic hypoglycemia" as a criterion\n'
    )
    assert not _has_operative_match(row, "three or more")
    assert _has_operative_match(row, "history of problematic hypoglycemia")


def test_patient_detail_is_redacted_before_it_reaches_an_artifact() -> None:
    """Flagging oos-002 for carrying a name, a DOB and an A1c while copying that string
    into a new worksheet and a new report — both committed — would spread what
    CLAUDE.md forbids across three files instead of one."""
    from eval.searchbench.fetch_sources import redact

    # Deliberately NOT the dataset's own string. Copying `oos-002`'s question into a
    # test to prove it gets redacted would put the record in a third committed file —
    # the mistake this function exists to stop. The shape is what matters.
    out = redact("My patient Placeholder, DOB 1/1/1900, A1c 9.9, on metformin only")
    assert "Placeholder" not in out and "1/1/1900" not in out and "9.9" not in out
    assert "redacted" in out
    # A policy question is passed through untouched.
    plain = "Is a CGM covered for a type 2 diabetic not on insulin?"
    assert redact(plain) == plain


def test_the_orchestration_runs_offline_and_writes_nothing(tmp_path, monkeypatch, capsys) -> None:
    """`--offline` on a working tree used to overwrite index.json, all 30 worksheets and
    the drift report with empty content: it fetches nothing, so every passage and check
    comes back blank while the files look freshly generated."""
    from eval.searchbench import fetch_sources

    monkeypatch.setattr(fetch_sources, "SOURCES_DIR", tmp_path / "sources")
    monkeypatch.setattr(fetch_sources, "REVIEW_DIR", tmp_path / "review")
    monkeypatch.setattr(fetch_sources, "REPORT_PATH", tmp_path / "drift.md")
    monkeypatch.setattr(
        fetch_sources.tavily, "search", lambda *a, **k: pytest.fail("offline searched")
    )

    flags, resolutions = fetch_sources.run(only="cgm-elig-001", offline=True)

    assert flags, "an offline run still reports what it can check"
    assert resolutions
    assert not (tmp_path / "sources").exists() or not list((tmp_path / "sources").iterdir())
    assert not (tmp_path / "review").exists() or not list((tmp_path / "review").iterdir())
    assert not (tmp_path / "drift.md").exists()
    assert "no files written" in capsys.readouterr().out


def test_the_written_source_is_byte_identical_to_the_fetched_text(tmp_path, monkeypatch) -> None:
    """The stated reason for keeping metadata out of the .txt and for the
    `data/searchbench/sources/** -text` gitattributes rule: an answer key is validated
    against exact passages, so a rewritten byte shifts every offset a citation names."""
    from eval.searchbench import fetch_sources

    text = "Line one.\nLine two with a \u2019 curly quote.\nLine three.\n"
    source = tmp_path / "doc.txt"
    source.write_text(text, encoding="utf-8", newline="")

    monkeypatch.setattr(fetch_sources, "SOURCES_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir()
    resolution = Resolution("L33822", "id", url="https://x")
    resolution.document = _document(text_path=str(source))

    written = fetch_sources._write_sources({"L33822": resolution})
    on_disk = (tmp_path / "out" / "l33822.txt").read_text(encoding="utf-8", newline="")

    assert written["l33822"] == text
    assert on_disk == text


def test_the_index_records_what_the_spec_asks_for(tmp_path, monkeypatch) -> None:
    """docs/08 §2 step 2: store the text "with retrieval date and revision date"."""
    import json

    from eval.searchbench import fetch_sources

    monkeypatch.setattr(fetch_sources, "SOURCES_DIR", tmp_path)
    resolution = Resolution("L33822", "record_url", url="https://x")
    resolution.document = _document()
    resolution.used_by = ["cgm-elig-001", "cross-001"]

    fetch_sources._write_index({"L33822": resolution})
    entry = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))["documents"][0]

    assert entry["retrieved_at"] and entry["revision_date"] == "2024-10-01"
    assert entry["method"] == "record_url" and entry["needs_review"] is False
    assert entry["used_by"] == ["cgm-elig-001", "cross-001"]
    assert entry["text_file"] == "l33822.txt"

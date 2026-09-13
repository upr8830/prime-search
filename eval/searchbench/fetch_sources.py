"""Fetch SearchBench's governing documents and report where the draft keys drifted.

    uv run --env-file .env python -m eval.searchbench.fetch_sources

This is step 2 of `docs/08` §2. Step 3 — a human correcting the keys against what this
produces — is task 2.1, and is the reason every output here is written for a reader
rather than for a program.

**Nothing here writes to `searchbench_v0.jsonl`.** `docs/08` §1's whole argument is that
answer keys are data with provenance; a script that silently corrected the file it is
auditing would erase the record of what the draft claimed and who changed it. The keys
change in one place, by hand, in task 2.1.

What it produces:

* `data/searchbench/sources/<slug>.txt` — the document text, byte-identical to what was
  fetched, plus `index.json` with the metadata and how each document was resolved
* `data/searchbench/review/<record_id>.md` — a worksheet per record: the draft key, and
  under each required claim and key phrase the passages from the live document that bear
  on it (`docs/08` §2 step 3: "reads the fetched source passages that `fetch_sources`
  highlighted")
* `reports/searchbench-drift.md` and a console summary — every place the live sources
  and the draft disagree

The drift report is the deliverable. `docs/08` §2 says finding that a draft key is wrong
"is expected and is a line for the technical statement", so the checks are written to
surface disagreement loudly rather than to produce a clean run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from eval.searchbench.schema import DATASET, AnswerKey, BenchRecord, load_records
from prime_search.config import get_settings
from prime_search.primitives import sources, tavily, within
from prime_search.schemas import Document
from prime_search.tracing import configure_logging, get_logger

_log = get_logger(component="fetch_sources")

SOURCES_DIR = Path("data/searchbench/sources")
REVIEW_DIR = Path("data/searchbench/review")
REPORT_PATH = Path("reports/searchbench-drift.md")

# docs/08 §2: "Tavily search restricted to cms.gov, MAC domains, fda.gov" — which is
# exactly `sources.PRIMARY_DOMAINS` (docs/01 §5's allow-list).
#
# `ssa.gov` is added **here and not to that list**. Two records name `SSA 1927(d)(2)(A)`
# as governing and the Social Security Act compilation is where Part D's statutory
# exclusions actually live, so this task needs it — but `PRIMARY_DOMAINS` is the
# `include_domains` every production search uses (`smoke.py`, the 1.6 sub-agent tools,
# `eval/model_select.py`), and docs/01 §5 pins that list. Widening the runtime filter as
# a side effect of a bench-fetching task is a change nobody asked for.
SEARCH_DOMAINS = sorted({*sources.PRIMARY_DOMAINS, "ssa.gov"})

# Passages kept per claim in a review worksheet. Three is enough to judge a claim and
# short enough that a 6-claim record stays readable in one screen.
PASSAGES_PER_CLAIM = 3
MAX_PASSAGE_CHARS = 600

# The dataset README names these as highest drift risk; the report leads with them so
# task 2.1's ~3 minutes per question are spent where the risk is.
HIGH_RISK = (
    "glp1-path-005", "chg-glp1-001", "chg-glp1-003",
    "chg-cgm-002", "cgm-code-004", "cgm-code-001",
)

# CMS Medicare Coverage Database ids resolve to a URL by pattern; everything else does
# not, which is the central difficulty of this task (11 of 30 records name their
# governing document only in prose).
_LCD = re.compile(r"^L(\d{4,6})$")
_ARTICLE = re.compile(r"^A(\d{4,6})$")

# Dates asserted inside a draft key, in the three shapes the seed file uses.
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_DATE_PATTERNS = (
    re.compile(rf"\b({_MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),
)
# "November 2024 proposed rule" — month precision, which four change-detection keys use
# and which the day-requiring patterns above missed entirely. Tracked separately: a
# month is not comparable to a document's revision date, but it *is* a date for the
# purpose of docs/08 §4's "the key lists the changes with dates".
_MONTH_YEAR = re.compile(rf"\b({_MONTHS})\s+(\d{{4}})\b")

_MONTH_NUMBER = {
    name: index
    for index, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        start=1,
    )
}


@dataclass
class Resolution:
    """How one `governing_documents` entry became a URL, and how much to trust it.

    The method matters more than the URL. `record_url` and `id` are deterministic; a
    `search` result is the top hit for a prose descriptor and is a *guess* — "CMS/HHS
    2025 announcements" has no canonical document, and presenting whatever Tavily
    returned as the governing text would be the same mistake the whole bench exists to
    catch.
    """

    descriptor: str
    method: str  # url | record_url | id | search | unresolved
    url: str | None = None
    query: str | None = None
    document: Document | None = None
    error: str | None = None
    used_by: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.method in {"search", "unresolved"} or self.document is None

    @property
    def slug(self) -> str:
        return _slugify(self.descriptor)

    def as_json(self) -> dict[str, object]:
        document = self.document
        return {
            "descriptor": self.descriptor,
            "method": self.method,
            "needs_review": self.needs_review,
            "url": self.url,
            "query": self.query,
            "error": self.error,
            "used_by": sorted(self.used_by),
            "text_file": f"{self.slug}.txt" if document else None,
            "title": document.title if document else None,
            "source_tier": document.source_tier if document else None,
            "publisher": document.publisher if document else None,
            "document_id_external": document.document_id_external if document else None,
            "revision_date": _iso(document.revision_date) if document else None,
            "effective_date": _iso(document.effective_date) if document else None,
            "paragraph_count": document.paragraph_count if document else 0,
            "fetch_method": document.fetch_method if document else None,
            "retrieved_at": _iso(document.retrieved_at) if document else None,
        }


@dataclass
class Flag:
    """One disagreement between a draft key and the live sources."""

    record_id: str
    kind: str  # date | key_phrase | forbidden | resolution
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.detail}"


# --- resolution -------------------------------------------------------------------


def resolve(descriptor: str, key: AnswerKey, *, offline: bool = False) -> Resolution:
    """Turn one `governing_documents` entry into a URL (docs/08 §2 step 2)."""
    external = descriptor.strip()

    # 0. A canonical URL. docs/08 §5 allows "external ids or canonical URLs"; without
    #    this a corrected key naming its document by URL could never clear the flag.
    if external.lower().startswith(("http://", "https://")):
        return Resolution(external, "url", url=external)

    # 1. A URL the record already carries, when it plainly names this document.
    for url in key.sources:
        if _url_names(url, external):
            return Resolution(external, "record_url", url=url)

    # 2. A Medicare Coverage Database id.
    if (canonical := _mcd_url(external)) is not None:
        return Resolution(external, "id", url=canonical)

    # 3. A prose descriptor. Searched, and flagged as a guess.
    if offline:
        return Resolution(external, "unresolved", error="offline: search skipped")
    query = _search_query(external)
    try:
        result = tavily.search(query, include_domains=SEARCH_DOMAINS, max_results=5)
    except Exception as exc:  # noqa: BLE001 - one unresolvable document is a flag, not a crash
        return Resolution(external, "unresolved", query=query, error=f"{type(exc).__name__}: {exc}")
    if result.error or not result.hits:
        return Resolution(
            external, "unresolved", query=query, error=result.error or "no results"
        )
    best = max(result.hits, key=lambda hit: (sources.tier_rank(hit.tier), hit.score))
    return Resolution(external, "search", url=best.url, query=query)


def _url_names(url: str, external: str) -> bool:
    """Does this URL plainly identify this document? `L33822` -> `...lcdid=33822`."""
    lowered = url.lower()
    if (match := _LCD.match(external)) is not None:
        return f"lcdid={match.group(1)}" in lowered
    if (match := _ARTICLE.match(external)) is not None:
        return f"articleid={match.group(1)}" in lowered
    return False


def _mcd_url(external: str) -> str | None:
    if (match := _LCD.match(external)) is not None:
        return f"https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid={match.group(1)}"
    if (match := _ARTICLE.match(external)) is not None:
        return (
            "https://www.cms.gov/medicare-coverage-database/view/article.aspx"
            f"?articleId={match.group(1)}"
        )
    return None


def _search_query(descriptor: str) -> str:
    """The descriptor, lightly shaped into a query.

    Left close to the author's words on purpose: rewriting "CMS/HHS 2025 announcements"
    into something that retrieves well would hide how vague the draft key is, and that
    vagueness is itself a finding for task 2.1.
    """
    cleaned = descriptor.replace("/", " ").strip()
    if cleaned.upper().startswith("SSA "):  # a statute citation
        return f"Social Security Act {cleaned[4:]} text"
    return cleaned


# --- drift checks -----------------------------------------------------------------


def check_dates(
    record: BenchRecord, resolutions: dict[str, Resolution], texts: dict[str, str]
) -> list[Flag]:
    """docs/08 §2's worked example: "L33822 revision date found: … — draft expected
    2023-04-16".

    The wording matters more than the comparison. A draft key that says "the non-insulin
    pathway was added by the revision effective April 16, 2023" is **correct** even
    though the document's current revision is 2024-10-01 — the 2023 row is still in the
    revision history. Reporting that as "draft expected 2023-04-16" invites a reviewer
    with three minutes per record to overwrite a right answer with a wrong one, so a
    date the document still carries is reported as a *currency* note and a date it has
    never carried as drift.
    """
    asserted = _dates_in(record.answer_key)
    if not asserted:
        return []
    flags: list[Flag] = []
    governing_texts: list[str] = []
    carried: set[date] = set()
    program_documents = 0
    for descriptor in record.answer_key.governing_documents:
        resolution = resolutions.get(descriptor)
        document = resolution.document if resolution else None
        if document is None:
            continue
        text = texts.get(resolution.slug, "")
        governing_texts.append(text)
        if document.document_id_external is None:
            # A press release or fact sheet has no revision history for a key's dates to
            # live in: "$50 per month beginning July 1, 2026" is a program date, and
            # comparing it with the page's revision date reported a key whose every date
            # is verbatim in the page as drift. Checked for presence below instead.
            program_documents += 1
            continue
        caveat = _guess_caveat(resolution)
        live = document.revision_date or document.effective_date
        if live is not None:
            carried.add(live)
        if live is None:
            flags.append(
                Flag(
                    record.id,
                    "date",
                    f"{descriptor}: draft asserts {_join(asserted)} but no revision or "
                    f"effective date could be extracted from the live document{caveat}",
                )
            )
            continue
        if live in asserted:
            continue
        still_present = sorted(d for d in asserted if _date_in_text(text, d))
        if still_present:
            flags.append(
                Flag(
                    record.id,
                    "date",
                    f"{descriptor} is now at {live.isoformat()}; the draft's "
                    f"{_join(still_present)} is still in the document's revision history, "
                    "so a claim *about that revision* is fine — check only that the key "
                    f"does not present it as current{caveat}",
                )
            )
            continue
        flags.append(
            Flag(
                record.id,
                "date",
                f"{descriptor} revision date found: {live.isoformat()} — "
                f"draft expected {_join(asserted)}, which does not appear in the "
                f"document at all{caveat}",
            )
        )
    if program_documents:
        missing = sorted(
            d
            for d in asserted
            if d not in carried and not any(_date_in_text(t, d) for t in governing_texts)
        )
        if missing:
            flags.append(
                Flag(
                    record.id,
                    "date",
                    f"draft asserts {_join(missing)}, which appears in none of its governing "
                    "documents — correct the date or add the document that establishes it",
                )
            )
    return flags


def _date_in_text(text: str, value: date) -> bool:
    """Does the document itself mention this date, in any of the shapes CMS uses?"""
    if not text:
        return False
    month = value.strftime("%B")
    candidates = (
        value.isoformat(),
        f"{value.month:02d}/{value.day:02d}/{value.year}",
        f"{value.month}/{value.day}/{value.year}",
        f"{month} {value.day}, {value.year}",
        f"{month} {value.day} {value.year}",
    )
    return any(candidate in text for candidate in candidates)


def _guess_caveat(resolution: Resolution | None) -> str:
    """Say when a flag was computed against a document the run only guessed at.

    Without this the report reads as though every `key_phrase` and `date` flag was
    checked against the governing text, when five of them were checked against the top
    search hit for a prose descriptor.
    """
    if resolution is not None and resolution.method == "search":
        return " [resolved by search - confirm the document before acting]"
    return ""


def check_key_phrases(
    record: BenchRecord, resolutions: dict[str, Resolution], texts: dict[str, str]
) -> list[Flag]:
    """A phrase the evaluator will look for that the live document does not contain is
    a broken key (docs/05 §2's `evidence_grounding` reads these)."""
    flags: list[Flag] = []
    for evidence in record.answer_key.required_evidence:
        resolution = _resolution_for(evidence.document_id_external, record, resolutions)
        if resolution is None:
            # Not a fetch problem: the key cites evidence from a document it never
            # lists as governing. Measured on `glp1-path-001`, whose `e1` names
            # `Section 1927(d)(2)(A)` while `governing_documents` holds only a CMS
            # guidance descriptor — so the statute would never be fetched for it.
            flags.append(
                Flag(
                    record.id,
                    "key_phrase",
                    f"{evidence.id} cites {evidence.document_id_external!r}, which is not "
                    "in governing_documents — add it there or correct the evidence",
                )
            )
            continue
        if resolution.document is None:
            flags.append(
                Flag(
                    record.id,
                    "key_phrase",
                    f"{evidence.id}: {evidence.document_id_external!r} was not fetched "
                    f"({resolution.error}), so its key phrases could not be checked",
                )
            )
            continue
        haystack = texts.get(resolution.slug, "").lower()
        missing = [phrase for phrase in evidence.key_phrases if phrase.lower() not in haystack]
        if missing:
            flags.append(
                Flag(
                    record.id,
                    "key_phrase",
                    f"{evidence.id} ({evidence.document_id_external}): "
                    f"{_join(missing)} not found in the live document"
                    f"{_guess_caveat(resolution)}",
                )
            )
    return flags


def check_forbidden(
    record: BenchRecord, resolutions: dict[str, Resolution], texts: dict[str, str]
) -> list[Flag]:
    """A `forbidden_claims` entry says the draft believes something is stale. If its
    distinctive wording is still **operative** in the live document, the draft may be
    wrong — which would make the bench penalise a correct answer.

    "Operative" is the whole difficulty. A CMS document's Revision History quotes the
    text it removed, verbatim and in full: L33822 contains `Removed: "with multiple
    (three or more) daily administrations of insulin..."`. A plain substring test
    therefore flags every correctly-retired requirement as still present — measured on
    the first run, which reported `cgm-elig-001` f1 as drift when the draft was right.
    A match inside a removal notice is evidence *for* the draft, so it is not a flag.
    """
    flags: list[Flag] = []
    slugs = [
        resolutions[d].slug for d in record.answer_key.governing_documents if d in resolutions
    ]
    for forbidden in record.answer_key.forbidden_claims:
        phrases = _distinctive_phrases(forbidden.text)
        if not phrases:
            # Said out loud rather than skipped. Measured: 9 of the 10 shipped forbidden
            # claims are plain sentences with nothing quotable — "Bill CGM supplies with
            # K0553" — so the check was silently inert for almost all of them while the
            # report's legend read as though the category had been evaluated. A record
            # reported as "no drift detected" whose only real assertion was never tested
            # is worse than one reported as unchecked.
            flags.append(
                Flag(
                    record.id,
                    "forbidden",
                    f"{forbidden.id} could not be checked automatically (no quoted "
                    f"wording or code to match): \"{forbidden.text}\" — verify by hand",
                )
            )
            continue
        operative = [
            phrase
            for phrase in phrases
            if any(_has_operative_match(texts.get(slug, ""), phrase) for slug in slugs)
        ]
        if operative:
            # Any operative phrase is worth reporting. Requiring all of them meant a
            # two-phrase claim with one live phrase was dropped entirely.
            scope = "" if len(operative) == len(phrases) else f" ({len(phrases)} checked)"
            flags.append(
                Flag(
                    record.id,
                    "forbidden",
                    f"{forbidden.id}: {_join(operative)} still appears in operative text"
                    f"{scope} — draft calls this stale ({forbidden.reason})",
                )
            )
    return flags


def check_codes(
    record: BenchRecord, resolutions: dict[str, Resolution], texts: dict[str, str]
) -> list[Flag]:
    """HCPCS/ICD codes a key asserts, against the live documents.

    `data/searchbench/README.md` promises "any date/code mismatches versus the draft"
    and only dates were compared. Codes are where a coding key goes stale fastest, and
    the dataset proves it: `cgm-code-001` calls `K0553`/`K0554` retired, yet they appear
    19 and 16 times in the live A52464 — exactly the check `forbidden_claims` could not
    make because the claim has no quoted wording.
    """
    flags: list[Flag] = []
    slugs = [
        resolutions[d].slug for d in record.answer_key.governing_documents if d in resolutions
    ]
    if not slugs:
        return flags
    corpus = " ".join(texts.get(slug, "") for slug in slugs)
    if not corpus:
        return flags

    asserted = _codes_in(_key_text(record.answer_key))
    missing = sorted(code for code in asserted if code not in corpus)
    if missing:
        flags.append(
            Flag(
                record.id,
                "code",
                f"{_join(missing)} asserted in the key but absent from the governing "
                "document(s) — confirm the code is current",
            )
        )
    # The mirror: a code the key says is retired that the document still uses.
    retired = {
        code
        for forbidden in record.answer_key.forbidden_claims
        for code in _codes_in(f"{forbidden.text} {forbidden.reason}")
    }
    still_used = sorted(code for code in retired if code in corpus)
    if still_used:
        flags.append(
            Flag(
                record.id,
                "code",
                f"{_join(still_used)} is called stale by a forbidden_claim but still "
                "appears in the live document — confirm before penalising an answer "
                "that uses it",
            )
        )
    return flags


# HCPCS level II (K0553, E2103, A4239) and ICD-10-CM (E11.10). Deliberately narrow so
# ordinary prose and section numbers are not mistaken for codes.
_CODE = re.compile(r"\b([A-Z]\d{4}|[A-Z]\d{2}\.\d{1,2})\b")


def _codes_in(text: str) -> set[str]:
    return set(_CODE.findall(text or ""))


# Words a CMS revision-history entry uses when it quotes text it has retired:
# `Removed: "with multiple (three or more) daily administrations of insulin..."`.
_REMOVAL_CONTEXT = re.compile(
    r"\b(removed|deleted|retired|superseded|struck)\b", re.IGNORECASE
)


def _has_operative_match(text: str, phrase: str) -> bool:
    """Does `phrase` appear somewhere that is not a removal notice?

    Scoped to what precedes the match **on its own line**, not a fixed window of
    characters. A window overlaps whatever came before: with 240 characters, a live
    sentence immediately following a revision-history entry inherited that entry's
    "Removed:" and was wrongly treated as retired. The grammar being matched is
    `Removed: "<quoted text>"`, so the keyword is always on the same line and ahead of
    the quote.
    """
    if not text or not phrase:
        return False
    lowered = text.lower()
    start = 0
    while (index := lowered.find(phrase, start)) != -1:
        line_start = text.rfind("\n", 0, index) + 1
        if not _in_removal_scope(text[line_start:index]):
            return True
        start = index + len(phrase)
    return False


def _in_removal_scope(prefix: str) -> bool:
    """Is the match governed by the nearest revision marker, and is that a removal?

    CMS renders a whole revision row on one line: `Removed: "..." ... Added: "..."`.
    Asking only whether "Removed" appears anywhere before the match meant text the same
    row *added* was treated as retired — the mirror image of the bug this scoping
    fixes. The nearest preceding marker wins, which is how the row actually reads.
    """
    markers = list(_REVISION_MARKER.finditer(prefix))
    return bool(markers) and _REMOVAL_CONTEXT.fullmatch(markers[-1].group(1)) is not None


# Every marker that opens a clause in a CMS revision row, not just the removing ones.
_REVISION_MARKER = re.compile(
    r"\b(Removed|Deleted|Retired|Superseded|Struck|Added|Revised|Clarified)\b:?",
    re.IGNORECASE,
)


def check_authoring(record: BenchRecord) -> list[Flag]:
    """docs/08 §4 and §5's authoring rules, which need no network at all.

    Worth checking because the seed keys were written by hand and one already breaks a
    rule: an `out_of_scope` record carries `required_evidence`, which §4 forbids — an
    out-of-scope answer is supposed to be a scope warning, so requiring evidence for it
    asks the system to research a question it should decline.
    """
    key = record.answer_key
    flags: list[Flag] = []
    if record.is_out_of_scope:
        if key.required_evidence:
            flags.append(
                Flag(
                    record.id,
                    "authoring",
                    "docs/08 §4: an out_of_scope record must have no required_evidence, "
                    f"but carries {_join(e.id for e in key.required_evidence)}",
                )
            )
        if not key.expected_scope_warning:
            flags.append(
                Flag(
                    record.id,
                    "authoring",
                    "docs/08 §4: an out_of_scope record must have an expected_scope_warning",
                )
            )
    if not 2 <= len(key.required_claims) <= 6:
        flags.append(
            Flag(
                record.id,
                "authoring",
                f"docs/08 §5: required_claims should be 2-6, found {len(key.required_claims)}",
            )
        )
    if (patient := _patient_details(record.question)) :
        # CLAUDE.md is unconditional: "No PHI, no patient records, not even synthetic."
        # docs/08 §8 repeats it ("Any patient-level inputs" — not included, deliberately).
        # An out-of-scope record testing that the system declines individual questions
        # can do that without a name, a date of birth and a lab value.
        flags.append(
            Flag(
                record.id,
                "authoring",
                f"the question embeds patient-level detail ({_join(patient)}); CLAUDE.md "
                "and docs/08 §8 forbid patient records, synthetic ones included — "
                "rephrase at policy level",
            )
        )
    if record.question_type == "change_detection" and not _any_date_in(key):
        flags.append(
            Flag(
                record.id,
                "authoring",
                "docs/08 §4: a change-detection key must list the changes with dates, "
                "but asserts none",
            )
        )
    return flags


def _any_date_in(key: AnswerKey) -> bool:
    """Does the key date its changes at all, to any precision?

    Month precision counts. `chg-glp1-002` says "the November 2024 proposed rule" and
    "the April 2025 final rule"; checking only day-precision dates reported those keys
    as dateless, which is false — and the same gap made `check_dates` skip the very
    records the dataset README calls highest drift risk.
    """
    return bool(_dates_in(key)) or bool(_MONTH_YEAR.search(_key_text(key)))


def check_resolution(record: BenchRecord, resolutions: dict[str, Resolution]) -> list[Flag]:
    flags: list[Flag] = []
    for descriptor in record.answer_key.governing_documents:
        resolution = resolutions.get(descriptor)
        if resolution is None or resolution.method == "unresolved":
            reason = resolution.error if resolution else "not attempted"
            flags.append(
                Flag(record.id, "resolution", f"{descriptor!r}: not resolved ({reason})")
            )
        elif resolution.document is None:
            flags.append(
                Flag(
                    record.id,
                    "resolution",
                    f"{descriptor!r}: resolved to {resolution.url} but the fetch failed "
                    f"({resolution.error})",
                )
            )
        elif resolution.method == "search":
            flags.append(
                Flag(
                    record.id,
                    "resolution",
                    f"{descriptor!r} has no canonical id; best search hit was "
                    f"{resolution.url} ({resolution.document.source_tier}) — confirm this "
                    "is the governing document",
                )
            )
    return flags


# --- the run ----------------------------------------------------------------------


def run(
    *, dataset: Path = DATASET, only: str | None = None, offline: bool = False
) -> tuple[list[Flag], dict[str, Resolution]]:
    """Resolve, fetch, highlight and report. Returns the flags and the resolutions."""
    records = load_records(dataset)
    if only:
        records = [r for r in records if r.id == only or r.domain == only or r.split == only]
    if not records:
        raise SystemExit(f"no records matched {only!r}")

    get_settings().export_sdk_env()
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    wanted: dict[str, list[str]] = defaultdict(list)
    for record in records:
        for descriptor in record.answer_key.governing_documents:
            wanted[descriptor].append(record.id)

    print(f"{len(records)} records, {len(wanted)} distinct governing documents\n")

    resolutions: dict[str, Resolution] = {}
    documents: dict[str, Document] = {}
    for descriptor, used_by in sorted(wanted.items()):
        resolution = resolve(descriptor, _merged_key(records, descriptor), offline=offline)
        resolution.used_by = used_by
        if resolution.url and offline:
            # Said explicitly, or the resolution check below reports a URL that resolved
            # fine as "the fetch failed (None)".
            resolution.error = "offline: fetch skipped"
        elif resolution.url:
            _fetch_into(resolution, documents)
        resolutions[descriptor] = resolution
        _print_resolution(resolution)

    # Offline resolves and checks but writes nothing. Without this guard, `--offline`
    # on a working tree overwrote index.json, all 30 worksheets and the drift report
    # with empty content: it fetches no documents, so every passage and every check
    # comes back blank while the files look freshly generated.
    texts = _write_sources(resolutions) if not offline else {}
    if not offline:
        _write_index(resolutions)

    flags: list[Flag] = []
    for record in records:
        record_flags = (
            check_authoring(record)
            + check_resolution(record, resolutions)
            + check_dates(record, resolutions, texts)
            + check_key_phrases(record, resolutions, texts)
            + check_forbidden(record, resolutions, texts)
            + check_codes(record, resolutions, texts)
        )
        flags.extend(record_flags)
        if not offline:
            _write_worksheet(record, resolutions, record_flags)

    if not offline:
        _write_report(records, resolutions, flags)
    _print_summary(records, resolutions, flags, offline=offline)
    return flags, resolutions


def _fetch_into(resolution: Resolution, documents: dict[str, Document]) -> None:
    try:
        result = tavily.fetch(resolution.url, docs=documents, run_dir=_fetch_dir())
    except Exception as exc:  # noqa: BLE001 - a failed fetch is a flag, not a crash
        resolution.error = f"{type(exc).__name__}: {exc}"
        return
    if result.error and not result.document.is_fetched:
        resolution.error = result.error
        return
    resolution.document = result.document
    resolution.url = result.document.url
    if result.error:  # a thin extract still has text, but say so
        resolution.error = result.error


def _fetch_dir() -> Path:
    """Where `tavily.fetch` persists its own copy.

    Not `SOURCES_DIR`: `fetch` writes `<run_dir>/docs/<doc_id>.txt` plus a metadata
    sidecar, so pointing it at the committed folder left a second, hash-named copy of
    every document beside the readable one — doubling what docs/08 §2 step 4 asks to
    commit. The cache directory is already gitignored, so `data/searchbench/sources/`
    ends up holding exactly the files the spec names.
    """
    directory = Path(get_settings().tavily_cache_dir) / "searchbench"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _merged_key(records: list[BenchRecord], descriptor: str) -> AnswerKey:
    """The `sources` URLs of every record naming this document.

    A document is shared — `L33822` governs 15 records — and only some of them carry
    its URL, so resolution should see all of them rather than whichever record happened
    to come first.
    """
    urls: list[str] = []
    for record in records:
        if descriptor in record.answer_key.governing_documents:
            urls.extend(record.answer_key.sources)
    return AnswerKey(summary="", sources=list(dict.fromkeys(urls)))


# --- outputs ----------------------------------------------------------------------


def _write_sources(resolutions: dict[str, Resolution]) -> dict[str, str]:
    """Copy each fetched document to `sources/<slug>.txt` and return the texts.

    The text is written unmodified — no metadata header — so `within.load_paragraphs`
    offsets over this file match the ones over the fetched copy, and any later verbatim
    check reads the same bytes. Metadata lives in `index.json`.
    """
    texts: dict[str, str] = {}
    for resolution in resolutions.values():
        document = resolution.document
        if document is None:
            continue
        try:
            text = within.load_text(document)
        except (OSError, ValueError) as exc:
            resolution.error = resolution.error or f"could not read text: {exc}"
            continue
        path = SOURCES_DIR / f"{resolution.slug}.txt"
        path.write_text(text, encoding="utf-8", newline="\n")
        texts[resolution.slug] = text
    return texts


def _write_index(resolutions: dict[str, Resolution]) -> None:
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "search_domains": SEARCH_DOMAINS,
        "documents": [r.as_json() for r in sorted(resolutions.values(), key=lambda r: r.descriptor)],
    }
    (SOURCES_DIR / "index.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def _write_worksheet(
    record: BenchRecord, resolutions: dict[str, Resolution], flags: list[Flag]
) -> None:
    """docs/08 §2 step 3's input: the draft key, and the live passages bearing on it."""
    lines = [
        f"# {record.id} — validation worksheet",
        "",
        f"**{redact(record.question)}**",
        "",
        f"`{record.domain}` · tier {record.tier} · {record.question_type} · split "
        f"`{record.split}`",
        "",
        "Correct the key in `data/searchbench/searchbench_v0.jsonl`, then set `as_of` and "
        "`validated_by` (docs/08 §2 step 3). This file is regenerated; do not edit it.",
        "",
    ]
    if flags:
        lines += ["## Flags", ""]
        lines += [f"- {flag}" for flag in flags] + [""]

    lines += ["## Draft summary", "", record.answer_key.summary, ""]
    if record.answer_key.expected_scope_warning:
        lines += ["## Expected scope warning", "", record.answer_key.expected_scope_warning, ""]

    lines += ["## Governing documents", ""]
    for descriptor in record.answer_key.governing_documents:
        resolution = resolutions.get(descriptor)
        if resolution is None:
            lines.append(f"- `{descriptor}` — not resolved")
            continue
        document = resolution.document
        if document is None:
            lines.append(f"- `{descriptor}` — **not fetched** ({resolution.error})")
            continue
        dated = _iso(document.revision_date) or _iso(document.effective_date) or "no date found"
        lines.append(
            f"- `{descriptor}` via **{resolution.method}** — [{document.title}]({document.url}) "
            f"· {document.source_tier} · {dated} · {document.paragraph_count} paragraphs"
        )
    lines.append("")

    lines += ["## Required claims, against the live text", ""]
    for claim in record.answer_key.required_claims:
        marker = "**must**" if claim.must else "optional"
        lines += [f"### {claim.id} ({marker})", "", claim.text, ""]
        lines += _passages_for(claim.text, record, resolutions)

    if record.answer_key.required_evidence:
        lines += ["## Required evidence key phrases", ""]
        for evidence in record.answer_key.required_evidence:
            marker = "**must**" if evidence.must else "optional"
            lines += [
                f"### {evidence.id} ({marker}) — {evidence.document_id_external} "
                f"[{evidence.doc_type}]",
                "",
            ]
            for phrase in evidence.key_phrases:
                lines += [f"`{phrase}`", ""]
                lines += _passages_for(phrase, record, resolutions)

    if record.answer_key.forbidden_claims:
        lines += ["## Forbidden claims", ""]
        for forbidden in record.answer_key.forbidden_claims:
            lines += [f"- **{forbidden.id}**: {forbidden.text} — _{forbidden.reason}_"]
        lines.append("")

    (REVIEW_DIR / f"{record.id}.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n"
    )


def _passages_for(
    query: str, record: BenchRecord, resolutions: dict[str, Resolution]
) -> list[str]:
    """The best passages for one claim or phrase, across the record's documents."""
    found: list[tuple[float, str, within.Passage]] = []
    for descriptor in record.answer_key.governing_documents:
        resolution = resolutions.get(descriptor)
        if resolution is None or resolution.document is None:
            continue
        try:
            passages = within.search_within(resolution.document, query, k=PASSAGES_PER_CLAIM)
        except (OSError, ValueError) as exc:
            _log.warning("worksheet.search_failed", record=record.id, error=str(exc))
            continue
        found.extend((p.score, descriptor, p) for p in passages)
    if not found:
        return ["_no matching passage in the fetched documents._", ""]
    found.sort(key=lambda item: item[0], reverse=True)
    lines: list[str] = []
    for _, descriptor, passage in found[:PASSAGES_PER_CLAIM]:
        section = f" §{passage.section}" if passage.section else ""
        text = passage.text.strip()
        if len(text) > MAX_PASSAGE_CHARS:
            text = text[:MAX_PASSAGE_CHARS].rstrip() + " […]"
        lines += [f"> {text}", "", f"— `{descriptor}`{section} ¶{passage.paragraph_index}", ""]
    return lines


def _write_report(
    records: list[BenchRecord], resolutions: dict[str, Resolution], flags: list[Flag]
) -> None:
    by_record: dict[str, list[Flag]] = defaultdict(list)
    for flag in flags:
        by_record[flag.record_id].append(flag)
    # Counted before the sort below reads it: `by_record` is a defaultdict, and the sort
    # key touches every record id, which silently created an empty entry for each and
    # made the report say "38 flags across 30 records" when 19 records had any.
    flagged = len(by_record)
    ranked = sorted(
        records,
        key=lambda r: (r.id not in HIGH_RISK, -len(by_record[r.id]), r.id),
    )
    counts = defaultdict(int)
    for flag in flags:
        counts[flag.kind] += 1
    fetched = [r for r in resolutions.values() if r.document is not None]

    lines = [
        "# SearchBench v0 — source drift report",
        "",
        f"Generated {datetime.now(UTC).date().isoformat()} by "
        "`uv run --env-file .env python -m eval.searchbench.fetch_sources` "
        "(`docs/08` §2 step 2).",
        "",
        "Every answer key in `searchbench_v0.jsonl` is a **draft** written from the "
        "author's knowledge. This report lists every place the live governing documents "
        "disagree with one. `docs/08` §2: finding that a draft key is wrong \"is expected "
        "and is a line for the technical statement\".",
        "",
        "**Nothing here has been applied.** Correcting the keys is task 2.1, by hand.",
        "",
        "## Totals",
        "",
        f"- {len(records)} records, {len(resolutions)} distinct governing documents, "
        f"{len(fetched)} fetched",
        f"- **{len(flags)} flags** across {flagged} of {len(records)} records",
        "- by kind: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"),
        "",
        "| kind | what it means |",
        "|---|---|",
        "| `date` | the draft asserts a date the live document does not carry |",
        "| `key_phrase` | a `required_evidence` phrase is absent from the live text, so the "
        "evidence-grounding evaluator would look for something that is not there |",
        "| `forbidden` | a claim the draft calls stale is still in the live document, or "
        "could not be checked automatically |",
        "| `code` | a code the key asserts is absent from the governing document, or one it "
        "calls retired is still in use |",
        "| `resolution` | the governing document could not be resolved, or only by a search "
        "guess |",
        "| `authoring` | the record breaks one of docs/08 §4-§5's authoring rules |",
        "",
        "## Documents",
        "",
        "| document | method | tier | revision | paragraphs | used by |",
        "|---|---|---|---|---|---|",
    ]
    for resolution in sorted(resolutions.values(), key=lambda r: r.descriptor):
        document = resolution.document
        method = resolution.method + (" ⚠" if resolution.needs_review else "")
        if document is None:
            lines.append(
                f"| `{resolution.descriptor}` | {method} | — | — | — | "
                f"{len(resolution.used_by)} records |"
            )
            continue
        dated = _iso(document.revision_date) or _iso(document.effective_date) or "—"
        lines.append(
            f"| [{resolution.descriptor}]({document.url}) | {method} | "
            f"{document.source_tier} | {dated} | {document.paragraph_count} | "
            f"{len(resolution.used_by)} records |"
        )
    lines.append("")

    lines += [
        "## Records",
        "",
        "Highest drift risk first (the six named in `data/searchbench/README.md`), then by "
        "flag count. Worksheets with the live passages are in `data/searchbench/review/`.",
        "",
    ]
    for record in ranked:
        record_flags = by_record[record.id]
        mark = " ⚠ high risk" if record.id in HIGH_RISK else ""
        status = f"{len(record_flags)} flags" if record_flags else "no drift detected"
        lines += [
            f"### {record.id} — {status}{mark}",
            "",
            f"> {redact(record.question)}",
            "",
        ]
        if record_flags:
            lines += [f"- {flag}" for flag in record_flags] + [""]
        lines += [f"[worksheet](../data/searchbench/review/{record.id}.md)", ""]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def _print_resolution(resolution: Resolution) -> None:
    document = resolution.document
    mark = "!" if resolution.needs_review else " "
    if document is None:
        print(f" {mark} {resolution.descriptor:52} {resolution.method:11} {resolution.error}")
        return
    dated = _iso(document.revision_date) or _iso(document.effective_date) or "no date"
    print(
        f" {mark} {resolution.descriptor:52} {resolution.method:11} "
        f"{document.source_tier:18} {dated:10} {document.paragraph_count:4}p"
    )


def _print_summary(
    records: list[BenchRecord],
    resolutions: dict[str, Resolution],
    flags: list[Flag],
    *,
    offline: bool = False,
) -> None:
    by_record: dict[str, list[Flag]] = defaultdict(list)
    for flag in flags:
        by_record[flag.record_id].append(flag)
    print(f"\n{'=' * 78}\n{len(flags)} flags across {len(by_record)} of {len(records)} records\n")
    for record in sorted(records, key=lambda r: (-len(by_record[r.id]), r.id)):
        record_flags = by_record[record.id]
        if not record_flags:
            continue
        mark = " (high risk)" if record.id in HIGH_RISK else ""
        print(f"{record.id}{mark}")
        for flag in record_flags:
            print(f"    {flag}")
    clean = [r.id for r in records if not by_record[r.id]]
    if clean:
        print(f"\nno drift detected: {', '.join(clean)}")
    if offline:
        print("\noffline: resolved and checked only, no files written.")
    else:
        print(f"\nreport:     {REPORT_PATH}")
        print(f"worksheets: {REVIEW_DIR}/<record_id>.md")
        print(f"sources:    {SOURCES_DIR}/")
    print("\nNothing was written to the dataset. Correcting the keys is task 2.1.")


# --- small helpers ----------------------------------------------------------------


def _key_text(key: AnswerKey) -> str:
    """Everything in a key that can assert a date or a code."""
    return " ".join(
        [key.summary]
        + [claim.text for claim in key.required_claims]
        + [forbidden.text for forbidden in key.forbidden_claims]
        + [forbidden.reason for forbidden in key.forbidden_claims]
        + [note for note in key.expected_contradictions]
    )


def _dates_in(key: AnswerKey) -> set[date]:
    """Every full date the draft key asserts. Month-precision dates are deliberately
    excluded: they cannot be compared to a document's revision date, and treating
    "April 2025" as 2025-04-01 would invent a day the key never claimed."""
    blob = _key_text(key)
    found: set[date] = set()
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(blob):
            parsed = _to_date(match.groups())
            if parsed is not None:
                found.add(parsed)
    return found


def _to_date(groups: tuple[str, ...]) -> date | None:
    try:
        if groups[0] in _MONTH_NUMBER:  # "April 16, 2023"
            return date(int(groups[2]), _MONTH_NUMBER[groups[0]], int(groups[1]))
        if len(groups[0]) == 4:  # "2023-04-16"
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        return date(int(groups[2]), int(groups[0]), int(groups[1]))  # "04/16/2023"
    except ValueError:
        return None


# Patient-level detail in a question. Deliberately narrow: a question may say "a type 2
# diabetic not on insulin" — that is a policy population, not a person. What is caught is
# an identified individual (a named patient, a date of birth, a specific lab value).
_PATIENT_PATTERNS = (
    ("a date of birth", re.compile(r"\bDOB\b|\bdate of birth\b", re.IGNORECASE)),
    ("a named patient", re.compile(r"\b(?:my|the)\s+patient\s+[A-Z][a-z]+\b")),
    ("a lab value", re.compile(r"\bA1c\s*[:=]?\s*\d", re.IGNORECASE)),
    ("a medical record number", re.compile(r"\b(?:MRN|member id|policy no)\b", re.IGNORECASE)),
)


def _patient_details(question: str) -> list[str]:
    """Which patient-level identifiers a question carries, if any."""
    return [label for label, pattern in _PATIENT_PATTERNS if pattern.search(question)]


def redact(question: str) -> str:
    """Mask patient-level detail before a question is written to an artifact.

    Flagging `oos-002` for carrying a name, a date of birth and an A1c while copying
    that same string verbatim into a new worksheet and a new report — both committed —
    would have spread what CLAUDE.md forbids ("not even synthetic") across three files
    instead of one. The redaction is display-only: the dataset is untouched, and task
    2.1 rewrites the question at policy level.
    """
    if not _patient_details(question):
        return question
    redacted = question
    for pattern in (
        re.compile(r"\bDOB\s*:?\s*[\d/\-.]+", re.IGNORECASE),
        re.compile(r"\bA1c\s*(?:of|[:=])?\s*[\d.]+%?", re.IGNORECASE),
        re.compile(r"\b(?:my|the)\s+patient\s+[A-Z][a-z]+", re.IGNORECASE),
    ):
        redacted = pattern.sub("[redacted]", redacted)
    return f"{redacted}  _(patient detail redacted; see docs/11)_"


def _distinctive_phrases(text: str) -> list[str]:
    """Quoted spans and long parenthetical phrases from a forbidden claim.

    A whole sentence never appears verbatim in a policy document, so matching on one
    would flag nothing. Quoted fragments — which is how the seed file writes the
    superseded wording — do appear.
    """
    spans = re.findall(r'"([^"]{6,})"', text) + re.findall(r"\(([^)]{6,})\)", text)
    phrases: list[str] = []
    for span in spans:
        # `("three or more")` matches both patterns, and the parenthesised one keeps the
        # quotes — so the phrase searched for was `"three or more"`, which appears in no
        # document and silently disabled the check.
        cleaned = span.strip().strip('"').strip().lower()
        if len(cleaned) >= 6 and cleaned not in phrases:
            phrases.append(cleaned)
    return phrases


def _resolution_for(
    external: str, record: BenchRecord, resolutions: dict[str, Resolution]
) -> Resolution | None:
    """Match a `required_evidence.document_id_external` to a resolved document.

    The two fields do not always agree — a record can name `Section 1927(d)(2)(A)` in
    evidence and `SSA 1927(d)(2)(A)` in `governing_documents` — so an exact miss falls
    back to a containment test before giving up.

    Scoped to **this record's** `governing_documents`. `resolutions` is the run-wide map
    of every descriptor in all 30 records, so an exact-key lookup matched documents
    another record had named: `glp1-path-001`'s `e2` ("CMS 2024 Part D guidance") hit a
    premium-projection fact sheet resolved for `adv-glp1-002`, and the report then told
    a reviewer that "medically accepted indication" — the correct statutory term — was
    missing from a document `glp1-path-001` never names. It also suppressed the flag
    this function exists to raise.
    """
    governing = record.answer_key.governing_documents
    if external in governing:
        return resolutions.get(external)
    lowered = external.lower()
    for descriptor in governing:
        other = descriptor.lower()
        if lowered in other or other in lowered:
            return resolutions.get(descriptor)
    return None


def _slugify(text: str) -> str:
    if text.lower().startswith(("http://", "https://")):
        # A URL's head is the shared host; the tail is what tells sibling pages apart.
        path = re.sub(r"^https?://[^/]+", "", text.lower())
        return re.sub(r"[^a-z0-9]+", "-", path).strip("-")[-60:].strip("-") or "document"
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "document"


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _join(values) -> str:  # noqa: ANN001
    return ", ".join(sorted(str(v.isoformat() if isinstance(v, date) else v) for v in values))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.searchbench.fetch_sources",
        description="Fetch SearchBench governing documents and report draft-key drift "
        "(docs/08 §2 step 2). Never modifies the dataset.",
    )
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument(
        "--only", help="limit to one record id, domain (cgm|glp1|cross|other) or split"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="resolve and report without any network call; documents stay unfetched",
    )
    args = parser.parse_args(argv)

    configure_logging()
    flags, _ = run(dataset=args.dataset, only=args.only, offline=args.offline)
    # Flags are the expected outcome, not a failure: docs/08 §2 says a wrong draft key
    # "is expected". Exit 0 so this can run in a pipeline without pretending drift is
    # an error.
    return 0 if flags is not None else 1


if __name__ == "__main__":
    sys.exit(main())

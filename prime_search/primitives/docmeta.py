"""Deterministic document metadata and paragraph structure (docs/04 §2).

Runs over the title, URL and extracted text after `fetch`; no model involved. What
the live pages forced (all measured 2026-09-12):

* **The CMS header metadata block is JavaScript-rendered and absent from the
  extract** on both L33822 and A52464 — "Document Information" carries AMA/AHA
  license text instead, and neither page's extract contains the string "Original
  Effective Date" at all. The dates survive only in the Revision History table
  (`| 10/01/2024 | R16 | Revision Effective Date: 10/01/2024 | ...`), so dates are
  aggregated over the whole document — latest revision, earliest original — rather
  than read from a fixed position. Both pages therefore have a `revision_date` and
  no `effective_date`, which is the honest answer, not a gap to paper over.
* **A date label inside a markdown table *header* is not adjacent to its value.**
  CMS's "Associated Documents" table reads
  `| Updated On | Effective Dates | Status |` over
  `| 10/09/2024 | 10/01/2024 - N/A | Currently in Effect |`, so the nearest date
  after "Effective Dates" is the *Updated On* cell — a different column. Header rows
  are skipped; data rows are kept, because CMS writes "Revision Effective Date:
  10/01/2024" inside a single cell.
* **docs/04 §2's canonical section names are not headings on the live pages.** The
  real markers are markdown (`## LCD Information`, `### Coverage Guidance`); the
  string "COVERAGE INDICATIONS, LIMITATIONS, AND/OR MEDICAL NECESSITY" occurs 21
  times inside table cells. A heading must therefore own its whole line.
* Date labels also occur as markdown link text (`Revision Effective Date](https://…`)
  and with `N/A` values; both are skipped.
* FDA labels date themselves as "Revised: 5/2026" or "Updated June 1, 2026" — neither
  a label docs/04 §2 lists nor a full date. Both are supported as *weak* signals, so
  a real Revision Effective Date always outranks them.

Offsets are character offsets into the text returned by `normalize_text`, which is
exactly what `fetch` persists: docs/04 §3 validates evidence as a substring of the
referenced paragraph, so text and offsets must agree byte for byte.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import parse_qsl, urlsplit

# --- normalization ---------------------------------------------------------------

# Folded once, before persisting, so an agent that retypes ASCII punctuation still
# produces a verbatim substring. Live CMS text carries U+2010 (non-breaking hyphen),
# NBSP, en dashes and curly quotes.
_FOLD = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'", 0x2032: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x2033: '"',
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2015: "-",
    0x00A0: " ", 0x2007: " ", 0x2009: " ", 0x202F: " ", 0x3000: " ",
    0x00AD: None, 0x200B: None, 0x200C: None, 0x200D: None, 0xFEFF: None,
}


def normalize_text(raw: str) -> str:
    """The one text form that is persisted, offset, indexed and cited.

    Idempotent, which the round-trip test pins. Newlines are LF only, so a Windows
    checkout of a committed fixture still produces identical offsets.
    """
    text = unicodedata.normalize("NFC", raw or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n").translate(_FOLD)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return f"{text}\n" if text else ""


# --- paragraphs and sections -----------------------------------------------------

# A paragraph is a run of non-empty lines: docs/04 §2 splits on blank lines and keeps
# tables whole. Normalization has already emptied whitespace-only lines.
_BLOCK = re.compile(r"[^\n]+(?:\n[^\n]+)*")

_HEADING_MD = re.compile(r"^\s{0,3}#{1,6}\s+(?P<text>.+?)\s*#*$")
_HEADING_HTML = re.compile(r"^\s*<h[1-6][^>]*>(?P<text>.*?)</h[1-6]>\s*$", re.IGNORECASE)
_HEADING_BOLD = re.compile(r"^\s*\*\*(?P<text>[^*].{2,78}?)\*\*:?\s*$")

# docs/04 §2's CMS coverage-database section names.
CANONICAL_SECTIONS: tuple[str, ...] = (
    "Coverage Indications, Limitations, and/or Medical Necessity",
    "Summary of Evidence",
    "Coding Information",
    "HCPCS Codes",
    "Documentation Requirements",
    "Revision History",
)
_CANONICAL_KEYS = {
    re.sub(r"[^a-z0-9]+", " ", name.lower()).strip() for name in CANONICAL_SECTIONS
}

# Chrome, not content. Excluded from the BM25 index (within.py) but still indexed and
# offset, so `?p=<index>` and Location stay valid.
_BOILERPLATE_SECTION = re.compile(
    r"license for use|ama disclaimer|cms disclaimer|page help|connect with cms|"
    r"get email updates|subscriptions|creating a document pdf|"
    # Site chrome that is nonetheless a real heading. These reach citations through
    # Location.section, so "LCD L33822 §Main header" has to be impossible.
    r"^(official websites use|secure \.gov websites|skip to main|breadcrumb)|"
    r"^(main header|contents|footer|related resources|view package photos|view more)$",
    re.IGNORECASE,
)
_BOILERPLATE_TEXT = re.compile(
    r"an official website of the united states government|skip to main content|"
    r"javascript|copyright \d{4} american (medical|hospital|dental)|"
    r"cpt codes, descriptions, and other data only are copyright",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Paragraph:
    index: int  # 0-based (docs/07 renders ?p=<index>)
    text: str
    char_start: int
    char_end: int  # half-open: text[char_start:char_end] == self.text
    section: str | None
    boilerplate: bool = False


def _clean_inline(text: str) -> str:
    text = re.sub(r"\[(?P<label>[^\]]*)\]\([^)]*\)", r"\g<label>", text)  # markdown links
    return re.sub(r"[*_`]+", "", text).strip(" :|")


def _heading_of(line: str) -> str | None:
    for pattern in (_HEADING_MD, _HEADING_HTML, _HEADING_BOLD):
        match = pattern.match(line)
        if match:
            return _clean_inline(match.group("text"))
    stripped = _clean_inline(line)
    if re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip(" :") in _CANONICAL_KEYS:
        return stripped
    return None


def split_paragraphs(text: str) -> list[Paragraph]:
    """Blank-line split with offsets; tables stay single paragraphs (docs/04 §2).

    Expects `normalize_text` output; call it first or the offsets will not match the
    persisted file.
    """
    paragraphs: list[Paragraph] = []
    section: str | None = None
    for index, block in enumerate(_BLOCK.finditer(text)):
        body = block.group(0)
        heading = _heading_of(body.split("\n", 1)[0])
        if heading:
            section = heading
        is_boilerplate = bool(
            (section and _BOILERPLATE_SECTION.search(section)) or _BOILERPLATE_TEXT.search(body)
        )
        paragraphs.append(
            Paragraph(
                index=index,
                text=body,
                char_start=block.start(),
                char_end=block.end(),
                section=section,
                boilerplate=is_boilerplate,
            )
        )
    return paragraphs


# --- dates -----------------------------------------------------------------------

_MONTHS = {
    name[:3].lower(): number
    for number, name in enumerate(
        (
            "January February March April May June July August September October "
            "November December"
        ).split(),
        start=1,
    )
}
_NUMERIC_MDY = re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})\b")
_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b")
_MONTH_FIRST = re.compile(r"\b(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})\b")
_DAY_FIRST = re.compile(r"\b(?P<d>\d{1,2})\s+(?P<mon>[A-Za-z]{3,9})\.?,?\s+(?P<y>\d{4})\b")
_SHORT_MDY = re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<yy>\d{2})\b")
# Month-year only, the form FDA labels use ("Revised: 5/2026", "Revised: June/2026").
# Resolved to the first of the month: a label revision has no finer granularity.
# The lookbehind keeps document numbers out — "Pub 100-02/2024" is a manual
# reference, not February 2024.
_MONTH_YEAR_NUM = re.compile(r"(?<![\d\-/])(?P<m>\d{1,2})/(?P<y>\d{4})\b")
_MONTH_YEAR_NAME = re.compile(r"\b(?P<mon>[A-Za-z]{3,9})[/ ](?P<y>\d{4})\b")

# 1965 is Medicare's enactment; the upper bound leaves room for a future effective
# date. The window is what stops HCPCS codes and section numbers parsing as dates.
_MIN_YEAR, _MAX_YEAR = 1965, datetime.now().year + 5


def _build(year: int, month: int, day: int) -> date | None:
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    return parsed if _MIN_YEAR <= parsed.year <= _MAX_YEAR else None


def parse_date_token(token: str) -> date | None:
    """Tolerant parser: 04/16/2023, 2023-04-16, April 16 2023, 16 Apr 2023, 4/16/23.

    Returns the first parseable date in `token`, or None. Ordered so an unambiguous
    form is tried before the two-digit-year form.
    """
    text = token or ""
    # finditer, not search: the first match of a pattern is often not a date at all
    # ("Chapter 15, 2024" matches the month-name shape), and abandoning the pattern
    # there would miss the real date later in the same window.
    for pattern in (_NUMERIC_MDY, _ISO):
        for match in pattern.finditer(text):
            found = _build(int(match["y"]), int(match["m"]), int(match["d"]))
            if found:
                return found
    for pattern in (_MONTH_FIRST, _DAY_FIRST):
        for match in pattern.finditer(text):
            month = _MONTHS.get(match["mon"][:3].lower())
            if month:
                found = _build(int(match["y"]), month, int(match["d"]))
                if found:
                    return found
    for match in _SHORT_MDY.finditer(text):
        found = _build(2000 + int(match["yy"]), int(match["m"]), int(match["d"]))
        if found:
            return found
    # Last resort: month-year, day defaulted to the 1st.
    for match in _MONTH_YEAR_NUM.finditer(text):
        found = _build(int(match["y"]), int(match["m"]), 1)
        if found:
            return found
    for match in _MONTH_YEAR_NAME.finditer(text):
        month = _MONTHS.get(match["mon"][:3].lower())
        if month:
            found = _build(int(match["y"]), month, 1)
            if found:
                return found
    return None


def find_date_token(text: str) -> date | None:
    """First parseable date anywhere in `text`; used for a search hit's `date_hint`."""
    return parse_date_token(text)


# label -> which field it feeds. "revision"/"effective" are authoritative; the
# "_weak" kinds only fill a gap, so a site-wide "Last Updated" cannot outrank a real
# revision date. "extra" labels have no docs/02 field and go to the sidecar.
_DATE_LABELS: tuple[tuple[str, str], ...] = (
    ("Revision Effective Date", "revision"),
    ("Revision Date", "revision"),
    ("Original Effective Date", "effective"),
    ("Effective Date", "effective"),
    ("Decision Date", "effective"),  # FDA 510(k) database
    ("Approval Date", "effective"),  # Drugs@FDA
    ("Action Date", "effective"),
    ("Issued", "effective_weak"),
    ("Posted", "effective_weak"),
    ("Publication Date", "effective_weak"),
    ("Last Updated", "revision_weak"),
    ("Last Reviewed", "revision_weak"),
    # FDA/DailyMed labels state currency as "Revised: 5/2026" or "Updated June 1,
    # 2026" rather than any label docs/04 §2 lists (which says "patterns like").
    # Weak, so an authoritative Revision Effective Date always wins.
    ("Revised", "revision_weak"),
    ("Updated On", "revision_weak"),
    ("Updated", "revision_weak"),
    ("Revision Ending Date", "extra"),
    ("Retirement Date", "extra"),
    ("Date Received", "extra"),
    # Not wanted for themselves, but they are real CMS LCD header fields and must be
    # known so they terminate the previous label's window. Without them, an
    # "Effective Date" with no value reaches across and takes this field's date.
    ("Notice Period Start Date", "extra"),
    ("Notice Period End Date", "extra"),
)
# Longest label first: plain `Effective Date` must not swallow `Revision Effective
# Date`, and Python's alternation is first-match-wins.
_LABEL_RE = re.compile(
    "(?P<label>"
    + "|".join(re.escape(label) for label, _ in sorted(_DATE_LABELS, key=lambda p: -len(p[0])))
    + r")\s*(?:\(s\))?\s*[:|]?",
    re.IGNORECASE,
)
_LABEL_KIND = {label.lower(): kind for label, kind in _DATE_LABELS}
_WINDOW = 140  # chars searched after a label for "the nearest date token" (docs/04 §2)
# Weak labels are ordinary words, so they also occur mid-sentence: a revision-history
# cell reading "Revised to add code A4239 effective 07/01/2018" would otherwise book
# that date as the document's revision. A short window keeps "Revised: 5/2026" while
# rejecting prose.
_WINDOW_WEAK = 24
_WEAK_KINDS = frozenset({"revision_weak", "effective_weak"})


# A markdown table header line: the row above the `| --- | --- |` separator.
_TABLE_HEADER = re.compile(r"^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[\s:|-]+\|[ \t]*$", re.MULTILINE)


def _table_header_spans(text: str) -> list[tuple[int, int]]:
    """Character ranges of markdown table *header* rows.

    A label in a column header is not adjacent to its value — the value sits in the
    matching column of a later row. CMS's "Associated Documents" table is exactly
    this trap: `| Updated On | Effective Dates | Status |` over
    `| 10/09/2024 | 10/01/2024 - N/A | Currently in Effect |`, where the nearest date
    after "Effective Dates" is the *Updated On* cell. Data rows are fine, because CMS
    writes "Revision Effective Date: 10/01/2024" inside a single cell.
    """
    spans = []
    for match in _TABLE_HEADER.finditer(text):
        header_end = text.index("\n", match.start())
        spans.append((match.start(), header_end))
    return spans


def _labelled_dates(text: str) -> tuple[dict[str, list[date]], dict[str, list[date]]]:
    """(dates by kind, dates by literal label). Every label occurrence in the
    document is considered; the caller aggregates."""
    by_kind: dict[str, list[date]] = {}
    by_label: dict[str, list[date]] = {}
    header_spans = _table_header_spans(text)
    matches = list(_LABEL_RE.finditer(text))
    for position, match in enumerate(matches):
        if any(start <= match.start() < end for start, end in header_spans):
            continue  # a column header, not a labelled value
        label = match.group("label").lower()
        span = _WINDOW_WEAK if _LABEL_KIND[label] in _WEAK_KINDS else _WINDOW
        next_start = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        window = text[match.end() : min(len(text), match.end() + span, next_start)]
        if window.lstrip().startswith("](") or re.match(r"\s*N/?A\b", window, re.IGNORECASE):
            continue  # markdown link text, or an explicitly empty field
        parsed = parse_date_token(window)
        if parsed:
            by_kind.setdefault(_LABEL_KIND[label], []).append(parsed)
            by_label.setdefault(label, []).append(parsed)
    return by_kind, by_label


def _resolve_dates(text: str) -> tuple[date | None, date | None, dict[str, str]]:
    """(effective_date, revision_date, extra_dates).

    Latest revision and earliest original, because both real layouts appear: a header
    block states each once, while a revision-history table restates `Revision
    Effective Date` for every past revision (R16 down to R1 on L33822). Future-dated
    revisions are ignored unless they are all there is.
    """
    by_kind, by_label = _labelled_dates(text)
    today = date.today()

    revisions = by_kind.get("revision") or by_kind.get("revision_weak") or []
    past = [value for value in revisions if value <= today]
    revision_date = max(past) if past else (min(revisions) if revisions else None)

    effectives = by_kind.get("effective") or by_kind.get("effective_weak") or []
    effective_date = min(effectives) if effectives else None

    extra = {
        label: min(values).isoformat()
        for label, values in by_label.items()
        if _LABEL_KIND[label] == "extra"
    }
    return effective_date, revision_date, extra


# --- doc type and external id ----------------------------------------------------

# docs/04 §2's regexes, ordered by confidence. The FDA patterns are this build's
# invention: no spec gives one, and docs/09 §1.3 requires an FDA fixture.
_ID_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("LCD", re.compile(r"\b(L\d{5})\b")),
    ("Article", re.compile(r"\b(A\d{5})\b")),
    ("NCD", re.compile(r"\b(NCD\s+\d+\.\d+)\b", re.IGNORECASE)),
    ("MLN Matters", re.compile(r"\b(MLN\d+)\b", re.IGNORECASE)),
    ("510(k)", re.compile(r"\b(K\d{6})\b")),
    ("Approval", re.compile(r"\b(P\d{6}|DEN\d{6})\b")),
    ("Approval", re.compile(r"\b((?:NDA|BLA|ANDA)\s*#?\s*\d{6})\b")),
)
_TYPE_ONLY: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Fact sheet", re.compile(r"\bfact sheet\b", re.IGNORECASE)),
    ("Press release", re.compile(r"\bpress release\b|\bpress announcement\b", re.IGNORECASE)),
    ("Label", re.compile(r"\bprescribing information\b|\bpackage insert\b", re.IGNORECASE)),
)
# CMS puts the id in its own URL, which beats any text match.
_URL_ID_PARAMS = {"lcdid": ("LCD", "L"), "articleid": ("Article", "A"), "ncdid": ("NCD", "")}


def _doc_type_and_id(url: str, title: str, text: str) -> tuple[str | None, str | None]:
    """URL first, then title, then the head of the text.

    Order matters: L33822's body cites A52464, A59330 and A58798, so a text-first
    search would file the LCD as an Article.
    """
    params = {key.lower(): value for key, value in parse_qsl(urlsplit(url).query)}
    for param, (doc_type, prefix) in _URL_ID_PARAMS.items():
        if params.get(param, "").strip().isdigit():
            return doc_type, f"{prefix}{params[param].strip()}"
    if params.get("setid"):
        return "Label", f"SPL {params['setid']}"
    if params.get("id", "").upper().startswith("K"):
        return "510(k)", params["id"].upper()

    head = text[:6000]
    for haystack in (title, head):
        for doc_type, pattern in _ID_RULES:
            match = pattern.search(haystack or "")
            if match:
                return doc_type, re.sub(r"\s+", " ", match.group(1)).upper()
    for haystack in (title, head):
        for doc_type, pattern in _TYPE_ONLY:
            if pattern.search(haystack or ""):
                return doc_type, None
    if params.get("applno", "").isdigit():
        return "Approval", f"ApplNo {params['applno']}"
    return None, None


_PUBLISHER_NAMES = re.compile(
    r"\b(Noridian|CGS Administrators|CGS|Palmetto GBA|Palmetto|National Government Services"
    r"|NGS|WPS|Novitas|First Coast|CMS|FDA)\b"
)


def _publisher(url: str, title: str, text: str, rule_publisher: str | None) -> str | None:
    """docs/04 §2: "from domain and page header"."""
    if rule_publisher:
        return rule_publisher
    for candidate in (title or "", text[:2000]):
        match = _PUBLISHER_NAMES.search(candidate)
        if match:
            return match.group(1)
    return host_of_url(url) or None


def host_of_url(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


# --- public result ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DocMeta:
    title: str
    publisher: str | None
    doc_type: str | None
    document_id_external: str | None
    effective_date: date | None
    revision_date: date | None
    sections: list[str]
    paragraphs: list[Paragraph]
    extra_dates: dict[str, str] = field(default_factory=dict)  # sidecar only

    @property
    def paragraph_count(self) -> int:
        return len(self.paragraphs)


def extract_meta(
    *, url: str, title: str, text: str, publisher_hint: str | None = None
) -> DocMeta:
    """All of docs/04 §2 over already-normalized text.

    Fields stay None when nothing is found: docs/04 §2 makes a missing date on a
    policy document a critic finding, not something to guess at.
    """
    paragraphs = split_paragraphs(text)
    doc_type, external_id = _doc_type_and_id(url, title, text)
    effective_date, revision_date, extra = _resolve_dates(text)
    # Content sections only: the site banner and cookie notices are headings too,
    # and docs/09 §1.3 checks these against a policy document's real structure.
    sections: list[str] = []
    for paragraph in paragraphs:
        if paragraph.section and not paragraph.boilerplate and paragraph.section not in sections:
            sections.append(paragraph.section)
    return DocMeta(
        title=title or url,
        publisher=_publisher(url, title, text, publisher_hint),
        doc_type=doc_type,
        document_id_external=external_id,
        effective_date=effective_date,
        revision_date=revision_date,
        sections=sections,
        paragraphs=paragraphs,
        extra_dates=extra,
    )

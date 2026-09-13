"""SearchBench evaluators (docs/05 §2).

Twelve metric keys, scored per run against a validated answer key: deterministic ones
first, then LLM-judge ones on the evaluator model at temperature 0 with a rubric prompt
and a `comment` - the comment is the text GEPA consumes (docs/05 §5), so every comment
names ids, sentences and reasons rather than a bare number.

Three kinds of "no score", kept apart because a report that averages them together lies:

* **not applicable** - `score=None`, comment "not applicable: ...". A contradiction metric on
  a question with no expected contradiction. Excluded from means.
* **run failed** - no record or no answer. Quality metrics score 0, never None: a crash must
  not look better than a wrong answer.
* **judge failed** - `score=None` with `metadata.error`. Counted separately by the report and
  fixed by re-scoring, not averaged.

The public surface (`score_record`, `composite`, `feedback_text`) is what the 3.1 GEPA
adapter imports; `EVALUATORS` are the same functions wrapped for LangSmith `evaluate()`.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel

from eval.searchbench.schema import AnswerKey, BenchRecord
from prime_search.agents.synthesizer import _ALT_CITATION, _CITATION
from prime_search.models import structured, token_usage
from prime_search.primitives import sources
from prime_search.prompts import render
from prime_search.schemas import Answer, Citation, Document, RunRecord

__all__ = [
    "EVALUATORS",
    "METRIC_KEYS",
    "Score",
    "bench_from_example",
    "composite",
    "feedback_text",
    "record_from_run",
    "resolve_descriptor",
    "score_record",
]

# docs/05 §2's table, in its order.
METRIC_KEYS: tuple[str, ...] = (
    "answer_correctness",
    "evidence_recall",
    "citation_correctness",
    "citation_completeness",
    "currency",
    "contradiction_handling",
    "scope_handling",
    "primary_source_ratio",
    "search_cost",
    "latency_s",
    "tokens",
    "search_efficiency",
)

SOURCES_INDEX = Path("data/searchbench/sources/index.json")
# answer_correctness = 0.8 x claims + 0.2 x summary; an asserted forbidden claim caps it.
# docs/08 §5 calls such an answer "wrong even if everything else is right"; a cap rather
# than zero keeps a mostly right answer distinguishable from nothing (docs/11).
CLAIMS_WEIGHT = 0.8
SUMMARY_WEIGHT = 0.2
FORBIDDEN_CAP = 0.25
CITATION_SAMPLE = 8
MAX_PASSAGES_PER_SENTENCE = 4
_SUMMARY_SCORES = {"consistent": 1.0, "partial": 0.5, "inconsistent": 0.0}
_ORDER_SCORES = {
    "ordered_with_dates": 1.0,
    "dated_not_ordered": 0.5,
    "undated": 0.0,
    "no_change_stated_with_date": 1.0,
    "no_change_stated_undated": 0.5,
}


@dataclass(frozen=True)
class Score:
    key: str
    score: float | int | None
    comment: str
    metadata: dict = field(default_factory=dict)

    def to_langsmith(self) -> dict[str, Any]:
        """A dict LangSmith's `EvaluationResult` accepts (its model forbids extra keys).

        LangSmith rejects a score outside +/-99999.9999 and drops the whole ingest batch
        with it, so a larger count (a prime run's tokens) goes as a string `value`."""
        score, value = self.score, None
        if score is not None and abs(score) > LANGSMITH_SCORE_MAX:
            score, value = None, f"{score:,}"
        return {
            "key": self.key,
            "score": score,
            "value": value,
            "comment": self.comment,
            "metadata": self.metadata or None,
        }


# --- judge schemas -------------------------------------------------------------------


class ClaimJudgment(BaseModel):
    id: str
    status: Literal["present", "incorrect", "missing"]
    quote: str = ""
    reason: str = ""


class ForbiddenJudgment(BaseModel):
    id: str
    asserted: bool
    quote: str = ""


class AnswerCorrectnessJudgment(BaseModel):
    # Required, not defaulted: a native reply without the list validated as "no claims"
    # and graded every claim missing on the first dev bench (docs/11).
    claims: list[ClaimJudgment]
    forbidden: list[ForbiddenJudgment]
    summary_consistency: Literal["consistent", "partial", "inconsistent"]
    notes: str = ""


class SentenceJudgment(BaseModel):
    index: int
    supported: bool
    reason: str = ""


class CitationJudgment(BaseModel):
    items: list[SentenceJudgment]


class OrderJudgment(BaseModel):
    verdict: Literal[
        "ordered_with_dates",
        "dated_not_ordered",
        "undated",
        "no_change_stated_with_date",
        "no_change_stated_undated",
    ]
    reason: str = ""


class ContradictionItem(BaseModel):
    index: int
    surfaced: bool
    governing_stated: bool
    quote: str = ""
    reason: str = ""


class ContradictionJudgment(BaseModel):
    items: list[ContradictionItem]


class ScopeJudgment(BaseModel):
    scope_flagged_in_text: bool
    fabricated_criteria: list[str] = []
    reason: str = ""


# --- text helpers --------------------------------------------------------------------

_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-")
_SPACES = dict.fromkeys(map(ord, "\u00a0\u2007\u2009\u202f"), " ")
_HEADING = re.compile(r"^##+\s*(.+?)\s*$", re.MULTILINE)
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[\"“])")
_ABBREVIATION = re.compile(r"\b(?:e\.g|i\.e|U\.S|No|vs|etc|Dr|St|Sec)\.$", re.IGNORECASE)
_CITES_ONLY = re.compile(r"^\s*(?:\[\d{1,3}\]\s*)+[.;,]?\s*$")
_EMPTY_LINE = re.compile(r"^(?:none(?: found)?|not applicable|n/?a)\.?$", re.IGNORECASE)
_URL = re.compile(r"https?://\S+")
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\([^)]+\)")
# Footnote markers: markdown `[^1]` and the baseline model's `[^36130e-00^]` result ids.
_FOOTNOTE = re.compile(r"\[\^[^\]\s]+\]")
LANGSMITH_SCORE_MAX = 99_999.9999
JUDGE_ATTEMPTS = 2
# answer_correctness is the majority of this many independent judge calls (docs/05 §2 as
# built). One call moved single rows 0.3-0.5 when an unchanged answer was re-scored.
ANSWER_JUDGE_VOTES = 3
_STATUS_ORDER = ("present", "incorrect", "missing")
_SUMMARY_ORDER = ("inconsistent", "partial", "consistent")
_EXT_ID = re.compile(r"^(?:[LA]\d{5}|NCD\s*\d+(?:\.\d+)*)$", re.IGNORECASE)
# Doc types that name the same kind of document in the key and in docmeta (docs/11).
_TYPE_GROUPS = (
    {"guidance", "fact sheet", "press release", "mln matters", "memo"},
    {"label", "approval"},
    {"lcd"},
    {"article"},
    {"ncd"},
    {"statute"},
)


def fold(text: str | None) -> str:
    """Case, whitespace and Unicode folding for phrase and date matching. Live answers
    carry U+2011 and U+202F ("2024‑10‑01"), which a plain `in` never matches."""
    folded = unicodedata.normalize("NFKC", text or "").translate(_DASHES).translate(_SPACES)
    return " ".join(folded.casefold().split())


def normalize_citations(text: str) -> str:
    return _ALT_CITATION.sub(lambda match: f"[{int(match.group(1))}]", text or "")


def sections(body: str) -> dict[str, str]:
    """`## Heading` -> the text under it."""
    body = body or ""
    found: dict[str, str] = {}
    matches = list(_HEADING.finditer(body))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        found[match.group(1).strip()] = body[match.end():end].strip()
    return found


def sentences(text: str) -> list[str]:
    """Sentence units: each bullet or line, split on sentence ends, with a citation that
    trails the full stop ("... criteria. [2]") kept with its sentence."""
    units: list[str] = []
    for raw in normalize_citations(text).splitlines():
        line = _BULLET.sub("", raw).strip()
        if not line or line.startswith("#") or _EMPTY_LINE.match(line.strip("*_ ")):
            continue
        merged: list[str] = []
        for piece in (part.strip() for part in _SPLIT.split(line)):
            if not piece:
                continue
            if merged and (_CITES_ONLY.match(piece) or _ABBREVIATION.search(merged[-1])):
                merged[-1] = f"{merged[-1]} {piece}"
            else:
                merged.append(piece)
        units.extend(merged)
    return units


def _claims_text(answer: Answer) -> str:
    """The judge text without "Effective dates relied on": its lines are a bibliography
    (`[4] CMS fact sheet - 2026-04-06`), not claims a passage states (docs/11)."""
    text = _judge_text(answer)
    match = re.search(r"^##+\s*Effective dates\b.*?(?=^##|\Z)", text, re.MULTILINE | re.DOTALL)
    return text[: match.start()] + text[match.end():] if match else text


def _document_header(document: Any) -> str:
    """The source as recorded at fetch time. A passage rarely repeats its own document id
    or revision date, so a sentence naming them is checked against this line (docs/11)."""
    if document is None:
        return "Document: (not recorded)"
    parts = [document.doc_type, document.document_id_external, f'"{document.title}"', document.publisher]
    found = [str(part) for part in parts if part]
    if document.revision_date:
        found.append(f"revision effective {document.revision_date.isoformat()}")
    if document.effective_date:
        found.append(f"effective {document.effective_date.isoformat()}")
    return "Document: " + ", ".join(found)


def _judge_text(answer: Answer) -> str:
    """The answer a judge reads: the body without its Sources list, else the summary."""
    body = answer.body_markdown or ""
    match = re.search(r"^##+\s*Sources\b", body, re.MULTILINE)
    body = body[: match.start()] if match else body
    return body.strip() or answer.summary


def _clip(text: str, limit: int = 90) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


# --- document resolution -------------------------------------------------------------


@dataclass(frozen=True)
class IndexEntry:
    descriptor: str
    url: str | None
    document_id_external: str | None
    revision_date: date | None
    effective_date: date | None
    needs_review: bool


@dataclass
class Target:
    """What a key's document descriptor resolves to, and how much to trust it."""

    descriptor: str
    ext_id: str | None = None
    urls: set[str] = field(default_factory=set)
    hosts: set[str] = field(default_factory=set)
    doc_type: str | None = None
    date: date | None = None
    needs_review: bool = False
    how: str = "unresolved"  # id | url | index | search | sources | unresolved


@lru_cache(maxsize=4)
def load_sources_index(path: str = str(SOURCES_INDEX)) -> dict[str, IndexEntry]:
    """`data/searchbench/sources/index.json` (docs/08 §2), keyed by descriptor."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    entries: dict[str, IndexEntry] = {}
    for item in payload.get("documents", []):
        entries[item["descriptor"]] = IndexEntry(
            descriptor=item["descriptor"],
            url=item.get("url"),
            document_id_external=item.get("document_id_external"),
            revision_date=_parse_date(item.get("revision_date")),
            effective_date=_parse_date(item.get("effective_date")),
            needs_review=bool(item.get("needs_review")),
        )
    return entries


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _norm_id(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def _site(url: str) -> str:
    return ".".join(sources.host_of(url).split(".")[-2:])


def id_from_url(url: str | None) -> str | None:
    """The MCD id CMS puts in its own URL (`lcdid=33822` -> `L33822`), as docmeta reads
    it. Live runs fetched L33822 under URLs that gave no document id at all."""
    params = {key.lower(): value.strip() for key, value in parse_qsl(urlsplit(url or "").query)}
    for param, prefix in (("lcdid", "L"), ("articleid", "A"), ("ncdid", "NCD")):
        if params.get(param, "").isdigit():
            return f"{prefix}{params[param]}"
    return None


def doc_external_id(document: Document) -> str | None:
    return document.document_id_external or id_from_url(document.url)


def doc_type_compatible(key_type: str | None, run_type: str | None) -> bool:
    """An untyped run document is compatible: docmeta leaves most pages untyped."""
    if not key_type or not run_type:
        return True
    left, right = key_type.strip().lower(), run_type.strip().lower()
    return left == right or any(left in group and right in group for group in _TYPE_GROUPS)


def resolve_descriptor(descriptor: str, key: AnswerKey, *, doc_type: str | None = None) -> Target:
    """An external id, a canonical URL, or a prose descriptor resolved through the sources
    index and the key's own source URLs (user decision, docs/11)."""
    text = descriptor.strip()
    target = Target(descriptor=text, doc_type=doc_type)
    if _EXT_ID.match(text):
        target.ext_id, target.how = _norm_id(text), "id"
    elif text.lower().startswith(("http://", "https://")):
        target.urls.add(sources.normalize_url(text))
        target.ext_id = id_from_url(text)
        target.how = "url"

    entry = load_sources_index().get(text)
    if entry is not None:
        if entry.url:
            target.urls.add(sources.normalize_url(entry.url))
        if entry.document_id_external and not target.ext_id:
            target.ext_id = _norm_id(entry.document_id_external)
        target.needs_review = entry.needs_review
        if not entry.needs_review:
            target.date = entry.revision_date or entry.effective_date
        if target.how == "unresolved":
            target.how = "search" if entry.needs_review else "index"

    for url in key.sources:
        url_id = id_from_url(url)
        if target.ext_id and url_id and _norm_id(url_id) == target.ext_id:
            target.urls.add(sources.normalize_url(url))
        elif not target.ext_id and target.how != "url":
            target.urls.add(sources.normalize_url(url))
            if target.how == "unresolved":
                target.how = "sources"
    target.hosts = {_target_site(url) for url in target.urls}
    return target


def _target_site(url: str) -> str:
    """`_site`, reading DailyMed as FDA: it republishes FDA-approved labels, and a key's
    "FDA Wegovy label" is the same document there (docs/11). Only that host, not nih.gov."""
    host = (urlsplit(url).hostname or "").lower()
    return "fda.gov" if host == "dailymed.nlm.nih.gov" else _site(url)


def matches_target(url: str | None, doc_type: str | None, ext_id: str | None, target: Target) -> str | None:
    """The rung a document matched on: id, then normalized URL, then host + doc type -
    the last only when the key names no id (docs/05 §2's fallback)."""
    if target.ext_id and ext_id and _norm_id(ext_id) == target.ext_id:
        return "id"
    if url and sources.normalize_url(url) in target.urls:
        return "url"
    if (
        not target.ext_id
        and url
        and target.hosts
        and _target_site(url) in target.hosts
        and doc_type_compatible(target.doc_type, doc_type)
    ):
        return "host+type"
    return None


def _citation_rung(citation: Citation, record: RunRecord, target: Target) -> str | None:
    document = record.documents.get(citation.doc_id) if citation.doc_id else None
    if document is not None:
        return matches_target(document.url, document.doc_type, doc_external_id(document), target)
    return matches_target(citation.url, None, id_from_url(citation.url), target)


# --- shared rules --------------------------------------------------------------------


def _not_applicable(key: str, reason: str) -> Score:
    return Score(key, None, f"not applicable: {reason}")


def _answer_of(record: RunRecord | None) -> Answer | None:
    return record.answer if record is not None else None


def _run_failed(key: str, record: RunRecord | None) -> Score:
    reason = (record.error or record.status) if record is not None else "no run record"
    return Score(key, 0.0, f"run failed: {_clip(str(reason), 160)}")


def _is_baseline(record: RunRecord) -> bool:
    return record.request.mode == "baseline"


def _judge_failed(key: str, meta: dict) -> Score:
    return Score(key, None, f"judge failed: {meta.get('judge_error', 'no result')}", {**meta, "error": True})


def judge_call(schema: type[BaseModel], prompt_name: str, check: Any = None, **values: object) -> tuple[Any, dict]:
    """One judge call on the evaluator model. Never raises.

    Always the base prompt set: evaluators must not drift with the prompts GEPA
    optimizes. The answer is substituted last, so text inside it that looks like a
    placeholder is never filled in.
    """
    answer = values.pop("answer", None)
    if answer is not None:
        values["answer"] = answer
    prompt = render(prompt_name, "base", **values)
    meta: dict[str, Any] = {}
    tokens = 0
    result = None
    # `check` names a verdict that parsed but covers none of what it was asked to grade;
    # that is retried once. A failure of both structured rungs is not retried.
    for attempt in range(JUDGE_ATTEMPTS):
        caller = structured("evaluator", schema)
        problem = None
        try:
            result = caller.invoke(prompt)
            meta["judge_mode"] = caller.last_mode
            problem = check(result) if check is not None else None
        except Exception as exc:  # noqa: BLE001 - a judge failure is a None score, not a lost row
            meta["judge_error"] = _clip(f"{type(exc).__name__}: {exc}", 300)
            result = None
        for message in getattr(caller, "messages", None) or []:
            input_tokens, output_tokens, _ = token_usage(message)
            tokens += input_tokens + output_tokens
        if result is None:
            break
        if problem is None:
            meta.pop("judge_error", None)
            break
        meta["judge_error"] = problem
        meta["judge_retries"] = attempt + 1
        result = None
    meta["judge_tokens"] = tokens
    return result, meta


def _covers(expected: set, judged: set, what: str) -> str | None:
    if expected and not expected & judged:
        return f"judge returned no verdict for any {what}"
    return None


# --- deterministic metrics -----------------------------------------------------------


def evidence_recall(record: RunRecord | None, bench: BenchRecord) -> Score:
    key = "evidence_recall"
    items = bench.answer_key.required_evidence
    if not items:
        return _not_applicable(key, "the answer key requires no evidence")
    if _answer_of(record) is None:
        return _run_failed(key, record)
    if _is_baseline(record):
        return Score(key, 0.0, "baseline: citations are URLs with no stored passage, so no required "
                     "evidence can be matched - 0 by construction")

    total = matched_weight = 0
    matched: list[str] = []
    unmatched: list[str] = []
    guessed: list[str] = []
    rungs: dict[str, str] = {}
    for item in items:
        weight = 2 if item.must else 1
        total += weight
        target = resolve_descriptor(item.document_id_external, bench.answer_key, doc_type=item.doc_type)
        if target.needs_review:
            guessed.append(item.id)
        document_seen = False
        hit: tuple[str, str] | None = None
        for evidence in record.evidence:
            document = record.documents.get(evidence.doc_id)
            if document is None:
                continue
            rung = matches_target(document.url, document.doc_type, doc_external_id(document), target)
            if rung is None:
                continue
            document_seen = True
            passage = fold(evidence.evidence_text)
            if not item.key_phrases or any(fold(phrase) in passage for phrase in item.key_phrases):
                hit = (rung, evidence.evidence_id)
                break
        label = f"{item.id}{' (must)' if item.must else ''}"
        if hit:
            matched_weight += weight
            rungs[item.id] = hit[0]
            matched.append(f"{label} via {hit[0]} ({hit[1]})")
        elif target.how == "unresolved":
            unmatched.append(f"{label} [{item.document_id_external}: descriptor resolves to no document]")
        elif document_seen:
            phrases = ", ".join(repr(phrase) for phrase in item.key_phrases)
            unmatched.append(f"{label} [{item.document_id_external}: document found, no passage containing {phrases}]")
        else:
            unmatched.append(f"{label} [{item.document_id_external}: no evidence from this document]")

    parts = []
    if matched:
        parts.append("matched " + "; ".join(matched))
    if unmatched:
        parts.append("unmatched " + "; ".join(unmatched))
    if guessed:
        parts.append("search-guessed descriptor (needs_review): " + ", ".join(guessed))
    return Score(
        key,
        round(matched_weight / total, 4),
        " | ".join(parts),
        {"matched": rungs, "needs_review": guessed},
    )


def citation_completeness(record: RunRecord | None, bench: BenchRecord) -> Score:
    key = "citation_completeness"
    answer = _answer_of(record)
    if answer is None:
        return _run_failed(key, record)
    found = sections(answer.body_markdown)
    parts = [text for heading, text in found.items() if heading.lower().startswith(("criteria", "codes"))]
    if parts:
        units = [unit for text in parts for unit in sentences(text)]
        scope = "Criteria / Details and Codes and documentation"

        def cited(unit: str) -> bool:
            return bool(_CITATION.search(unit))
    else:
        # No Criteria / Codes sections - the baseline's prose, whatever headings it uses
        # (docs/11): the whole answer minus a trailing list of links, where a URL, markdown
        # link or footnote marker counts as a citation.
        units = sentences(_strip_trailing_links(answer.body_markdown))
        scope = "whole answer (no Criteria / Codes sections)"

        def cited(unit: str) -> bool:
            return bool(
                _CITATION.search(unit) or _URL.search(unit) or _MARKDOWN_LINK.search(unit) or _FOOTNOTE.search(unit)
            )
    if not units:
        return _not_applicable(key, f"no sentences in {scope}")
    uncited = [unit for unit in units if not cited(unit)]
    count = len(units) - len(uncited)
    comment = f"{count}/{len(units)} cited in {scope}"
    if uncited:
        comment += "; uncited: " + "; ".join(f"'{_clip(unit, 80)}'" for unit in uncited[:3])
    return Score(key, round(count / len(units), 4), comment)


def _strip_trailing_links(body: str) -> str:
    lines = (body or "").splitlines()
    while lines:
        tail = _BULLET.sub("", lines[-1]).strip()
        if not tail or _URL.fullmatch(tail) or _MARKDOWN_LINK.fullmatch(tail) or tail.lower().rstrip(":") in {"sources", "references"}:
            lines.pop()
            continue
        break
    return "\n".join(lines)


def primary_source_ratio(record: RunRecord | None, bench: BenchRecord) -> Score:
    key = "primary_source_ratio"
    answer = _answer_of(record)
    if answer is None:
        return _run_failed(key, record)
    if not answer.citations:
        return _not_applicable(key, "the answer cites nothing")
    below: list[str] = []
    for citation in answer.citations:
        document = record.documents.get(citation.doc_id) if citation.doc_id else None
        tier = document.source_tier if document is not None else sources.tier_for(citation.url)
        if not sources.at_least(tier):
            below.append(f"[{citation.n}] {tier} {sources.host_of(citation.url)}")
    good = len(answer.citations) - len(below)
    comment = f"{good}/{len(answer.citations)} citations at official_secondary or better"
    if below:
        comment += "; below: " + ", ".join(below[:5])
    return Score(key, round(good / len(answer.citations), 4), comment)


def cost_metrics(record: RunRecord | None, bench: BenchRecord | None = None) -> list[Score]:
    """search_cost, latency_s and tokens (docs/05 §2), read from the run's usage."""
    if record is None:
        return [Score(key, None, "no run record to measure") for key in ("search_cost", "latency_s", "tokens")]
    usage = record.usage
    tokens_comment = f"{usage.input_tokens} in + {usage.output_tokens} out"
    if usage.input_tokens == 0 and usage.output_tokens > 0:
        tokens_comment += " (input tokens not reported)"
    return [
        Score("search_cost", usage.searches + usage.fetches, f"{usage.searches} searches + {usage.fetches} fetches"),
        Score("latency_s", float(usage.wall_seconds), f"{usage.wall_seconds}s wall clock"),
        Score("tokens", usage.input_tokens + usage.output_tokens, tokens_comment),
    ]


def _date_forms(value: date) -> list[str]:
    return [
        value.isoformat(),
        f"{value:%B} {value.day}, {value.year}",
        f"{value:%b}. {value.day}, {value.year}",
        f"{value:%b} {value.day}, {value.year}",
        f"{value.month:02d}/{value.day:02d}/{value.year}",
        f"{value.month}/{value.day}/{value.year}",
    ]


def currency(record: RunRecord | None, bench: BenchRecord, *, judge: bool = True) -> Score:
    """Governing documents cited, their governing date stated (in `effective_dates` or
    the answer text, user decision), and for change detection an ordering verdict."""
    key = "currency"
    governing = bench.answer_key.governing_documents
    if not governing:
        return _not_applicable(key, "the answer key names no governing document")
    answer = _answer_of(record)
    if answer is None:
        return _run_failed(key, record)

    dated_text = fold(" ".join(answer.effective_dates) + "\n" + answer.body_markdown)
    cited_parts: list[float] = []
    date_parts: list[float] = []
    notes: list[str] = []
    for descriptor in governing:
        target = resolve_descriptor(descriptor, bench.answer_key)
        cited = any(_citation_rung(citation, record, target) for citation in answer.citations)
        cited_parts.append(1.0 if cited else 0.0)
        note = f"{descriptor}: {'cited' if cited else 'not cited'}"
        if target.date is None:
            note += "; no governing date on record" + (" (search-guessed index entry)" if target.needs_review else "")
        else:
            found = any(fold(form) in dated_text for form in _date_forms(target.date))
            date_parts.append(1.0 if found else 0.0)
            note += f"; governing date {target.date.isoformat()} {'stated' if found else 'not stated'}"
        notes.append(note)

    parts = [_mean(cited_parts)]
    if date_parts:
        parts.append(_mean(date_parts))
    meta: dict[str, Any] = {}
    if bench.question_type == "change_detection":
        if not judge:
            return Score(key, None, "judge not run (change-detection ordering)")
        result, meta = judge_call(
            OrderJudgment, "eval_currency_order",
            question=bench.question, key_summary=bench.answer_key.summary, answer=_judge_text(answer),
        )
        if result is None:
            return _judge_failed(key, meta)
        parts.append(_ORDER_SCORES[result.verdict])
        notes.append(f"order: {result.verdict}" + (f" ({_clip(result.reason, 120)})" if result.reason else ""))
    return Score(key, round(_mean(parts), 4), "; ".join(notes), meta)


# --- judge metrics -------------------------------------------------------------------


def _render_claims(key: AnswerKey) -> str:
    return "\n".join(
        f"- {claim.id}{' (must)' if claim.must else ''}: {claim.text}" for claim in key.required_claims
    ) or "(none)"


def _render_forbidden(key: AnswerKey) -> str:
    return "\n".join(f"- {claim.id}: {claim.text}" for claim in key.forbidden_claims) or "(none)"


def answer_correctness(
    record: RunRecord | None, bench: BenchRecord, *, judge: bool = True, votes: int = ANSWER_JUDGE_VOTES
) -> list[Score]:
    """answer_correctness and search_efficiency, which needs it (separate evaluators
    cannot see each other's scores). The judge is asked `votes` times, concurrently, and
    the verdicts are merged by majority (`_majority`)."""
    key = "answer_correctness"
    answer_key = bench.answer_key
    answer = _answer_of(record)
    if answer is None:
        score = _run_failed(key, record)
    elif not judge:
        score = Score(key, None, "judge not run")
    else:

        def one_vote(_: int) -> tuple[AnswerCorrectnessJudgment | None, dict]:
            return judge_call(
                AnswerCorrectnessJudgment, "eval_answer_correctness",
                question=bench.question, key_summary=answer_key.summary,
                required_claims=_render_claims(answer_key), forbidden_claims=_render_forbidden(answer_key),
                answer=_judge_text(answer),
                check=lambda result: _covers(
                    {claim.id for claim in answer_key.required_claims}, {claim.id for claim in result.claims}, "required claim"
                )
                or _covers(
                    {claim.id for claim in answer_key.forbidden_claims}, {item.id for item in result.forbidden}, "forbidden claim"
                ),
            )

        count = max(1, votes)
        with ThreadPoolExecutor(max_workers=count) as pool:
            ballots = list(pool.map(one_vote, range(count)))
        results = [result for result, _ in ballots if result is not None]
        meta = _vote_meta([meta for _, meta in ballots], len(results))
        score = _judge_failed(key, meta) if not results else _grade_answer(_majority(results, answer_key), answer_key, meta)
    return [score, _search_efficiency(score, record)]


def _majority(results: Sequence[AnswerCorrectnessJudgment], key: AnswerKey) -> AnswerCorrectnessJudgment:
    """One verdict from several judge calls.

    A required claim takes the status more than half the calls gave it; without a
    majority it is missing (unconfirmed is not present), and a claim most calls omitted
    stays omitted. A forbidden claim counts as asserted only on a majority. The summary
    takes the median grade, and a tie between two calls goes to the lower one.
    """
    half = len(results) / 2
    claims: list[ClaimJudgment] = []
    for claim in key.required_claims:
        votes = [next((item for item in result.claims if item.id == claim.id), None) for result in results]
        if sum(vote is None for vote in votes) > half:
            continue
        statuses = [vote.status if vote is not None else "missing" for vote in votes]
        status = next((option for option in _STATUS_ORDER if statuses.count(option) > half), None)
        chosen = next((vote for vote in votes if vote is not None and vote.status == status), None)
        if chosen is None:
            chosen = ClaimJudgment(id=claim.id, status="missing", reason="judges disagreed: " + "/".join(statuses))
        claims.append(chosen)
    forbidden: list[ForbiddenJudgment] = []
    for item in key.forbidden_claims:
        votes = [next((vote for vote in result.forbidden if vote.id == item.id), None) for result in results]
        asserted = [vote for vote in votes if vote is not None and vote.asserted]
        if len(asserted) > half:
            forbidden.append(asserted[0])
        elif any(vote is not None for vote in votes):
            forbidden.append(ForbiddenJudgment(id=item.id, asserted=False))
    grades = sorted(_SUMMARY_ORDER.index(result.summary_consistency) for result in results)
    summary = _SUMMARY_ORDER[grades[(len(grades) - 1) // 2]]
    return AnswerCorrectnessJudgment(claims=claims, forbidden=forbidden, summary_consistency=summary)


def _vote_meta(metas: Sequence[dict], counted: int) -> dict:
    """Metadata for a majority verdict: tokens and retries summed over every call."""
    meta: dict[str, Any] = {
        "judge_tokens": sum(item.get("judge_tokens", 0) for item in metas),
        "judge_votes": counted,
        "judge_calls": len(metas),
    }
    modes = sorted({item["judge_mode"] for item in metas if item.get("judge_mode")})
    if modes:
        meta["judge_mode"] = "+".join(modes)
    retries = sum(item.get("judge_retries", 0) for item in metas)
    if retries:
        meta["judge_retries"] = retries
    if counted == 0:
        meta["judge_error"] = next((item["judge_error"] for item in metas if item.get("judge_error")), "no result")
    elif counted < len(metas):
        meta["judge_failed_votes"] = len(metas) - counted
    return meta


def _grade_answer(result: AnswerCorrectnessJudgment, key: AnswerKey, meta: dict) -> Score:
    by_id = {claim.id: claim for claim in result.claims}
    total = present = 0
    missing: list[str] = []
    incorrect: list[str] = []
    for claim in key.required_claims:
        weight = 2 if claim.must else 1
        total += weight
        judged = by_id.get(claim.id)
        label = f"{claim.id}{' (must)' if claim.must else ''}"
        if judged is not None and judged.status == "present":
            present += weight
        elif judged is not None and judged.status == "incorrect":
            incorrect.append(f"{label} - {_clip(judged.reason or judged.quote, 120)}")
        else:
            missing.append(label + ("" if judged is not None else " (judge omitted)"))
    claims_score = present / total if total else 1.0
    summary = result.summary_consistency
    value = CLAIMS_WEIGHT * claims_score + SUMMARY_WEIGHT * _SUMMARY_SCORES[summary]
    known = {claim.id for claim in key.forbidden_claims}
    asserted = [item for item in result.forbidden if item.asserted and item.id in known]
    if asserted:
        value = min(value, FORBIDDEN_CAP)

    parts = [f"claims {present}/{total} weighted present"]
    if missing:
        parts.append("missing: " + ", ".join(missing))
    if incorrect:
        parts.append("incorrect: " + "; ".join(incorrect))
    if asserted:
        parts.append("forbidden asserted: " + "; ".join(f"{item.id} '{_clip(item.quote, 80)}'" for item in asserted))
    parts.append(f"summary: {summary}")
    return Score("answer_correctness", round(value, 4), "; ".join(parts), meta)


def _search_efficiency(correctness: Score, record: RunRecord | None) -> Score:
    key = "search_efficiency"
    if correctness.score is None or record is None:
        return Score(key, None, "no answer_correctness to divide")
    calls = record.usage.searches + record.usage.fetches
    value = correctness.score / max(1, calls) * 10
    return Score(key, round(value, 4), f"answer_correctness {correctness.score} / max(1, {calls} calls) x 10")


def _sample(items: Sequence[str], size: int) -> list[int]:
    """Evenly spaced indices: deterministic (noise control), and spread across sections
    instead of piling into the Answer section as "the first eight" would."""
    count = len(items)
    if count <= size:
        return list(range(count))
    return sorted({round(index * (count - 1) / (size - 1)) for index in range(size)})


def citation_correctness(record: RunRecord | None, bench: BenchRecord, *, judge: bool = True) -> Score:
    key = "citation_correctness"
    answer = _answer_of(record)
    if answer is None:
        return _run_failed(key, record)
    if _is_baseline(record):
        return Score(key, 0.0, "baseline: citations are URLs with no stored passage to check a sentence "
                     "against - 0 by construction")
    cited = [unit for unit in sentences(_claims_text(answer)) if _CITATION.search(unit)]
    if not cited:
        return Score(key, 0.0, "no cited sentences")

    by_number = {citation.n: citation for citation in answer.citations}
    evidence = {item.evidence_id: item for item in record.evidence}
    sampled = [cited[index] for index in _sample(cited, CITATION_SAMPLE)]
    unmapped: set[int] = set()
    blocks: list[str] = []
    for position, sentence in enumerate(sampled):
        passages: list[str] = []
        for number in dict.fromkeys(int(value) for value in _CITATION.findall(sentence)):
            citation = by_number.get(number)
            item = evidence.get(citation.evidence_id) if citation is not None else None
            if item is not None:
                header = _document_header(record.documents.get(item.doc_id))
                passages.append(f"[{number}] {header}\n{item.evidence_text}")
        if not passages:
            unmapped.add(position)
            continue
        blocks.append(
            f"Item {position}\nSentence: {sentence}\nPassages:\n"
            + "\n".join(passages[:MAX_PASSAGES_PER_SENTENCE])
        )

    judged: dict[int, SentenceJudgment] = {}
    meta: dict[str, Any] = {}
    if blocks:
        if not judge:
            return Score(key, None, "judge not run")
        result, meta = judge_call(
            CitationJudgment, "eval_citation_correctness", question=bench.question, items="\n\n".join(blocks),
            check=lambda result: _covers(
                set(range(len(sampled))) - unmapped, {item.index for item in result.items}, "cited sentence"
            ),
        )
        if result is None:
            return _judge_failed(key, meta)
        judged = {item.index: item for item in result.items}

    supported = 0
    failing: list[str] = []
    for position, sentence in enumerate(sampled):
        numbers = "".join(f"[{value}]" for value in dict.fromkeys(_CITATION.findall(sentence)))
        if position in unmapped:
            failing.append(f"{numbers} maps to no passage: '{_clip(sentence, 70)}'")
            continue
        verdict = judged.get(position)
        if verdict is not None and verdict.supported:
            supported += 1
        else:
            reason = verdict.reason if verdict is not None else "judge omitted this item"
            failing.append(f"{numbers} '{_clip(sentence, 70)}' - {_clip(reason, 100)}")
    comment = f"{supported}/{len(sampled)} sampled cited sentences supported (of {len(cited)} cited)"
    if failing:
        comment += "; failing: " + "; ".join(failing)
    return Score(key, round(supported / len(sampled), 4), comment, meta)


def contradiction_handling(record: RunRecord | None, bench: BenchRecord, *, judge: bool = True) -> Score:
    key = "contradiction_handling"
    expected = bench.answer_key.expected_contradictions
    if not expected:
        return _not_applicable(key, "the answer key expects no contradiction")
    answer = _answer_of(record)
    if answer is None:
        return _run_failed(key, record)
    if not judge:
        return Score(key, None, "judge not run")
    result, meta = judge_call(
        ContradictionJudgment, "eval_contradiction",
        question=bench.question, key_summary=bench.answer_key.summary,
        governing_documents="; ".join(bench.answer_key.governing_documents) or "(none)",
        expected_contradictions="\n".join(f"x{index}. {text}" for index, text in enumerate(expected, start=1)),
        contradiction_lines="\n".join(f"- {line}" for line in answer.contradictions) or "(none recorded)",
        answer=_judge_text(answer),
        check=lambda result: _covers(
            set(range(1, len(expected) + 1)), {item.index for item in result.items}, "expected contradiction"
        ),
    )
    if result is None:
        return _judge_failed(key, meta)
    judged = {item.index: item for item in result.items}
    values: list[float] = []
    notes: list[str] = []
    for index, text in enumerate(expected, start=1):
        item = judged.get(index)
        surfaced = bool(item and item.surfaced)
        governing = bool(item and item.surfaced and item.governing_stated)
        values.append(0.5 * surfaced + 0.5 * governing)
        state = "surfaced, governing stated" if governing else "surfaced, governing not stated" if surfaced else "not surfaced"
        notes.append(f"x{index} '{_clip(text, 60)}': {state}")
    return Score(key, round(_mean(values), 4), "; ".join(notes), meta)


def scope_handling(record: RunRecord | None, bench: BenchRecord, *, judge: bool = True) -> Score:
    """Triggered by a non-null `expected_scope_warning` (docs/11). The warning counts in
    `Answer.scope_warning` or stated in the text (user decision)."""
    key = "scope_handling"
    warning = bench.answer_key.expected_scope_warning
    if warning is None:
        return _not_applicable(key, "the answer key expects no scope warning")
    answer = _answer_of(record)
    if answer is None:
        return _run_failed(key, record)
    if not judge:
        return Score(key, None, "judge not run")
    result, meta = judge_call(
        ScopeJudgment, "eval_scope",
        question=bench.question, expected_scope_warning=warning,
        key_summary=bench.answer_key.summary, answer=_judge_text(answer),
    )
    if result is None:
        return _judge_failed(key, meta)
    in_field = bool(answer.scope_warning and answer.scope_warning.strip())
    flagged = in_field or result.scope_flagged_in_text
    value = 0.5 * flagged + 0.5 * (not result.fabricated_criteria)
    where = "scope_warning field" if in_field else "stated in text" if flagged else "not flagged"
    comment = f"scope: {where}; " + (
        "fabricated: " + "; ".join(f"'{_clip(item, 80)}'" for item in result.fabricated_criteria)
        if result.fabricated_criteria
        else "no fabricated payer criteria"
    )
    return Score(key, round(value, 4), comment, meta)


# --- assembly ------------------------------------------------------------------------


def score_record(record: RunRecord | None, bench: BenchRecord, *, judge: bool = True) -> dict[str, Score]:
    """Every metric for one run. An evaluator that raises becomes a None score with the
    error in its comment, never a lost row."""
    steps: list[tuple[tuple[str, ...], Callable[[], Score | list[Score]]]] = [
        (("evidence_recall",), lambda: evidence_recall(record, bench)),
        (("citation_completeness",), lambda: citation_completeness(record, bench)),
        (("primary_source_ratio",), lambda: primary_source_ratio(record, bench)),
        (("search_cost", "latency_s", "tokens"), lambda: cost_metrics(record)),
        (("currency",), lambda: currency(record, bench, judge=judge)),
        (("citation_correctness",), lambda: citation_correctness(record, bench, judge=judge)),
        (("contradiction_handling",), lambda: contradiction_handling(record, bench, judge=judge)),
        (("scope_handling",), lambda: scope_handling(record, bench, judge=judge)),
        (("answer_correctness", "search_efficiency"), lambda: answer_correctness(record, bench, judge=judge)),
    ]
    scores: dict[str, Score] = {}
    for keys, step in steps:
        for score in _safely(keys, step):
            scores[score.key] = score
    return {key: scores[key] for key in METRIC_KEYS if key in scores}


def _safely(keys: Sequence[str], step: Callable[[], Score | list[Score]]) -> list[Score]:
    try:
        result = step()
    except Exception as exc:  # noqa: BLE001 - see score_record
        message = _clip(f"evaluator error: {type(exc).__name__}: {exc}", 300)
        return [Score(key, None, message, {"error": True}) for key in keys]
    return result if isinstance(result, list) else [result]


def composite(scores: Mapping[str, Any]) -> float | None:
    """docs/05 §2's scalar. A not-applicable component takes answer_correctness,
    extending 05's own "else answer_correctness" rule; clamped to [0, 1] (docs/11).

    A judge failure is not "not applicable": if any score carries `metadata.error` the
    composite is None until re-scored, rather than borrowing answer_correctness."""
    for item in scores.values():
        metadata = item.metadata if isinstance(item, Score) else item.get("metadata") if isinstance(item, dict) else None
        if (metadata or {}).get("error"):
            return None

    def value(key: str) -> float | None:
        item = scores.get(key)
        if isinstance(item, Score):
            return item.score
        return item.get("score") if isinstance(item, dict) else item

    correctness = value("answer_correctness")
    if correctness is None:
        return None

    def component(key: str) -> float:
        found = value(key)
        return correctness if found is None else float(found)

    handling = value("contradiction_handling")
    if handling is None:
        handling = value("scope_handling")
    if handling is None:
        handling = correctness
    calls = value("search_cost") or 0
    raw = (
        0.40 * correctness
        + 0.20 * component("evidence_recall")
        + 0.20 * component("citation_correctness")
        + 0.10 * component("currency")
        + 0.10 * handling
        - 0.002 * max(0, calls - 15)
    )
    return round(min(1.0, max(0.0, raw)), 4)


def feedback_text(scores: Mapping[str, Score]) -> str:
    """The comments GEPA reads, one line per metric in docs/05 §2's order."""
    lines = []
    for key in METRIC_KEYS:
        score = scores.get(key)
        if score is not None:
            shown = "n/a" if score.score is None else score.score
            lines.append(f"{key}={shown}: {score.comment}")
    return "\n".join(lines)


# --- LangSmith wrappers --------------------------------------------------------------


def record_from_run(run: Any) -> RunRecord | None:
    """The bench target returns the RunRecord in its outputs: the only thing an
    evaluator sees of a run."""
    data = (getattr(run, "outputs", None) or {}).get("record")
    if not data:
        return None
    try:
        return RunRecord.model_validate(data)
    except Exception:  # noqa: BLE001 - an unreadable record is a failed run
        return None


def bench_from_example(example: Any) -> BenchRecord:
    metadata = dict(getattr(example, "metadata", None) or {})
    split = metadata.get("dataset_split")
    if isinstance(split, list):
        split = split[0] if split else None
    inputs = getattr(example, "inputs", None) or {}
    return BenchRecord.model_validate(
        {
            "id": metadata.get("id") or inputs.get("question_id"),
            "domain": metadata.get("domain"),
            "tier": metadata.get("tier"),
            "question_type": metadata.get("question_type"),
            "question": inputs.get("question"),
            "split": split or "dev",
            "answer_key": getattr(example, "outputs", None) or {},
        }
    )


def _langsmith(name: str, keys: tuple[str, ...], score: Callable[[RunRecord | None, BenchRecord], Score | list[Score]]):  # noqa: ANN202
    def evaluator(run: Any, example: Any) -> dict[str, Any]:
        try:
            results = score(record_from_run(run), bench_from_example(example))
        except Exception as exc:  # noqa: BLE001 - LangSmith would log it without our keys
            message = _clip(f"evaluator error: {type(exc).__name__}: {exc}", 300)
            results = [Score(key, None, message, {"error": True}) for key in keys]
        results = results if isinstance(results, list) else [results]
        if len(results) == 1:
            return results[0].to_langsmith()
        return {"results": [item.to_langsmith() for item in results]}

    evaluator.__name__ = name
    return evaluator


EVALUATORS = [
    _langsmith("evidence_recall", ("evidence_recall",), evidence_recall),
    _langsmith("citation_completeness", ("citation_completeness",), citation_completeness),
    _langsmith("primary_source_ratio", ("primary_source_ratio",), primary_source_ratio),
    _langsmith("cost_metrics", ("search_cost", "latency_s", "tokens"), cost_metrics),
    _langsmith("currency", ("currency",), currency),
    _langsmith("citation_correctness", ("citation_correctness",), citation_correctness),
    _langsmith("contradiction_handling", ("contradiction_handling",), contradiction_handling),
    _langsmith("scope_handling", ("scope_handling",), scope_handling),
    _langsmith("answer_correctness", ("answer_correctness", "search_efficiency"), answer_correctness),
]

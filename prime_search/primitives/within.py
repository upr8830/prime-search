"""BM25 over the paragraphs of a fetched document (docs/01 §5, docs/03 §4).

Local only — no Tavily call, no model — and budgeted separately as
`max_deep_reads = 10` (docs/01 §3).

Two things the live documents forced (measured 2026-09-12):

* A single paragraph can be enormous: L33822's revision-history table is 16,054
  characters and A52464's ICD-10 table is 51,964. docs/04 §2 requires a table to stay
  one paragraph, so the paragraph is preserved and the *index* is built over
  overlapping windows that all carry their parent's `paragraph_index`. A returned
  passage is therefore still citable — its offsets slice the persisted text — without
  pushing 50 KB into an agent's context.
* `BM25Okapi` returns *negative* scores for terms that occur in more than half the
  corpus, so "relevant" cannot mean "score > 0". Relevance is query-token overlap;
  the score only orders.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from prime_search.primitives.docmeta import Paragraph, normalize_text, split_paragraphs
from prime_search.schemas import Document, Location

MAX_PASSAGE_CHARS = 2000  # window size for an oversized paragraph
WINDOW_OVERLAP = 200  # so a sentence spanning two windows still matches one of them
# rank_bm25's current defaults, pinned: a library default change would silently
# re-rank every deep read and surface only as a bench regression.
BM25_K1, BM25_B, BM25_EPSILON = 1.5, 0.75, 0.25

# Keeps HCPCS/ICD/NCD tokens whole: a4239, e2103, icd-10, 40.2, cms-1780-f.
_TOKEN = re.compile(r"[a-z0-9]+(?:[./-][a-z0-9]+)*")

_MAX_CACHED_INDEXES = 32


def tokenize(text: str) -> list[str]:
    """One tokenizer for corpus and query. No stopword list: BM25's idf already
    discounts frequent terms, and dropping "insulin" would be fatal here."""
    return _TOKEN.findall((text or "").lower())


@dataclass(frozen=True, slots=True)
class Passage:
    paragraph_index: int
    section: str | None
    text: str
    char_start: int
    char_end: int
    score: float

    def as_dict(self) -> dict[str, object]:
        """docs/03 §4 promises paragraph indices and text; the offsets and score are
        additive, so the root can rank and `add_evidence` can build a Location."""
        return {
            "paragraph_index": self.paragraph_index,
            "section": self.section,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "score": round(self.score, 4),
        }

    def location(self) -> Location:
        return Location(
            section=self.section,
            paragraph_index=self.paragraph_index,
            char_start=self.char_start,
            char_end=self.char_end,
        )


def load_text(document: Document) -> str:
    if not document.is_fetched or not document.text_path:
        raise ValueError(
            f"{document.doc_id} is {document.fetch_method}: call fetch() before "
            "search_within (docs/04 §3 rule 1 — a snippet is never evidence)"
        )
    return Path(document.text_path).read_text(encoding="utf-8")


def load_paragraphs(document: Document) -> list[Paragraph]:
    """Paragraphs of a persisted document, sliced from the file using the sidecar
    offsets so text, offsets and `paragraph_count` cannot drift apart (docs/04 §3)."""
    text = load_text(document)
    sidecar = Path(document.text_path).with_suffix(".meta.json")
    if sidecar.is_file():
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        # The sidecar records the sha1 of the text it was built from. Checking it is
        # the only way to catch a text file that was rewritten while the sidecar was
        # not: the paragraph count can match while every offset has moved, and every
        # citation built on those offsets would point at the wrong words.
        recorded = payload.get("text_sha1")
        actual = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if recorded and recorded != actual:
            raise ValueError(
                f"{document.doc_id}: text on disk does not match the sidecar it was "
                f"indexed from ({actual[:12]} vs {recorded[:12]}) — refetch, because "
                "the paragraph offsets are stale (docs/04 §3)"
            )
        paragraphs = [
            Paragraph(
                index=row["index"],
                text=text[row["char_start"] : row["char_end"]],
                char_start=row["char_start"],
                char_end=row["char_end"],
                section=row["section"],
                boilerplate=row["boilerplate"],
            )
            for row in payload["paragraphs"]
        ]
    else:
        paragraphs = split_paragraphs(normalize_text(text))
    if len(paragraphs) != document.paragraph_count:
        raise ValueError(
            f"{document.doc_id}: {len(paragraphs)} paragraphs on disk vs "
            f"{document.paragraph_count} on the Document — refetch, because evidence "
            "offsets would be wrong (docs/04 §3)"
        )
    return paragraphs


def _windows(paragraph: Paragraph) -> list[tuple[int, int]]:
    """Absolute offsets of the windows a paragraph is indexed as."""
    length = paragraph.char_end - paragraph.char_start
    if length <= MAX_PASSAGE_CHARS:
        return [(paragraph.char_start, paragraph.char_end)]
    step = MAX_PASSAGE_CHARS - WINDOW_OVERLAP
    return [
        (
            paragraph.char_start + offset,
            min(paragraph.char_start + offset + MAX_PASSAGE_CHARS, paragraph.char_end),
        )
        for offset in range(0, length, step)
    ]


# Keyed by (doc_id, sha1 of the text), so an edited or refetched document can never
# answer from a stale index.
_index_cache: dict[tuple[str, str], tuple[BM25Okapi, list[Passage], list[set[str]]]] = {}


def _index(document: Document) -> tuple[BM25Okapi, list[Passage], list[set[str]]]:
    text = load_text(document)
    key = (document.doc_id, hashlib.sha1(text.encode("utf-8")).hexdigest())
    paragraphs = load_paragraphs(document)  # before the cache: the drift guard in
    # load_paragraphs has to run on every call, or a Document whose paragraph_count
    # no longer matches the file is served happily from a warm index.
    cached = _index_cache.get(key)
    if cached is not None:
        return cached

    passages: list[Passage] = []
    corpus: list[list[str]] = []
    for paragraph in paragraphs:
        if paragraph.boilerplate:
            continue  # nav, banners and the AMA/AHA license blocks are not content
        for start, end in _windows(paragraph):
            body = text[start:end]
            passages.append(Passage(paragraph.index, paragraph.section, body, start, end, 0.0))
            # Heading tokens ride along, so "coding information" reaches its section.
            corpus.append(tokenize(f"{paragraph.section or ''} {body}"))
    if not corpus:
        raise ValueError(f"{document.doc_id}: no content paragraphs to search")

    entry = (
        BM25Okapi(corpus, k1=BM25_K1, b=BM25_B, epsilon=BM25_EPSILON),
        passages,
        [set(tokens) for tokens in corpus],
    )
    if len(_index_cache) >= _MAX_CACHED_INDEXES:
        _index_cache.clear()  # bounded; rebuilding is cheap next to a fetch
    _index_cache[key] = entry
    return entry


def search_within(document: Document, query: str, k: int = 5) -> list[Passage]:
    """docs/03 §4: BM25 over paragraphs; returns paragraph indices and text.

    At most one window per paragraph, so `k=5` cannot be filled with five slices of
    the same table. Deterministic: score descending, then document order.
    """
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return []
    bm25, passages, token_sets = _index(document)
    scores = bm25.get_scores(sorted(query_tokens))
    ranked = sorted(
        (
            Passage(
                passage.paragraph_index,
                passage.section,
                passage.text,
                passage.char_start,
                passage.char_end,
                float(score),
            )
            for passage, tokens, score in zip(passages, token_sets, scores, strict=True)
            if query_tokens & tokens  # relevance is overlap; BM25Okapi scores go negative
        ),
        key=lambda passage: (-passage.score, passage.paragraph_index, passage.char_start),
    )
    best: dict[int, Passage] = {}
    for passage in ranked:
        if passage.paragraph_index not in best:
            best[passage.paragraph_index] = passage
        if len(best) == k:
            break
    return sorted(best.values(), key=lambda passage: (-passage.score, passage.paragraph_index))


def clear_index_cache() -> None:
    _index_cache.clear()

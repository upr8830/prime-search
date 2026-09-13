"""The SearchBench record, as Pydantic (docs/05 §1).

**Why this is not in `prime_search/schemas.py`.** CLAUDE.md ties that module to
`docs/02`, and `docs/02` has no bench record — `docs/05` §1 defines this shape, and the
only thing `prime_search` knows about SearchBench is `RunRequest.question_id`. Putting
it there would add an eval-side dependency to the runtime package and put a schema in
`schemas.py` that `docs/02` does not describe, which is exactly the drift CLAUDE.md's
rule exists to prevent.

Validating on load is not ceremony. Every key in `searchbench_v0.jsonl` is a **draft**
(`validated_by: null`, `docs/08` §9), it will be hand-edited during task 2.1's
validation pass, and a typo introduced there would otherwise surface as a confusing
evaluator failure on Day 2 rather than as a parse error the moment it is saved.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

DATASET = Path("data/searchbench/searchbench_v0.jsonl")

# docs/08 §6: train 15, dev 5, holdout 10.
SPLIT_SIZES = {"train": 15, "dev": 5, "holdout": 10}

__all__ = [
    "DATASET",
    "SPLIT_SIZES",
    "AnswerKey",
    "BenchRecord",
    "ForbiddenClaim",
    "RequiredClaim",
    "RequiredEvidence",
    "load_records",
]


class RequiredClaim(BaseModel):
    """docs/08 §5: 2-6 atomic statements, `must` for the ones without which the answer
    is wrong. The `answer_correctness` evaluator weights `must` claims 2x (docs/05 §2)."""

    id: str
    text: str
    must: bool


class RequiredEvidence(BaseModel):
    """docs/08 §5: the document(s) and 1-3 key phrases that must appear in cited
    evidence text."""

    id: str
    document_id_external: str
    doc_type: str
    key_phrases: list[str] = Field(default_factory=list)
    must: bool


class ForbiddenClaim(BaseModel):
    """docs/08 §5: a statement that is stale or false, with the reason. An answer that
    asserts one of these is wrong even if everything else is right."""

    id: str
    text: str
    reason: str


class AnswerKey(BaseModel):
    """docs/05 §1. `as_of` and `validated_by` are null until a human completes
    `docs/08` §2 step 3 — which is the whole point of the provenance design in §1, so
    they are optional here rather than being filled in with a default."""

    as_of: date | None = None
    summary: str
    required_claims: list[RequiredClaim] = Field(default_factory=list)
    required_evidence: list[RequiredEvidence] = Field(default_factory=list)
    governing_documents: list[str] = Field(default_factory=list)
    expected_contradictions: list[str] = Field(default_factory=list)
    expected_scope_warning: str | None = None
    forbidden_claims: list[ForbiddenClaim] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    validated_by: str | None = None
    validation_notes: str = ""

    @property
    def is_validated(self) -> bool:
        """docs/08 §2 step 3. A run against unvalidated keys measures the author's
        memory, not the system, so the bench runner must be able to refuse."""
        return bool(self.validated_by) and self.as_of is not None

    @property
    def must_claims(self) -> list[RequiredClaim]:
        return [claim for claim in self.required_claims if claim.must]


class BenchRecord(BaseModel):
    """One SearchBench question (docs/05 §1, docs/08 §3-§5)."""

    id: str
    domain: Literal["cgm", "glp1", "cross", "other"]
    tier: int = Field(ge=1, le=4)  # docs/08 §3: 1 easy .. 4 adversarial
    question_type: Literal[
        "eligibility",
        "coding",
        "coverage_pathway",
        "change_detection",
        "contradiction",
        "out_of_scope",
        "other",
    ]
    question: str
    split: Literal["train", "dev", "holdout"]
    answer_key: AnswerKey

    @property
    def is_out_of_scope(self) -> bool:
        """docs/08 §4: "Out-of-scope questions must have an `expected_scope_warning`
        and no `required_evidence`"."""
        return self.question_type == "out_of_scope"


def load_records(path: Path | str = DATASET) -> list[BenchRecord]:
    """Parse and validate the dataset.

    Errors name the line and the record id, because the file is hand-edited during
    task 2.1 and "line 17 (glp1-path-002): ..." is the difference between a two-second
    fix and a hunt through 30 JSON objects on one line each.
    """
    return list(iter_records(path))


def iter_records(path: Path | str = DATASET) -> Iterator[BenchRecord]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"SearchBench dataset not found: {source}")
    with source.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except ValueError as exc:
                raise ValueError(f"{source}:{number}: not valid JSON: {exc}") from exc
            try:
                yield BenchRecord.model_validate(payload)
            except Exception as exc:
                identifier = payload.get("id", "<no id>") if isinstance(payload, dict) else "?"
                raise ValueError(f"{source}:{number} ({identifier}): {exc}") from exc

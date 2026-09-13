"""SearchBench: the 30-question benchmark and the tools that build and sync it.

`docs/08` is the construction spec, `docs/05` §1 the record schema. The pieces land in
the order `docs/08` §2 lists them: `fetch_sources.py` (step 2, task 1.8), human
validation (step 3, task 2.1), `sync.py` (step 4, task 2.1).
"""

from eval.searchbench.schema import (
    AnswerKey,
    BenchRecord,
    ForbiddenClaim,
    RequiredClaim,
    RequiredEvidence,
    load_records,
)

__all__ = [
    "AnswerKey",
    "BenchRecord",
    "ForbiddenClaim",
    "RequiredClaim",
    "RequiredEvidence",
    "load_records",
]

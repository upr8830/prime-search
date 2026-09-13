"""Patient-level detail in free text (CLAUDE.md: no PHI, not even synthetic).

docs/01 §8: "the API rejects inputs that look like patient records (simple heuristic:
MRN/DOB patterns) with a clear message". The same patterns already guarded the
SearchBench tooling (`eval/searchbench/fetch_sources.py`); they live here so the API and
the dataset checks cannot drift apart.

Deliberately narrow: "a type 2 diabetic not on insulin" is a policy population, not a
person. What is caught is an identified individual — a named patient, a date of birth,
a record number, or a specific lab value.
"""

from __future__ import annotations

import re

__all__ = ["LAB_VALUE", "PATIENT_PATTERNS", "patient_details"]

LAB_VALUE = "a lab value"

PATIENT_PATTERNS = (
    ("a date of birth", re.compile(r"\bDOB\b|\bdate of birth\b", re.IGNORECASE)),
    ("a named patient", re.compile(r"\b(?:my|the)\s+patient\s+[A-Z][a-z]+\b")),
    (LAB_VALUE, re.compile(r"\bA1c\s*[:=]?\s*\d", re.IGNORECASE)),
    ("a medical record number", re.compile(r"\b(?:MRN|member id|policy no)\b", re.IGNORECASE)),
)


def patient_details(text: str | None, *, include_lab_values: bool = True) -> list[str]:
    """Which patient-level identifiers `text` carries, if any.

    The API passes `include_lab_values=False`: a coverage question legitimately quotes a
    threshold ("an A1c of 7.5 or higher"), and rejecting it would block the policy
    questions the system exists to answer (docs/11). The dataset checks keep the rule.
    """
    if not text:
        return []
    return [
        label
        for label, pattern in PATIENT_PATTERNS
        if (include_lab_values or label != LAB_VALUE) and pattern.search(text)
    ]

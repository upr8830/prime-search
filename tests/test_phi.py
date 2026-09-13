"""The shared patient-detail guard (docs/01 §8). Placeholder names only: the point is the
shape of an identified individual, never a realistic record."""

from __future__ import annotations

from prime_search.phi import patient_details


def test_identifiers_are_flagged() -> None:
    assert patient_details("Patient MRN 12345, is a CGM covered?") == ["a medical record number"]
    assert "a date of birth" in patient_details("DOB 01/01/1900, CGM covered?")
    assert "a named patient" in patient_details("Can my patient Placeholder get a CGM?")


def test_a_policy_population_is_not_a_patient() -> None:
    assert patient_details("Is a CGM covered for a type 2 diabetic not on insulin?") == []
    assert patient_details(None) == []


def test_the_api_allows_a_quoted_a1c_threshold() -> None:
    question = "Does Medicare cover a CGM with an A1c 7.5 or higher?"
    assert patient_details(question) == ["a lab value"]  # the dataset checks keep the rule
    assert patient_details(question, include_lab_values=False) == []
    # Excluding lab values never hides a real identifier in the same text.
    assert patient_details("MRN 1, A1c 9", include_lab_values=False) == ["a medical record number"]

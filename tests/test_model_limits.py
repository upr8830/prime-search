"""Per-role output caps (docs/11): only the evaluator asks for more than the provider default."""

from __future__ import annotations


def test_the_evaluator_gets_a_larger_output_cap_and_other_roles_keep_the_default(offline_credentials) -> None:
    from prime_search.models import EVALUATOR_MAX_OUTPUT_TOKENS, baseline_model, evaluator_model, root_model

    assert evaluator_model().max_tokens == EVALUATOR_MAX_OUTPUT_TOKENS == 32_000
    assert root_model().max_tokens is None
    assert baseline_model().max_tokens is None  # starter parity (docs/03 §9)

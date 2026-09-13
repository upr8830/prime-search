"""The docs/09 §1.7 [G] gate, run live.

`make ask Q="..."` produces a cited answer with an "Effective dates relied on" section
and a Sources list; `--mode baseline` produces the starter-style answer; both traced.

Marked `live` so `make test` stays offline (docs/11 R8). Run with:

    uv run --env-file .env pytest tests/test_ask_live.py -m live -q -s
"""

from __future__ import annotations

import pytest

from prime_search.agents.synthesizer import SECTION_HEADINGS
from prime_search.schemas import RunRequest

pytestmark = pytest.mark.live

GATE_QUESTION = (
    "Is a therapeutic CGM covered under Medicare for a type 2 diabetic not on insulin?"
)


def test_the_gate_question_produces_a_cited_answer(capsys) -> None:
    from prime_search.agents.graph import run_prime

    record = run_prime(RunRequest(question=GATE_QUESTION))
    answer = record.answer
    assert answer is not None

    with capsys.disabled():
        print("\n" + "=" * 78)
        print("PRIME trace:", record.langsmith_run_url)
        print("=" * 78)
        print(answer.body_markdown)
        print("-" * 78)
        print("effective dates:", answer.effective_dates)
        print(
            f"citations={len(answer.citations)} evidence={len(record.evidence)} "
            f"documents={len(record.documents)} claims={len(record.claims)} "
            f"confidence={answer.confidence}"
        )
        print("usage:", record.usage.model_dump())

    # The gate's three requirements.
    assert answer.citations, "the gate requires a cited answer"
    assert "Effective dates relied on" in answer.body_markdown
    assert "## Sources" in answer.body_markdown
    assert record.langsmith_run_url and "smith.langchain.com" in record.langsmith_run_url

    # Every citation resolves to evidence that was actually recorded.
    evidence_ids = {item.evidence_id for item in record.evidence}
    assert all(citation.evidence_id in evidence_ids for citation in answer.citations)

    # And the sections are the ones docs/03 §8 specifies, in order.
    positions = [
        answer.body_markdown.find(f"## {heading}")
        for heading in SECTION_HEADINGS
        if f"## {heading}" in answer.body_markdown
    ]
    assert positions == sorted(positions)


def test_the_baseline_produces_the_starter_style_answer(capsys) -> None:
    from prime_search.baseline import run_baseline

    record = run_baseline(RunRequest(question=GATE_QUESTION, mode="baseline"))
    answer = record.answer
    assert answer is not None

    with capsys.disabled():
        print("\n" + "=" * 78)
        print("baseline trace:", record.langsmith_run_url)
        print("=" * 78)
        print(answer.body_markdown)
        print("-" * 78)
        print(f"citations={len(answer.citations)} searches={record.usage.searches}")

    assert answer.body_markdown.strip()
    assert record.langsmith_run_url and "smith.langchain.com" in record.langsmith_run_url
    # The control arm's shape: no evidence, no claims, no dates section.
    assert record.evidence == []
    assert answer.effective_dates == []

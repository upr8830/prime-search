"""The docs/09 §2.2 check, run live.

    uv run --env-file .env pytest tests/test_judge_critic_live.py -m live -q -s

"On the gestational-diabetes contradiction question, the run shows a judge round or a
critic recommendation and the answer's Contradictions section is non-empty." The
question is SearchBench `adv-cgm-001`, whose key expects "Secondary sources claim broad
coverage; the LCD requires specific criteria".

Everything the check depends on is printed - verdicts, critic reports, the answer's
contradiction lines and section, usage and the trace URL - so a pass or a failure can be
read, not just counted.
"""

from __future__ import annotations

import re

import pytest

from prime_search.agents.graph import run_prime
from prime_search.schemas import RunRequest

pytestmark = pytest.mark.live

QUESTION = "Is a CGM covered by Medicare for gestational diabetes?"


def _section(body: str, heading: str) -> str:
    match = re.search(
        rf"^##+\s*{re.escape(heading)}[^\n]*$(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL
    )
    return match.group(1).strip() if match else ""


def test_judge_and_critic_on_the_gestational_diabetes_question(capsys) -> None:
    record = run_prime(RunRequest(question=QUESTION, question_id="adv-cgm-001", depth="deep"))
    answer = record.answer
    assert answer is not None, record.error
    section = _section(answer.body_markdown, "Contradictions and caveats")

    with capsys.disabled():
        print(f"\nLangSmith trace: {record.langsmith_run_url}")
        print(f"status {record.status} | rounds {record.usage.rounds} | tasks {[t.task_id for t in record.tasks]}")
        for verdict in record.verdicts:
            print(
                f"verdict r{verdict.round}: sufficient={verdict.sufficient} coverage={verdict.coverage} "
                f"new_tasks={[t.task_id for t in verdict.new_tasks]} missing={verdict.missing}"
            )
        for report in record.critic_reports:
            print(
                f"critic: completion={report.completion_probability} "
                f"recommended={[t.task_id for t in report.recommended_searches]} "
                f"contradictions={report.contradictions}"
            )
        print("Answer.contradictions:")
        for line in answer.contradictions:
            print(f"  - {line}")
        print(f"## Contradictions and caveats\n{section}")
        print(f"usage: {record.usage.model_dump()}")

    assert record.verdicts, "the judge never ran"
    judge_round = any(v.new_tasks for v in record.verdicts) or any(t.round >= 1 for t in record.tasks)
    critic_recommendation = any(r.recommended_searches for r in record.critic_reports)
    assert judge_round or critic_recommendation, "neither a judge round nor a critic recommendation"
    assert answer.contradictions, "Answer.contradictions is empty"
    assert section and not re.fullmatch(r"(?i)none(?: found)?\.?", section), section
    assert "smith.langchain.com" in (record.langsmith_run_url or "")

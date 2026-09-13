"""The critic (docs/03 §7).

The model is a `ScriptedChatModel` returning fenced JSON, the shape the root model
actually emits, and the structured-output fallback is stubbed at
`critic_module.structured`. The assertions are about the ladder (fenced, repair,
structured, skipped), about what the critic is shown, and about what the harness keeps
of its answer.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime

import pytest
from conftest import ScriptedChatModel
from langchain_core.messages import AIMessage

from prime_search import events
from prime_search.agents import critic as critic_module
from prime_search.agents.critic import SKIPPED_TAG, STRUCTURED_TAG, build_prompt, run_critic
from prime_search.schemas import (
    Branch,
    Claim,
    CriticReport,
    Document,
    Evidence,
    Location,
    QueryUnderstanding,
    SearchPlan,
    SearchTask,
    TaskResult,
    Usage,
    Verdict,
)

REPORT = {
    "weak_claims": ["c1"],
    "missing_interpretations": [],
    "source_independence_issues": [],
    "secondary_when_primary_exists": [],
    "outdated_sources": [],
    "contradictions": [],
    "recommended_searches": [],
    "completion_probability": 0.8,
    "reasoning": "fine",
}


def _fenced(payload: dict) -> AIMessage:
    return AIMessage(content=f"```json\n{json.dumps(payload)}\n```")


class FakeCaller:
    def __init__(self, value=None, *, error=None) -> None:  # noqa: ANN001
        self.value = value
        self.error = error
        self.last_mode = "native"
        self.last_message = None

    def invoke(self, prompt: str):  # noqa: ANN201
        if self.error is not None:
            raise self.error
        return self.value


class Unreachable(ScriptedChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[no-untyped-def]
        self.seen.append(list(messages))
        raise ConnectionError("endpoint down")


def _document(doc_id: str, url: str, tier: str, **fields) -> Document:
    return Document(
        doc_id=doc_id, url=url, title=fields.pop("title", doc_id), source_tier=tier,
        retrieved_at=datetime.now(UTC), fetch_method="extract", **fields,
    )


def _evidence(evidence_id: str, doc_id: str, branch: str, stance: str, text: str, **fields) -> Evidence:
    return Evidence(
        evidence_id=evidence_id, doc_id=doc_id, branch_id=branch, claim_text=text,
        evidence_text=text, location=Location(paragraph_index=1, char_start=0, char_end=len(text)),
        relevance=0.8, source_quality=fields.pop("source_quality", 1.0), confidence=0.9,
        stance=stance, **fields,
    )


@pytest.fixture
def ws(sandboxed_run):
    """b1 answered from the LCD; b2 contested between the LCD and a web guide."""
    ws = sandboxed_run
    ws.understanding = QueryUnderstanding(
        normalized_question="q", domain="cgm", question_type="contradiction", time_sensitivity="high"
    )
    ws.plan = SearchPlan(
        understanding=ws.understanding,
        branches=[
            Branch(branch_id="b1", question="What does the LCD require?", rationale="r",
                   source_hint="primary_policy", priority=1),
            Branch(branch_id="b2", question="Do other sources agree?", rationale="r",
                   source_hint="any", priority=2),
        ],
        stop_criteria="Every criterion cited to a dated primary source",
        budget=ws.budget,
    )
    ws.documents["doc_lcd"] = _document(
        "doc_lcd", "https://www.cms.gov/lcd", "primary_policy", document_id_external="L33822",
        doc_type="LCD", publisher="CMS", revision_date=date(2024, 10, 1), title="Glucose Monitors",
    )
    ws.documents["doc_web"] = _document("doc_web", "https://example.com/guide", "web")
    ws.evidence += [
        _evidence("ev_1", "doc_lcd", "b1", "supports", "The beneficiary is insulin-treated",
                  effective_date=date(2024, 10, 1)),
        _evidence("ev_2", "doc_web", "b2", "contradicts", "Every diabetic qualifies for a CGM",
                  source_quality=0.3),
        _evidence("ev_3", "doc_lcd", "b2", "supports", "Coverage requires insulin or problematic hypoglycemia"),
    ]
    ws.claims += [
        Claim(claim_id="c1", text="Insulin treatment qualifies", branch_id="b1", supported_by=["ev_1"],
              status="supported", confidence=0.9, governing_date=date(2024, 10, 1)),
        Claim(claim_id="c2", text="Coverage is conditional", branch_id="b2", supported_by=["ev_3"],
              contradicted_by=["ev_2"], status="contested", confidence=0.6),
    ]
    ws.contradictions = ["c2"]
    ws.tasks.append(
        SearchTask(
            task_id="b2-r0", branch_id="b2", round=0, instruction="Check secondary sources",
            status="done",
            result=TaskResult(queries_issued=["CGM LCD revision 2024"], documents_fetched=[],
                              evidence_ids=["ev_2", "ev_3"], summary="", unresolved=None, usage=Usage()),
        )
    )
    ws.verdicts.append(
        Verdict(round=0, sufficient=False, coverage={"b1": "resolved", "b2": "partial"},
                missing=["which source governs b2"], reasoning="r")
    )
    return ws


def _critic(ws, script, **params):  # noqa: ANN001, ANN003, ANN202
    model = script if isinstance(script, ScriptedChatModel) else ScriptedChatModel(script=script)
    arguments = {"state_round": 1, "may_search": True}
    arguments.update(params)
    return run_critic(ws, model=model, **arguments), model


# --- the ladder --------------------------------------------------------------------------


def test_fenced_json_becomes_a_critic_report(ws) -> None:
    outcome, model = _critic(ws, [_fenced(REPORT)])
    assert (outcome.mode, outcome.fallback_tag) == ("fenced_json", None)
    assert outcome.report.weak_claims == ["c1"]
    assert len(model.seen) == 1


def test_one_repair_turn_then_success(ws) -> None:
    """docs/01 §9: "one repair attempt with the same model"."""
    outcome, model = _critic(ws, [AIMessage(content="Looks fine to me."), _fenced(REPORT)])
    assert outcome.mode == "fenced_json_repair"
    repair_turn = model.seen[1]
    assert len(repair_turn) == 3
    assert "last attempt" in repair_turn[-1].content


def test_a_second_unusable_reply_falls_back_to_structured_output_on_the_judge(ws, monkeypatch) -> None:
    """docs/03 §7: "fallback to structured output on the judge model"."""
    monkeypatch.setattr(critic_module, "structured", lambda *a, **k: FakeCaller(CriticReport(**REPORT)))
    outcome, _ = _critic(ws, [AIMessage(content="no"), AIMessage(content="still no")])
    assert (outcome.mode, outcome.fallback_tag) == ("structured", STRUCTURED_TAG)
    assert outcome.report is not None


def test_an_endpoint_error_skips_the_repair_turn(ws, monkeypatch) -> None:
    monkeypatch.setattr(critic_module, "structured", lambda *a, **k: FakeCaller(CriticReport(**REPORT)))
    outcome, model = _critic(ws, Unreachable())
    assert outcome.mode == "structured"
    assert len(model.seen) == 1  # no repair turn sent to an endpoint that is down


def test_when_everything_fails_the_run_goes_on_without_a_report(ws, monkeypatch) -> None:
    monkeypatch.setattr(
        critic_module, "structured", lambda *a, **k: FakeCaller(error=RuntimeError("both modes"))
    )
    outcome, _ = _critic(ws, [AIMessage(content="no"), AIMessage(content="no")])
    assert outcome.report is None
    assert outcome.fallback_tag == SKIPPED_TAG
    logged = [r for r in events.replay(ws.run_id) if r["type"] == "error"]
    assert logged and "critic" in json.dumps(logged[-1])


# --- what the harness keeps ----------------------------------------------------------------


def test_recommended_searches_are_capped_and_named_as_critic_tasks(ws) -> None:
    searches = [
        {"branch_id": "b2", "instruction": f"Fetch source {i}", "queries_hint": [f"query {i}"]}
        for i in range(4)
    ]
    searches[1]["branch_id"] = "b77"  # not a branch the plan has
    outcome, _ = _critic(ws, [_fenced({**REPORT, "recommended_searches": searches})], state_round=2)

    tasks = outcome.report.recommended_searches
    assert [(t.task_id, t.branch_id, t.round) for t in tasks] == [
        ("b2-r2-critic1", "b2", 2),
        ("critic-r2-critic2", "critic", 2),
        ("b2-r2-critic3", "b2", 2),
    ]


def test_a_recommendation_repeating_a_search_already_run_is_dropped(ws) -> None:
    searches = [
        {"branch_id": "b2", "instruction": "Anything", "queries_hint": ["cgm lcd revision 2024"]},
        {"branch_id": "b2", "instruction": "Fetch the billing article", "queries_hint": ["A52464"]},
    ]
    outcome, _ = _critic(ws, [_fenced({**REPORT, "recommended_searches": searches})])
    assert [t.instruction for t in outcome.report.recommended_searches] == ["Fetch the billing article"]


def test_unknown_ids_are_dropped_but_descriptions_are_kept(ws) -> None:
    description = "A web guide says every diabetic qualifies; L33822 requires insulin; the LCD governs"
    payload = {
        **REPORT,
        "weak_claims": ["c1", "c99"],
        "secondary_when_primary_exists": ["c2", "c404"],
        "outdated_sources": ["L33822", "doc_nope"],
        "contradictions": ["c2", "c42", "yes", description],
        "completion_probability": 1.7,
    }
    outcome, _ = _critic(ws, [_fenced(payload)])

    report = outcome.report
    assert report.weak_claims == ["c1"]
    assert report.secondary_when_primary_exists == ["c2"]
    assert report.outdated_sources == ["doc_lcd"]
    assert report.contradictions == ["c2", description]
    assert report.completion_probability == 1.0


def test_null_lists_and_bare_string_searches_are_accepted(ws) -> None:
    payload = {**REPORT, "contradictions": None, "recommended_searches": ["Fetch the billing article"]}
    outcome, _ = _critic(ws, [_fenced(payload)])

    assert outcome.mode == "fenced_json"  # no repair turn spent on a near-miss
    assert outcome.report.contradictions == []
    assert outcome.report.recommended_searches[0].branch_id == "critic"


# --- what the critic is shown -------------------------------------------------------------


def test_the_prompt_shows_evidence_tiers_dates_documents_and_searches(ws) -> None:
    """docs/03 §7's input: claims with their evidence (text, tier, dates), the
    trajectory, the stop criteria."""
    prompt = build_prompt(ws, may_search=True)

    assert '+ ev_1 · primary_policy · L33822 LCD · dated 2024-10-01: "The beneficiary is insulin-treated"' in prompt
    assert "- ev_2 · web · example.com · undated" in prompt
    assert "doc_lcd · primary_policy · L33822 LCD · revised 2024-10-01" in prompt
    assert '"CGM LCD revision 2024"' in prompt
    assert "round 0: insufficient; b1 resolved, b2 partial" in prompt
    assert "Every criterion cited to a dated primary source" in prompt
    assert not re.search(r"\{[a-z_]+\}", prompt)


def test_the_final_review_says_no_more_searches_will_run(ws) -> None:
    assert "final review" in build_prompt(ws, may_search=False)
    assert "final review" not in build_prompt(ws, may_search=True)

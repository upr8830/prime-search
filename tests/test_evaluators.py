"""SearchBench evaluators (docs/05 §2).

Runs are built from schemas and the judge is stubbed at `evaluators.structured`, so these
pin what each metric reads, its formula, when it does not apply, and what its comment
says - the comment is GEPA's feedback (docs/05 §5). The sources index is replaced by a
small fixture except where the real dataset is the point.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from langsmith.evaluation import EvaluationResult
from pydantic import ValidationError

from eval import evaluators
from eval.evaluators import (
    EVALUATORS,
    METRIC_KEYS,
    AnswerCorrectnessJudgment,
    CitationJudgment,
    ClaimJudgment,
    ContradictionItem,
    ContradictionJudgment,
    ForbiddenJudgment,
    IndexEntry,
    OrderJudgment,
    Score,
    ScopeJudgment,
    SentenceJudgment,
    composite,
    feedback_text,
    resolve_descriptor,
    score_record,
)
from eval.searchbench.schema import BenchRecord, load_records
from prime_search.schemas import (
    Answer,
    Citation,
    Document,
    Evidence,
    Location,
    RunRecord,
    RunRequest,
    Usage,
)

REAL_INDEX = evaluators.load_sources_index
LCD_URL = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?lcdid=33822"
INDEX = {
    "L33822": IndexEntry("L33822", LCD_URL, "L33822", date(2024, 10, 1), None, False),
    "CMS 2024 Part D guidance": IndexEntry(
        "CMS 2024 Part D guidance", "https://www.cms.gov/newsroom/fact-sheets/part-d-premiums", None, None, None, True
    ),
    "FDA Wegovy label": IndexEntry(
        "FDA Wegovy label", "https://www.accessdata.fda.gov/label/wegovy.pdf", None, date(2023, 7, 1), None, True
    ),
}


@pytest.fixture(autouse=True)
def index(monkeypatch):
    monkeypatch.setattr(evaluators, "load_sources_index", lambda *a, **k: INDEX)


class FakeCaller:
    def __init__(self, value, error) -> None:  # noqa: ANN001
        self.value = value
        self.error = error
        self.last_mode = "native"
        self.messages: list = []
        self.prompts: list[str] = []

    def invoke(self, prompt: str):  # noqa: ANN201
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.value


@pytest.fixture
def judge(monkeypatch):
    """`judge.answers[SchemaName] = value` (or a list, answered in turn, the last repeating);
    `judge.calls` records (schema, caller)."""
    state = SimpleNamespace(answers={}, calls=[], error=None)

    def fake(role, schema, **kwargs):  # noqa: ANN001, ANN003, ANN202
        value = state.answers.get(schema.__name__)
        if isinstance(value, list):
            value = value.pop(0) if len(value) > 1 else value[0]
        caller = FakeCaller(value, state.error)
        state.calls.append((schema.__name__, caller))
        return caller

    monkeypatch.setattr(evaluators, "structured", fake)
    return state


# --- builders --------------------------------------------------------------------------


def _doc(doc_id="doc_lcd", url=LCD_URL, *, tier="primary_policy", ext="L33822", doc_type="LCD", rev=date(2024, 10, 1)):  # noqa: ANN001, ANN202
    return Document(
        doc_id=doc_id, url=url, title=doc_id, source_tier=tier, document_id_external=ext,
        doc_type=doc_type, revision_date=rev, retrieved_at=datetime.now(UTC), fetch_method="extract",
    )


def _ev(evidence_id: str, doc_id: str, text: str) -> Evidence:
    return Evidence(
        evidence_id=evidence_id, doc_id=doc_id, branch_id="b1", claim_text=text[:100], evidence_text=text,
        location=Location(paragraph_index=0, char_start=0, char_end=len(text)),
        relevance=0.8, source_quality=1.0, confidence=0.9, stance="supports",
    )


def _cite(n: int, evidence_id: str = "", doc_id: str = "", url: str = LCD_URL) -> Citation:
    return Citation(n=n, evidence_id=evidence_id, doc_id=doc_id, url=url, label=url)


def _record(
    body: str = "## Answer\n\nCovered [1].",
    *,
    citations=(), evidence=(), documents=(), mode="prime", usage=None,  # noqa: ANN001
    effective_dates=(), scope_warning=None, contradictions=(), with_answer=True,  # noqa: ANN001
) -> RunRecord:
    answer = (
        Answer(
            summary="s", body_markdown=body, claims=[], citations=list(citations),
            effective_dates=list(effective_dates), contradictions=list(contradictions), unknowns=[],
            confidence=0.5, scope_warning=scope_warning,
        )
        if with_answer
        else None
    )
    return RunRecord(
        run_id="run-1", request=RunRequest(question="q?", mode=mode), started_at=datetime.now(UTC),
        finished_at=None, langsmith_run_url=None, plan=None, tasks=[],
        documents={d.doc_id: d for d in documents}, evidence=list(evidence), claims=[], verdicts=[],
        critic_reports=[], answer=answer, usage=usage or Usage(),
        status="completed" if with_answer else "failed", error=None if with_answer else "boom",
    )


def _bench(question_type: str = "eligibility", **key) -> BenchRecord:
    answer_key = {"summary": "Covered when insulin-treated.", "as_of": "2026-09-13", "validated_by": "t"}
    answer_key.update(key)
    return BenchRecord.model_validate(
        {"id": "x-001", "domain": "cgm", "tier": 2, "question_type": question_type,
         "question": "Is it covered?", "split": "dev", "answer_key": answer_key}
    )


def _item(id="e1", ext="L33822", doc_type="LCD", phrases=("insulin",), must=True) -> dict:  # noqa: A002, ANN001
    return {"id": id, "document_id_external": ext, "doc_type": doc_type, "key_phrases": list(phrases), "must": must}


def _claims(*specs: tuple[str, bool]) -> list[dict]:
    return [{"id": claim_id, "text": f"claim {claim_id}", "must": must} for claim_id, must in specs]


# --- document resolution and evidence_recall ---------------------------------------------


def test_every_governing_document_in_the_dataset_resolves(monkeypatch) -> None:
    monkeypatch.setattr(evaluators, "load_sources_index", REAL_INDEX)
    unresolved = [
        (record.id, descriptor)
        for record in load_records()
        for descriptor in record.answer_key.governing_documents
        if resolve_descriptor(descriptor, record.answer_key).how == "unresolved"
    ]
    assert unresolved == []


def test_evidence_recall_matches_by_external_id_and_key_phrase() -> None:
    record = _record(documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", "The beneficiary is insulin-treated")])
    score = evaluators.evidence_recall(record, _bench(required_evidence=[_item()]))
    assert score.score == 1.0
    assert score.metadata["matched"] == {"e1": "id"}


def test_evidence_recall_derives_the_id_from_an_mcd_url() -> None:
    """Live runs fetched L33822 under `LCDId=33822&ver=70` with no document id at all."""
    url = "https://www.cms.gov/medicare-coverage-database/view/lcd.aspx?LCDId=33822&ver=70"
    record = _record(documents=[_doc(url=url, ext=None)], evidence=[_ev("ev1", "doc_lcd", "insulin-treated")])
    assert evaluators.evidence_recall(record, _bench(required_evidence=[_item()])).score == 1.0


def test_evidence_recall_requires_a_key_phrase_in_the_passage() -> None:
    record = _record(documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", "Documentation must be kept.")])
    score = evaluators.evidence_recall(record, _bench(required_evidence=[_item()]))
    assert score.score == 0.0
    assert "document found, no passage containing 'insulin'" in score.comment


def test_key_phrases_fold_case_spacing_and_unicode_hyphens() -> None:
    passage = "REVISION  Effective Date: revised 2024‑10‑01"
    record = _record(documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", passage)])
    items = [_item("e1", phrases=("Revision Effective Date",)), _item("e2", phrases=("2024-10-01",))]
    assert evaluators.evidence_recall(record, _bench(required_evidence=items)).score == 1.0


def test_must_items_weigh_twice() -> None:
    record = _record(documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", "insulin-treated")])
    items = [_item("e1"), _item("e2", ext="A52464", doc_type="Article", must=False)]
    assert evaluators.evidence_recall(record, _bench(required_evidence=items)).score == pytest.approx(2 / 3, abs=1e-4)


def test_host_and_doc_type_fallback_only_when_the_key_names_no_id() -> None:
    fact_sheet = _doc("doc_fs", "https://www.cms.gov/newsroom/fact-sheets/another-page", ext=None, doc_type="Fact sheet", rev=None)
    record = _record(documents=[fact_sheet], evidence=[_ev("ev1", "doc_fs", "a medically accepted indication")])
    guidance = _item("e1", ext="CMS 2024 Part D guidance", doc_type="Guidance", phrases=("medically accepted",))
    score = evaluators.evidence_recall(record, _bench(required_evidence=[guidance]))
    assert score.score == 1.0 and score.metadata["matched"] == {"e1": "host+type"}
    assert "needs_review" in score.comment

    other_cms_page = _doc("doc_x", "https://www.cms.gov/some/other/page", ext=None, doc_type="LCD")
    record = _record(documents=[other_cms_page], evidence=[_ev("ev1", "doc_x", "insulin")])
    assert evaluators.evidence_recall(record, _bench(required_evidence=[_item()])).score == 0.0


def test_a_canonical_url_descriptor_matches_by_normalized_url() -> None:
    descriptor = "https://www.cms.gov/priorities/innovation/innovation-models/balance?utm_source=x"
    page = _doc("doc_b", "https://cms.gov/priorities/innovation/innovation-models/balance/", ext=None, doc_type=None, rev=None)
    record = _record(documents=[page], evidence=[_ev("ev1", "doc_b", "The BALANCE Model will launch")])
    item = _item("e1", ext=descriptor, doc_type="Press release", phrases=("BALANCE Model",))
    score = evaluators.evidence_recall(record, _bench(required_evidence=[item]))
    assert score.metadata["matched"] == {"e1": "url"}


def test_evidence_recall_is_not_applicable_without_required_evidence() -> None:
    score = evaluators.evidence_recall(_record(), _bench())
    assert score.score is None and score.comment.startswith("not applicable")


def test_the_baseline_scores_zero_on_passage_metrics_without_a_judge_call(judge) -> None:
    """User decision (docs/11): no passage stands behind a baseline citation."""
    record = _record("Covered, see https://www.cms.gov/x.", mode="baseline", citations=[_cite(1, url="https://www.cms.gov/x")])
    bench = _bench(required_evidence=[_item()])
    assert evaluators.evidence_recall(record, bench).score == 0.0
    correctness = evaluators.citation_correctness(record, bench)
    assert correctness.score == 0.0 and "by construction" in correctness.comment
    assert judge.calls == []


# --- citation_completeness, primary_source_ratio, cost ---------------------------------------

BODY = """## Answer

Yes [1].

## Criteria / Details

- Must have diabetes [1].
- Must use insulin.

## Codes and documentation

Bill E2103 [2]. Keep records [2].

## Unknowns / not verified

None.
"""


def test_citation_completeness_counts_criteria_and_codes_sentences() -> None:
    score = evaluators.citation_completeness(_record(BODY), _bench())
    assert score.score == 0.75
    assert "Must use insulin." in score.comment


def test_a_citation_after_the_full_stop_belongs_to_its_sentence() -> None:
    body = "## Criteria / Details\n\nCoverage requires insulin. [2]\n"
    assert evaluators.citation_completeness(_record(body), _bench()).score == 1.0


def test_alternative_citation_forms_count() -> None:
    body = "## Criteria / Details\n\n- Coverage requires insulin【3】.\n- Visits every six months【1†L1-L3】.\n"
    assert evaluators.citation_completeness(_record(body), _bench()).score == 1.0


def test_a_baseline_layout_uses_the_whole_answer_and_counts_urls() -> None:
    body = "Medicare covers CGMs when criteria are met (https://www.cms.gov/x). Some plans vary.\n\nSources:\nhttps://a.com"
    assert evaluators.citation_completeness(_record(body, mode="baseline"), _bench()).score == 0.5


def test_primary_source_ratio_uses_the_document_tier_then_the_url_tier() -> None:
    citations = [_cite(1, "ev1", "doc_lcd"), _cite(2, url="https://www.medicalnewstoday.com/articles/cgm")]
    score = evaluators.primary_source_ratio(_record(citations=citations, documents=[_doc()]), _bench())
    assert score.score == 0.5
    assert "medicalnewstoday.com" in score.comment


def test_primary_source_ratio_is_not_applicable_without_citations() -> None:
    assert evaluators.primary_source_ratio(_record(), _bench()).score is None


def test_cost_metrics_read_usage() -> None:
    usage = Usage(searches=3, fetches=2, input_tokens=0, output_tokens=20, wall_seconds=12.5)
    scores = {score.key: score for score in evaluators.cost_metrics(_record(usage=usage))}
    assert (scores["search_cost"].score, scores["latency_s"].score, scores["tokens"].score) == (5, 12.5, 20)
    assert "input tokens not reported" in scores["tokens"].comment


# --- currency ----------------------------------------------------------------------------------


def test_currency_needs_the_governing_document_cited_and_its_date_stated() -> None:
    bench = _bench(governing_documents=["L33822"])
    citations = [_cite(1, "ev1", "doc_lcd")]
    undated = _record(citations=citations, documents=[_doc()])
    assert evaluators.currency(undated, bench).score == 0.5
    dated = _record(citations=citations, documents=[_doc()], effective_dates=["L33822: revision effective 2024-10-01"])
    assert evaluators.currency(dated, bench).score == 1.0


def test_currency_reads_the_governing_date_in_the_answer_text() -> None:
    """User decision: the baseline never fills `effective_dates`."""
    bench = _bench(governing_documents=["L33822"])
    for body in ("Revised October 1, 2024 [1].", "Revised 2024‑10‑01 [1]."):
        record = _record(body, citations=[_cite(1, "ev1", "doc_lcd")], documents=[_doc()])
        assert evaluators.currency(record, bench).score == 1.0, body


def test_currency_takes_no_date_from_a_search_guessed_index_entry() -> None:
    bench = _bench(governing_documents=["FDA Wegovy label"])
    record = _record(citations=[_cite(1, url="https://www.accessdata.fda.gov/label/wegovy.pdf")])
    score = evaluators.currency(record, bench)
    assert score.score == 1.0
    assert "search-guessed index entry" in score.comment


def test_change_detection_currency_averages_in_the_order_verdict(judge) -> None:
    judge.answers["OrderJudgment"] = OrderJudgment(verdict="undated")
    bench = _bench("change_detection", governing_documents=["L33822"])
    record = _record(citations=[_cite(1, "ev1", "doc_lcd")], documents=[_doc()], effective_dates=["L33822: 2024-10-01"])
    assert evaluators.currency(record, bench).score == pytest.approx(2 / 3, abs=1e-4)


# --- judge metrics -----------------------------------------------------------------------------


def _correctness(claims, forbidden=(), summary="consistent") -> AnswerCorrectnessJudgment:  # noqa: ANN001
    return AnswerCorrectnessJudgment(claims=list(claims), forbidden=list(forbidden), summary_consistency=summary)


def test_answer_correctness_formula(judge) -> None:
    judge.answers["AnswerCorrectnessJudgment"] = _correctness(
        [ClaimJudgment(id="c1", status="present"), ClaimJudgment(id="c2", status="missing")], summary="partial"
    )
    scores = evaluators.answer_correctness(_record(), _bench(required_claims=_claims(("c1", True), ("c2", False))))
    assert scores[0].score == pytest.approx(0.8 * 2 / 3 + 0.2 * 0.5, abs=1e-4)
    assert "missing: c2" in scores[0].comment


def test_an_asserted_forbidden_claim_caps_answer_correctness(judge) -> None:
    judge.answers["AnswerCorrectnessJudgment"] = _correctness(
        [ClaimJudgment(id="c1", status="present")], [ForbiddenJudgment(id="f1", asserted=True, quote="all covered")]
    )
    bench = _bench(required_claims=_claims(("c1", True)), forbidden_claims=[{"id": "f1", "text": "x", "reason": "y"}])
    assert evaluators.answer_correctness(_record(), bench)[0].score == 0.25


def test_a_claim_the_judge_omitted_counts_as_missing(judge) -> None:
    judge.answers["AnswerCorrectnessJudgment"] = _correctness([ClaimJudgment(id="c1", status="present")])
    score = evaluators.answer_correctness(_record(), _bench(required_claims=_claims(("c1", True), ("c2", True))))[0]
    assert score.score == pytest.approx(0.8 * 0.5 + 0.2, abs=1e-4)
    assert "c2 (must) (judge omitted)" in score.comment


def test_a_verdict_with_no_claims_is_retried_then_a_judge_failure(judge) -> None:
    # Dev bench, glp1-path-002 / adv-glp1-002: a native reply without `claims` graded both answers 0.2.
    with pytest.raises(ValidationError):
        AnswerCorrectnessJudgment(summary_consistency="consistent")
    judge.answers["AnswerCorrectnessJudgment"] = _correctness([])
    score = evaluators.answer_correctness(_record(), _bench(required_claims=_claims(("c1", True))))[0]
    assert score.score is None and score.metadata["error"] is True
    assert "no verdict for any required claim" in score.comment
    assert len(judge.calls) == 2


def test_a_retry_that_covers_the_claims_is_graded(judge) -> None:
    judge.answers["AnswerCorrectnessJudgment"] = [_correctness([]), _correctness([ClaimJudgment(id="c1", status="present")])]
    score = evaluators.answer_correctness(_record(), _bench(required_claims=_claims(("c1", True))))[0]
    assert score.score == 1.0
    assert "judge_error" not in score.metadata and score.metadata["judge_retries"] == 1


def test_a_citation_verdict_with_no_items_is_a_judge_failure(judge) -> None:
    judge.answers["CitationJudgment"] = CitationJudgment(items=[])
    record = _record("## Answer\n\nCovered [1].", citations=[_cite(1, "ev1", "doc_lcd")], documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", "covered")])
    score = evaluators.citation_correctness(record, _bench())
    assert score.score is None and "no verdict for any cited sentence" in score.comment


def test_a_score_outside_langsmiths_range_is_sent_as_a_value() -> None:
    big = evaluators.Score("tokens", 586002, "586002 tokens").to_langsmith()
    assert (big["score"], big["value"]) == (None, "586,002")
    EvaluationResult(**big)
    assert evaluators.Score("tokens", 9002, "x").to_langsmith()["score"] == 9002


def test_a_verdict_that_skips_the_forbidden_claims_is_a_judge_failure(judge) -> None:
    with pytest.raises(ValidationError):
        AnswerCorrectnessJudgment(claims=[], summary_consistency="consistent")
    judge.answers["AnswerCorrectnessJudgment"] = _correctness([ClaimJudgment(id="c1", status="present")])
    bench = _bench(required_claims=_claims(("c1", True)), forbidden_claims=[{"id": "f1", "text": "x", "reason": "y"}])
    score = evaluators.answer_correctness(_record(), bench)[0]
    assert score.score is None and "no verdict for any forbidden claim" in score.comment


def test_a_judge_failure_leaves_the_composite_empty() -> None:
    failed = evaluators.Score("citation_correctness", None, "judge failed: x", {"error": True})
    scores = {"answer_correctness": evaluators.Score("answer_correctness", 0.9, ""), "citation_correctness": failed}
    assert evaluators.composite(scores) is None
    assert evaluators.composite({"answer_correctness": 0.9, "citation_correctness": None}) == pytest.approx(0.9)


def test_citation_completeness_reads_a_headed_baseline_whole_and_counts_footnotes() -> None:
    # Dev bench: cgm-elig-004's baseline used `###` headings (was not applicable) and
    # adv-glp1-002 cited with `[^36130e-00^]` markers (was 0/11).
    body = "Covered for pump users.[^ab12-00^]\n\n### Key Coverage Criteria\n\n1. **Use insulin**[^cd34-01^]\n2. Have a visit."
    score = evaluators.citation_completeness(_record(body), _bench())
    assert score.score == pytest.approx(2 / 3, abs=1e-4)
    assert "whole answer" in score.comment


def test_citation_correctness_samples_eight_evenly_spaced_sentences(judge) -> None:
    assert evaluators._sample(list(range(16)), 8) == [0, 2, 4, 6, 9, 11, 13, 15]
    judge.answers["CitationJudgment"] = CitationJudgment(items=[SentenceJudgment(index=i, supported=True) for i in range(8)])
    body = "## Criteria / Details\n\n" + "\n".join(f"- Fact number {i} [1]." for i in range(16))
    record = _record(body, citations=[_cite(1, "ev1", "doc_lcd")], documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", "facts")])
    score = evaluators.citation_correctness(record, _bench())
    assert score.score == 1.0
    assert judge.calls[0][1].prompts[0].count("Sentence: ") == 8


def test_a_dailymed_label_matches_an_fda_label_target() -> None:
    # Prime dev bench, glp1-path-002: the DailyMed Wegovy label was "not cited" against an fda.gov target.
    target = evaluators.Target(descriptor="FDA Wegovy label", hosts={"fda.gov"})
    dailymed = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=f5e548d0"
    assert evaluators.matches_target(dailymed, "Label", None, target) == "host+type"
    assert evaluators.matches_target("https://pmc.ncbi.nlm.nih.gov/articles/PMC1/", None, None, target) is None
    # The alias applies on both sides: a key source on DailyMed matches an FDA-hosted label.
    keyed = evaluators.Target(descriptor="Wegovy label", hosts={evaluators._target_site(dailymed)})
    assert evaluators.matches_target("https://www.accessdata.fda.gov/label/wegovy.pdf", "Label", None, keyed) == "host+type"


def test_citation_correctness_skips_effective_dates_and_shows_each_passages_document(judge) -> None:
    # Prime dev bench: "[1] LCD L33822 - 2024-10-01" lines were sampled, and a sentence naming
    # L33822 failed because the paragraph never repeats its own document id.
    judge.answers["CitationJudgment"] = CitationJudgment(items=[SentenceJudgment(index=0, supported=True)])
    body = (
        "## Criteria / Details\n\n- HCPCS A4271 descriptor revised (LCD L33822, 10/01/2024) [1].\n\n"
        "## Effective dates relied on\n\n- [1] LCD L33822 - 2024-10-01\n\n## Unknowns / not verified\n\n- None.\n"
    )
    record = _record(body, citations=[_cite(1, "ev1", "doc_lcd")], documents=[_doc()], evidence=[_ev("ev1", "doc_lcd", "descriptor revised")])
    score = evaluators.citation_correctness(record, _bench())
    prompt = judge.calls[0][1].prompts[0]
    assert score.score == 1.0 and prompt.count("Sentence: ") == 1
    assert "Document: LCD, L33822" in prompt and "revision effective 2024-10-01" in prompt


def test_a_citation_with_no_passage_is_unsupported_without_a_judge_call(judge) -> None:
    score = evaluators.citation_correctness(_record("## Answer\n\nCovered [9]."), _bench())
    assert score.score == 0.0
    assert "maps to no passage" in score.comment
    assert judge.calls == []


def test_contradiction_handling_applies_only_with_expected_contradictions(judge) -> None:
    assert evaluators.contradiction_handling(_record(), _bench()).score is None
    judge.answers["ContradictionJudgment"] = ContradictionJudgment(
        items=[ContradictionItem(index=1, surfaced=True, governing_stated=False)]
    )
    score = evaluators.contradiction_handling(_record(), _bench(expected_contradictions=["Label vs coverage"]))
    assert score.score == 0.5
    assert "governing not stated" in score.comment


def test_scope_handling_triggers_on_the_expected_warning(judge) -> None:
    assert evaluators.scope_handling(_record(), _bench()).score is None
    judge.answers["ScopeJudgment"] = ScopeJudgment(scope_flagged_in_text=True, fabricated_criteria=["a physician letter qualifies"])
    score = evaluators.scope_handling(_record(), _bench("out_of_scope", expected_scope_warning="Out of scope."))
    assert score.score == 0.5
    assert "stated in text" in score.comment and "physician letter" in score.comment


def test_a_judge_failure_is_none_with_a_comment_and_does_not_raise(judge) -> None:
    judge.error = RuntimeError("evaluator: structured output failed in both modes")
    score = evaluators.answer_correctness(_record(), _bench(required_claims=_claims(("c1", True))))[0]
    assert score.score is None and score.metadata["error"] is True
    assert score.comment.startswith("judge failed")


def test_a_failed_run_scores_zero_not_none(judge) -> None:
    record = _record(with_answer=False)
    bench = _bench(required_evidence=[_item()], required_claims=_claims(("c1", True)))
    assert evaluators.evidence_recall(record, bench).score == 0.0
    assert evaluators.answer_correctness(record, bench)[0].score == 0.0
    assert evaluators.contradiction_handling(record, bench).score is None  # still not applicable
    assert judge.calls == []


# --- assembly and LangSmith ---------------------------------------------------------------------


def _full_judge(judge) -> None:  # noqa: ANN001
    judge.answers.update(
        {
            "AnswerCorrectnessJudgment": _correctness([ClaimJudgment(id="c1", status="present")]),
            "CitationJudgment": CitationJudgment(items=[SentenceJudgment(index=0, supported=True)]),
            "OrderJudgment": OrderJudgment(verdict="ordered_with_dates"),
            "ContradictionJudgment": ContradictionJudgment(items=[ContradictionItem(index=1, surfaced=True, governing_stated=True)]),
            "ScopeJudgment": ScopeJudgment(scope_flagged_in_text=True),
        }
    )


def _scored_pair():  # noqa: ANN202
    record = _record(
        "## Answer\n\nCovered [1].\n\n## Criteria / Details\n\n- Insulin-treated beneficiaries qualify [1].",
        citations=[_cite(1, "ev1", "doc_lcd")], documents=[_doc()],
        evidence=[_ev("ev1", "doc_lcd", "insulin-treated")], usage=Usage(searches=3, fetches=2),
    )
    bench = _bench(
        required_claims=_claims(("c1", True)), required_evidence=[_item()], governing_documents=["L33822"],
        expected_contradictions=["x"], expected_scope_warning="Out of scope.",
    )
    return record, bench


def test_score_record_returns_every_metric_key(judge) -> None:
    _full_judge(judge)
    record, bench = _scored_pair()
    scores = score_record(record, bench)
    assert list(scores) == list(METRIC_KEYS)
    assert all(score.score is not None for score in scores.values())
    assert scores["search_efficiency"].score == pytest.approx(scores["answer_correctness"].score / 5 * 10)


def test_evaluator_outputs_validate_as_langsmith_results(judge) -> None:
    _full_judge(judge)
    record, bench = _scored_pair()
    run = SimpleNamespace(outputs={"record": record.model_dump(mode="json")})
    example = SimpleNamespace(
        inputs={"question": bench.question, "question_id": bench.id},
        outputs=bench.answer_key.model_dump(mode="json"),
        metadata={"id": bench.id, "domain": "cgm", "tier": 2, "question_type": "eligibility", "dataset_split": ["dev"]},
    )
    keys = []
    for evaluator in EVALUATORS:
        output = evaluator(run, example)
        for result in output.get("results", [output]):
            keys.append(EvaluationResult(**result).key)
    assert sorted(keys) == sorted(METRIC_KEYS)


def test_a_run_with_no_record_still_scores_every_key(judge) -> None:
    run = SimpleNamespace(outputs={"run_id": "r", "error": "boom"})
    _, bench = _scored_pair()
    example = SimpleNamespace(
        inputs={"question": bench.question, "question_id": bench.id},
        outputs=bench.answer_key.model_dump(mode="json"),
        metadata={"id": bench.id, "domain": "cgm", "tier": 2, "question_type": "eligibility", "dataset_split": ["dev"]},
    )
    output = EVALUATORS[0](run, example)
    assert output["key"] == "evidence_recall" and output["score"] == 0.0


def test_composite_matches_the_05_formula() -> None:
    scores = {
        "answer_correctness": 0.8, "evidence_recall": 0.5, "citation_correctness": 0.6, "currency": 1.0,
        "contradiction_handling": 0.5, "scope_handling": None, "search_cost": 20,
    }
    assert composite(scores) == pytest.approx(0.32 + 0.10 + 0.12 + 0.10 + 0.05 - 0.01)


def test_composite_substitutes_answer_correctness_for_not_applicable_parts() -> None:
    assert composite({"answer_correctness": 0.6, "search_cost": 0}) == pytest.approx(0.6)


def test_composite_clamps_and_needs_answer_correctness() -> None:
    assert composite({"answer_correctness": 0.0, "search_cost": 100}) == 0.0
    assert composite({"answer_correctness": None}) is None


def test_feedback_text_follows_the_metric_order() -> None:
    text = feedback_text({"tokens": Score("tokens", 12, "t"), "answer_correctness": Score("answer_correctness", None, "judge failed")})
    assert text.splitlines() == ["answer_correctness=n/a: judge failed", "tokens=12: t"]

"""Synthesis (docs/03 §8).

Two properties matter more than the prose: the section order the gate and the docs/05
§2 completeness evaluator both look for, and the post-hoc citation check - a model that
cites `[9]` when nine sources do not exist is the exact failure this system exists to
prevent, and it must be caught after the fact rather than trusted away.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from langchain_core.messages import AIMessage

from prime_search.agents.synthesizer import (
    SECTION_HEADINGS,
    confidence_for,
    contradiction_lines,
    synthesize,
)
from prime_search.schemas import Claim, CriticReport, Document, Evidence, Location, QueryUnderstanding
from prime_search.schemas import Branch, SearchPlan

from conftest import ScriptedChatModel

BODY = """## Answer

A therapeutic CGM is covered when the beneficiary meets the LCD criteria [1].

## Criteria / Details

- The beneficiary must have diabetes [1].
- Documentation must be in the medical record [2].

## Codes and documentation

Codes are listed in the companion article [2].

## Effective dates relied on

- LCD L33822: revision effective 2024-10-01

## Contradictions and caveats

None found.

## Unknowns / not verified

- Whether a later revision exists.

## Sources

[1] LCD L33822
[2] Article A52464
"""


def _document(doc_id: str = "doc_lcd", **kwargs) -> Document:
    return Document(
        doc_id=doc_id,
        url=kwargs.pop("url", f"https://www.cms.gov/{doc_id}"),
        title=kwargs.pop("title", "Glucose Monitors"),
        source_tier=kwargs.pop("tier", "primary_policy"),
        publisher="Noridian (DME MAC)",
        doc_type="LCD",
        document_id_external=kwargs.pop("external", "L33822"),
        revision_date=kwargs.pop("revision_date", date(2024, 10, 1)),
        retrieved_at=datetime.now(UTC),
        text_path="",
        paragraph_count=3,
        fetch_method="extract",
        **kwargs,
    )


def _evidence(evidence_id: str, *, doc_id: str = "doc_lcd", branch: str = "b1") -> Evidence:
    text = "The beneficiary has diabetes mellitus."
    return Evidence(
        evidence_id=evidence_id,
        doc_id=doc_id,
        branch_id=branch,
        claim_text="A beneficiary must have diabetes",
        evidence_text=text,
        location=Location(section="Coverage Indications", paragraph_index=0, char_start=0, char_end=len(text)),
        effective_date=None,
        relevance=0.8,
        source_quality=1.0,
        confidence=0.9,
        stance="supports",
    )


@pytest.fixture
def populated(sandboxed_run):
    ws = sandboxed_run
    ws.understanding = QueryUnderstanding(
        normalized_question="Is a therapeutic CGM covered?",
        domain="cgm",
        question_type="eligibility",
        time_sensitivity="high",
    )
    ws.documents["doc_lcd"] = _document()
    ws.documents["doc_art"] = _document(
        "doc_art", external="A52464", url="https://www.cms.gov/a52464",
        revision_date=date(2025, 1, 15),
    )
    ws.evidence.extend([_evidence("ev1"), _evidence("ev2", doc_id="doc_art")])
    ws.claims = [
        Claim(
            claim_id="c1", text="A beneficiary must have diabetes", branch_id="b1",
            supported_by=["ev1", "ev2"], status="supported", confidence=0.9,
            governing_date=date(2024, 10, 1),
        )
    ]
    ws.plan = SearchPlan(
        understanding=ws.understanding,
        branches=[Branch(branch_id="b1", question="criteria?", rationale="r",
                         source_hint="primary_policy", priority=1)],
        stop_criteria="cited",
        budget=ws.budget,
    )
    return ws


def test_the_answer_carries_every_section_heading_in_order(populated) -> None:
    """docs/03 §8's order, which the gate and the completeness evaluator both read."""
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)

    positions = [answer.body_markdown.find(f"## {heading}") for heading in SECTION_HEADINGS]
    assert all(position >= 0 for position in positions), dict(zip(SECTION_HEADINGS, positions))
    assert positions == sorted(positions)


def test_the_mechanical_fields_come_from_the_claim_graph_not_the_model(populated) -> None:
    """The model writes prose; dates, citations and claims are computed. A fabricated
    revision date in `effective_dates` is precisely what this system must not do."""
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)

    assert [c.n for c in answer.citations] == [1, 2]
    assert answer.citations[0].evidence_id == "ev1"
    assert answer.effective_dates == [
        "L33822: revision effective 2024-10-01",
        "A52464: revision effective 2025-01-15",
    ]
    assert [claim.claim_id for claim in answer.claims] == ["c1"]


def test_an_unmapped_citation_is_stripped(populated) -> None:
    """docs/03 §8: "every [n] must map to an evidence id; unmapped citations are
    removed and logged"."""
    model = ScriptedChatModel(
        script=[AIMessage(content=BODY.replace("criteria [1].", "criteria [1][9]."))]
    )
    answer = synthesize(populated, model=model)

    assert "[9]" not in answer.body_markdown
    assert "[1]" in answer.body_markdown  # the valid one survives


def test_surviving_citations_are_not_renumbered(populated) -> None:
    """Renumbering would repoint a good citation at a different passage - an invisible
    misattribution in place of a visible gap."""
    model = ScriptedChatModel(
        script=[AIMessage(content=BODY.replace("medical record [2].", "medical record [7][2]."))]
    )
    answer = synthesize(populated, model=model)

    assert "[2]" in answer.body_markdown
    assert answer.citations[1].n == 2
    assert answer.citations[1].evidence_id == "ev2"


def test_a_missing_sources_section_is_appended(populated) -> None:
    """The gate requires it and it is fully derivable, so a model that ran out of steam
    does not cost the run its sources."""
    truncated = BODY.split("## Sources")[0]
    model = ScriptedChatModel(script=[AIMessage(content=truncated)])
    answer = synthesize(populated, model=model)

    assert "## Sources" in answer.body_markdown
    assert "L33822" in answer.body_markdown
    assert "https://www.cms.gov/doc_lcd" in answer.body_markdown


def test_the_models_own_sources_section_is_left_alone(populated) -> None:
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)
    assert answer.body_markdown.count("## Sources") == 1


def test_the_summary_is_taken_from_the_answer_section(populated) -> None:
    """Taken from the body rather than requested separately, so the two cannot disagree."""
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)

    assert answer.summary.startswith("A therapeutic CGM is covered")
    assert "[1]" not in answer.summary  # citations belong in the body, not the summary
    assert "## Criteria" not in answer.summary


def test_no_evidence_gives_the_unknowns_only_answer(sandboxed_run) -> None:
    """docs/03 §13: "synthesis returns an answer consisting of the scope
    warning/unknowns only; the UI shows it plainly rather than an error"."""
    sandboxed_run.understanding = QueryUnderstanding(
        normalized_question="q", domain="other", question_type="out_of_scope",
        time_sensitivity="low", scope_warning="This is outside Medicare coverage policy.",
    )
    answer = synthesize(sandboxed_run, unresolved=["nothing was found"])

    assert answer.citations == []
    assert answer.confidence == 0.0
    assert "This is outside Medicare coverage policy." in answer.body_markdown
    assert "nothing was found" in answer.body_markdown
    assert answer.scope_warning == "This is outside Medicare coverage policy."


def test_the_prompt_shows_the_model_the_numbers_it_must_use(populated) -> None:
    """A model can only cite [1] and [2] correctly if it was shown [1] and [2]."""
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    synthesize(populated, model=model)

    prompt = "\n".join(str(m.content) for m in model.seen[0])
    assert "[1]" in prompt and "[2]" in prompt
    assert "The beneficiary has diabetes mellitus." in prompt  # the verbatim passage
    assert "L33822" in prompt


def test_the_streamed_tokens_reach_the_callback(populated) -> None:
    """The CLI renders from this and 2.4's SSE stream will too."""
    received: list[str] = []
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    synthesize(populated, model=model, on_token=received.append)

    assert "".join(received).strip() == BODY.strip()


def test_a_streaming_failure_falls_back_to_invoke(populated, monkeypatch) -> None:
    """A run that has done all the searching must not die at the last step over a
    transport feature."""

    class NoStream(ScriptedChatModel):
        def stream(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("streaming unsupported on this endpoint")

    answer = synthesize(populated, model=NoStream(script=[AIMessage(content=BODY)]))
    assert "A therapeutic CGM is covered" in answer.body_markdown


def test_token_usage_is_charged_to_the_run(populated) -> None:
    model = ScriptedChatModel(
        script=[
            AIMessage(
                content=BODY,
                usage_metadata={"input_tokens": 900, "output_tokens": 120, "total_tokens": 1020},
            )
        ]
    )
    synthesize(populated, model=model)
    assert populated.usage.input_tokens == 900
    assert populated.usage.output_tokens == 120


# --- the authored confidence formula ------------------------------------------------


def test_confidence_is_the_mean_of_supported_claims(populated) -> None:
    """docs/02 §2.7 defines no derivation; this one is authored and logged so the
    number is written down rather than chosen by a model."""
    assert confidence_for(populated) == pytest.approx(0.9)


def test_confidence_is_discounted_without_a_primary_source(populated) -> None:
    for document in populated.documents.values():
        document.source_tier = "official_secondary"
    assert confidence_for(populated) == pytest.approx(0.72)


def test_confidence_is_discounted_when_a_branch_found_nothing(populated) -> None:
    populated.plan.branches.append(
        Branch(branch_id="b2", question="codes?", rationale="r",
               source_hint="coding_article", priority=2)
    )
    assert confidence_for(populated) == pytest.approx(0.72)


def test_contested_claims_only_report_halfway(populated) -> None:
    """The system found things and cannot stand behind them. Zero would be wrong -
    it did find something - and high would be a lie."""
    populated.claims[0].status = "contested"
    assert confidence_for(populated) == pytest.approx(0.4)


def test_no_claims_at_all_is_zero_confidence(sandboxed_run) -> None:
    assert confidence_for(sandboxed_run) == 0.0


# --- the token sink cannot end a run (found live, 1.7) -------------------------------


def test_a_failing_token_sink_does_not_end_the_run(populated) -> None:
    """Measured, not hypothetical: a console that could not encode U+202F raised out of
    the callback, out of the stream, into the invoke fallback, out of that, and killed a
    run that had already gathered all ten of its evidence items."""

    def explodes(text: str) -> None:
        raise UnicodeEncodeError("charmap", text, 0, 1, "character maps to <undefined>")

    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model, on_token=explodes)

    assert "A therapeutic CGM is covered" in answer.body_markdown
    assert answer.citations  # the run finished intact


def test_the_token_sink_is_abandoned_rather_than_retried_per_token(populated) -> None:
    """A broken sink is broken for the rest of the run; calling it once per token would
    log thousands of identical warnings."""
    calls: list[str] = []

    def explodes(text: str) -> None:
        calls.append(text)
        raise RuntimeError("connection dropped")

    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    synthesize(populated, model=model, on_token=explodes)
    assert len(calls) == 1


def test_fullwidth_citation_brackets_are_normalized_and_validated() -> None:
    """Found live: Kimi-K2.6 wrote every citation as a CJK lenticular bracket, which
    sailed straight past the docs/03 §8 check - unmapped numbers were neither checked
    nor dropped, and the whole guarantee was silently off for that run."""
    from prime_search.agents.synthesizer import _validate_citations
    from prime_search.schemas import Citation

    citations = [Citation(n=1, evidence_id="ev1", doc_id="d", url="u", label="l")]
    body, dropped = _validate_citations(
        "criterion【1】 and another【9】 and［1］", citations
    )

    assert "[1]" in body
    assert "【" not in body and "［" not in body
    assert dropped == {9}


def test_dagger_and_line_range_citations_are_normalized() -> None:
    """Second form seen live, in the very next run after the plain lenticular one:
    `【1†L1-L3】`. The line range is discarded - it names lines in a source the
    citation already identifies, and nothing downstream can resolve it."""
    from prime_search.agents.synthesizer import _validate_citations
    from prime_search.schemas import Citation

    citations = [
        Citation(n=n, evidence_id=f"ev{n}", doc_id="d", url="u", label="l") for n in (1, 2)
    ]
    body, dropped = _validate_citations(
        "insulin-treated【1†L1-L3】 or hypoglycemia【2】 but not【9†L5】", citations
    )

    assert "[1]" in body and "[2]" in body
    assert "†" not in body and "L1-L3" not in body
    assert dropped == {9}


def test_the_evidence_block_does_not_print_the_section_twice(populated) -> None:
    """`citation.label` already carries the section, so appending it made every line
    read "...§CODING GUIDELINES, revision effective 2025-02-18, §CODING GUIDELINES" -
    and a live answer copied that shape straight into its Sources list."""
    from prime_search.agents.synthesizer import _render_evidence
    from prime_search.evidence.cite import build_citations

    citations = build_citations(populated.evidence, populated.documents)
    block = _render_evidence(populated, citations)
    assert block.count("Coverage Indications") == len(citations)


def test_the_sources_list_matches_the_citations_exactly(populated) -> None:
    """A live answer cited seven passages and printed nine sources - a reader following
    [4] to a list that agrees with neither Answer.citations nor the docs/04 section 7
    evaluator. The list is derived, so the three cannot disagree."""
    body = BODY.replace("[2]", "")  # the answer ends up citing only [1]
    model = ScriptedChatModel(script=[AIMessage(content=body)])
    answer = synthesize(populated, model=model)

    assert [c.n for c in answer.citations] == [1]
    sources = answer.body_markdown.split("## Sources", 1)[1]
    assert "[1]" in sources
    assert "[2]" not in sources  # not cited, so not listed


def test_the_models_own_sources_section_is_replaced_not_duplicated(populated) -> None:
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)
    assert answer.body_markdown.count("## Sources") == 1


def test_a_budget_note_is_added_to_the_unknowns_section(populated) -> None:
    """docs/01 section 9: "answer's 'unknowns' section states the budget was hit". The
    note reaches Answer.unknowns from collect, but a model summarizing its unknowns
    paraphrases the retrieval gaps and drops the one line that says why the answer is
    thin."""
    populated.usage.input_tokens = populated.budget.max_tokens + 1
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)

    section = answer.body_markdown.split("## Unknowns / not verified", 1)[1]
    assert "processing limit" in section.split("## Sources")[0]


def test_raw_doc_ids_become_document_titles(populated) -> None:
    """A live answer's Unknowns named "doc_7e7be1abff". A reader cannot look that up."""
    post = _document("doc_7e7be1abff", title="Dexcom community post", url="https://facebook.com/dexcom/posts/1")
    populated.documents[post.doc_id] = post
    body = BODY.replace(
        "- Whether a later revision exists.\n",
        "- Whether a later revision exists.\n- The claim in doc_7e7be1abff and doc_0123456789 was not confirmed.\n",
    )
    model = ScriptedChatModel(script=[AIMessage(content=body)])
    answer = synthesize(populated, model=model, unresolved=["doc_7e7be1abff could not be read"])

    assert answer.unknowns == ['"Dexcom community post" could not be read']
    assert 'The claim in "Dexcom community post" and a source document was not confirmed.' in answer.body_markdown
    assert "doc_7e7be1abff" not in answer.body_markdown and "doc_0123456789" not in answer.body_markdown


def test_no_budget_note_when_nothing_was_exhausted(populated) -> None:
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)
    assert "processing limit" not in answer.body_markdown
    assert "time limit" not in answer.body_markdown


def test_the_scope_warning_is_carried_into_the_body_verbatim(populated) -> None:
    """docs/03 §8: "Carry scope_warning from understanding into the answer verbatim."
    The prompt asks; this makes it true, because it is the one sentence a model is most
    likely to smooth away."""
    populated.understanding.scope_warning = (
        "This asks for a treatment decision for a specific person."
    )
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])  # the model omits it
    answer = synthesize(populated, model=model)

    assert populated.understanding.scope_warning in answer.body_markdown
    assert answer.scope_warning == populated.understanding.scope_warning
    # ...and it appears before the answer text it qualifies.
    body = answer.body_markdown
    assert body.index(populated.understanding.scope_warning) < body.index("A therapeutic CGM")


def test_the_summary_is_the_answer_not_the_caveat(populated) -> None:
    """docs/02 §2.7 asks `summary` for a "2-4 sentence direct answer", and the UI shows
    it as one line. Leading every out-of-scope answer with the caveat would bury the
    finding; `Answer.scope_warning` carries the sentence separately."""
    populated.understanding.scope_warning = "This is a policy-level answer only."
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    answer = synthesize(populated, model=model)

    assert answer.summary.startswith("A therapeutic CGM is covered")
    assert "This is a policy-level answer only." not in answer.summary


# --- contradictions reach the answer (task 2.2) -------------------------------------------


def _contested(ws, *, against_doc: str = "doc_web"):  # noqa: ANN001, ANN202
    """Turn c1 into a contested claim: the LCD for it, a web guide (or the article) against."""
    if against_doc == "doc_web":
        ws.documents["doc_web"] = Document(
            doc_id="doc_web", url="https://example.com/cgm-guide", title="CGM guide",
            source_tier="web", retrieved_at=datetime.now(UTC), fetch_method="extract",
        )
    text = "Medicare covers a CGM for every person with diabetes."
    ws.evidence.append(
        Evidence(
            evidence_id="ev_against", doc_id=against_doc, branch_id="b1",
            claim_text="A beneficiary must have diabetes", evidence_text=text,
            location=Location(paragraph_index=0, char_start=0, char_end=len(text)),
            effective_date=None, relevance=0.8,
            source_quality=0.3 if against_doc == "doc_web" else 1.0, confidence=0.9,
            stance="contradicts",
        )
    )
    ws.claims[0] = ws.claims[0].model_copy(
        update={"status": "contested", "supported_by": ["ev1"], "contradicted_by": ["ev_against"]}
    )
    return ws


def test_a_contested_claim_becomes_a_readable_contradiction_line(populated) -> None:
    """docs/05 §2's contradiction evaluator asks whether the answer states which source
    governs; a claim id says neither."""
    assert contradiction_lines(_contested(populated)) == [
        'L33822: A beneficiary must have diabetes - contradicted by example.com '
        '("Medicare covers a CGM for every person with diabetes."); '
        "L33822 governs (primary policy over web page)"
    ]


def test_the_later_effective_date_governs_between_equal_tiers(populated) -> None:
    lines = contradiction_lines(_contested(populated, against_doc="doc_art"))
    assert lines[0].endswith("A52464 governs (later effective date 2025-01-15)")


def test_the_critics_contradictions_are_added(populated) -> None:
    """The claim graph only sees disagreement inside a branch; the critic's are how a
    cross-branch one reaches the answer."""
    description = "A web guide says every diabetic qualifies; L33822 requires more; the LCD governs"
    review = CriticReport(contradictions=["c1", description], completion_probability=0.5, reasoning="r")

    lines = contradiction_lines(populated, review)  # c1 is not contested in the graph
    assert lines[0].startswith('Reviewer: "A beneficiary must have diabetes" (c1)')
    assert lines[1] == description


def test_a_contested_claim_the_critic_also_flags_is_listed_once(populated) -> None:
    ws = _contested(populated)
    review = CriticReport(contradictions=["c1"], completion_probability=0.5, reasoning="r")
    assert len(contradiction_lines(ws, review)) == 1


def test_the_answer_field_holds_readable_lines_not_claim_ids(populated) -> None:
    ws = _contested(populated)
    answer = synthesize(ws, model=ScriptedChatModel(script=[AIMessage(content=BODY)]))
    assert answer.contradictions == contradiction_lines(ws)
    assert "c1" not in answer.contradictions


def test_none_found_is_replaced_when_there_are_contradictions(populated) -> None:
    ws = _contested(populated)
    answer = synthesize(ws, model=ScriptedChatModel(script=[AIMessage(content=BODY)]))

    section = answer.body_markdown.split("## Contradictions and caveats")[1].split("## Unknowns")[0]
    assert "None found." not in section
    assert "L33822 governs (primary policy over web page)" in section


def test_a_contradictions_section_the_model_wrote_is_left_alone(populated) -> None:
    """The model's own section is cited; the inserted bullets are not."""
    ws = _contested(populated)
    written = BODY.replace("None found.", "The web guide overstates coverage; the LCD governs [1].")
    answer = synthesize(ws, model=ScriptedChatModel(script=[AIMessage(content=written)]))

    assert "The web guide overstates coverage; the LCD governs [1]." in answer.body_markdown
    assert "primary policy over web page" not in answer.body_markdown


def test_a_missing_contradictions_section_is_inserted_before_unknowns(populated) -> None:
    ws = _contested(populated)
    body = BODY.replace("## Contradictions and caveats\n\nNone found.\n\n", "")
    answer = synthesize(ws, model=ScriptedChatModel(script=[AIMessage(content=body)]))

    text = answer.body_markdown
    assert text.index("## Contradictions and caveats") < text.index("## Unknowns")


def test_the_reviewers_notes_reach_the_prompt(populated) -> None:
    review = CriticReport(
        contradictions=["A web guide says every diabetic qualifies; the LCD governs"],
        outdated_sources=["doc_lcd"],
        missing_interpretations=["Part B versus Part D"],
        completion_probability=0.55,
        reasoning="r",
    )
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    synthesize(populated, model=model, review=review)

    prompt = "\n".join(str(m.content) for m in model.seen[0])
    assert "## What the reviewer found" in prompt
    assert "Completion probability 0.55." in prompt
    assert "A web guide says every diabetic qualifies; the LCD governs" in prompt
    assert "L33822 (LCD, dated 2024-10-01)" in prompt
    assert "Part B versus Part D" in prompt


def test_no_review_says_so_in_the_prompt(populated) -> None:
    model = ScriptedChatModel(script=[AIMessage(content=BODY)])
    synthesize(populated, model=model)
    assert "(no review was run)" in "\n".join(str(m.content) for m in model.seen[0])


def test_inserted_contradiction_bullets_carry_their_citations(populated) -> None:
    """docs/03 §8: "Every factual sentence carries a `[n]` citation"."""
    import re

    ws = _contested(populated)
    answer = synthesize(ws, model=ScriptedChatModel(script=[AIMessage(content=BODY)]))
    section = answer.body_markdown.split("## Contradictions and caveats")[1].split("## Unknowns")[0]
    assert re.search(r"governs \(primary policy over web page\) \[\d+\]\[\d+\]", section), section


def test_the_critics_uncited_sentences_stay_out_of_the_body(populated) -> None:
    """They reach `Answer.contradictions`, but no passage stands behind them."""
    description = "A web guide says every diabetic qualifies; the LCD governs"
    review = CriticReport(contradictions=[description], completion_probability=0.5, reasoning="r")
    answer = synthesize(populated, model=ScriptedChatModel(script=[AIMessage(content=BODY)]), review=review)

    assert answer.contradictions == [description]
    section = answer.body_markdown.split("## Contradictions and caveats")[1].split("## Unknowns")[0]
    assert section.strip() == "None found."

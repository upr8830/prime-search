"""The document view and bench endpoints (docs/07 §5–7), offline."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from prime_search import events
from prime_search.api import main
from prime_search.primitives import within
from prime_search.schemas import Document, Evidence, Location, RunRequest
from prime_search.workspace import Workspace

PARAGRAPHS = 250


@pytest.fixture
def client(tmp_path, offline_credentials):
    events.set_runs_root(tmp_path / "runs")
    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        events.set_runs_root("runs")


def _evidence(evidence_id: str, doc_id: str) -> Evidence:
    text = "Paragraph number 0 describes coverage."
    return Evidence(
        evidence_id=evidence_id, doc_id=doc_id, branch_id="b1", claim_text=text, evidence_text=text,
        location=Location(paragraph_index=0, char_start=0, char_end=len(text)),
        relevance=0.8, source_quality=1.0, confidence=0.9, stance="supports",
    )


def _saved_run(*, text_path: str | None = None, write_local: bool = True) -> tuple[str, str]:
    """A run with one fetched document of 250 paragraphs, one snippet-only document, and
    evidence from both the fetched one and another document."""
    ws = Workspace(objective="q")
    text = "\n\n".join(f"Paragraph number {i} describes coverage." for i in range(PARAGRAPHS))
    count = len(within.split_paragraphs(within.normalize_text(text)))
    local = events.run_dir(ws.run_id) / "docs" / "doc_lcd.txt"
    if write_local:
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(text, encoding="utf-8")
    now = datetime.now(UTC)
    ws.documents["doc_lcd"] = Document(
        doc_id="doc_lcd", url="https://www.cms.gov/lcd", title="LCD", source_tier="primary_policy",
        retrieved_at=now, fetch_method="extract", text_path=text_path or str(local), paragraph_count=count,
    )
    ws.documents["doc_snip"] = Document(
        doc_id="doc_snip", url="https://example.org/", title="snippet", source_tier="web",
        retrieved_at=now, fetch_method="snippet_only",
    )
    ws.evidence.extend([_evidence("ev1", "doc_lcd"), _evidence("ev2", "doc_other")])
    events.write_run_artifacts(ws.to_record(RunRequest(question="q"), status="completed"))
    return ws.run_id, text


def test_paragraphs_are_paginated_at_200_with_the_documents_evidence(client) -> None:
    run_id, _ = _saved_run()
    first = client.get(f"/docs/{run_id}/doc_lcd").json()
    assert (first["total"], len(first["paragraphs"]), first["limit"], first["text_error"]) == (PARAGRAPHS, 200, 200, None)
    assert first["paragraphs"][0]["text"] == "Paragraph number 0 describes coverage."
    assert [item["evidence_id"] for item in first["evidence"]] == ["ev1"]

    rest = client.get(f"/docs/{run_id}/doc_lcd", params={"offset": 200}).json()
    assert len(rest["paragraphs"]) == 50 and rest["paragraphs"][0]["index"] == 200
    assert client.get(f"/docs/{run_id}/doc_lcd", params={"limit": 500}).status_code == 422


def test_text_is_read_from_the_runs_own_folder_when_the_recorded_path_is_foreign(client) -> None:
    # A committed example run carries an absolute path from the machine that ran it.
    run_id, _ = _saved_run(text_path="C:/Users/someone-else/runs/x/docs/doc_lcd.txt")
    view = client.get(f"/docs/{run_id}/doc_lcd").json()
    assert view["total"] == PARAGRAPHS and view["text_error"] is None


def test_a_path_outside_the_runs_root_is_never_read(client, tmp_path) -> None:
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("secret", encoding="utf-8")
    run_id, _ = _saved_run(text_path=str(outside), write_local=False)
    view = client.get(f"/docs/{run_id}/doc_lcd").json()
    assert view["paragraphs"] == [] and "not stored with this run" in view["text_error"]


def test_a_snippet_only_document_returns_metadata_and_a_text_error(client) -> None:
    run_id, _ = _saved_run()
    view = client.get(f"/docs/{run_id}/doc_snip").json()
    assert view["document"]["fetch_method"] == "snippet_only"
    assert view["paragraphs"] == [] and "snippet_only" in view["text_error"]


def test_unknown_runs_and_documents_are_404(client) -> None:
    run_id, _ = _saved_run()
    assert client.get(f"/docs/{run_id}/doc_missing").status_code == 404
    assert client.get("/docs/not-a-run/doc_lcd").status_code == 404
    assert client.get(f"/docs/{run_id}/..%2F..%2Fstate").status_code == 404


def test_bench_questions_never_carry_the_answer_key(client) -> None:
    questions = client.get("/bench/questions").json()
    assert len(questions) == 30
    assert set(questions[0]) == {"id", "question", "domain", "tier", "question_type", "split"}
    dev = client.get("/bench/questions", params={"split": "dev"}).json()
    assert len(dev) == 5 and {question["split"] for question in dev} == {"dev"}


def test_bench_summary_serves_the_latest_report_or_says_it_is_missing(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "LATEST_REPORT", tmp_path / "latest.json")
    assert client.get("/bench/summary").json() == {"missing": True}
    (tmp_path / "latest.json").write_text(json.dumps({"split": "dev", "configs": []}), encoding="utf-8")
    assert client.get("/bench/summary").json() == {"split": "dev", "configs": []}

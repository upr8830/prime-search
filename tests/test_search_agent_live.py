"""docs/09 §1.6's acceptance Check, against the live stack.

    uv run --env-file .env pytest tests/test_search_agent_live.py -m live -q -s

The spec's words: "on task 'current LCD coverage criteria for therapeutic CGM' the
agent fetches L33822 and adds >= 3 evidence items with verbatim passages and dates.
Record the trace URL in the build log."

`-s` matters: the trace URL is printed for the build log.

**This check is model-dependent, and the tool-call cap is why.** Observed over five
runs on 2026-09-12: four recorded 3 or more evidence items, one recorded 2. docs/03
§13's cap is 8 calls, and the minimum useful path spends 3 of them before any evidence
exists (search, fetch, search_within) — so an agent that searches twice, or reads twice
before recording, cannot reach 3 items. L33822 states five separate eligibility
criteria, and rule 3 ("one atomic claim per evidence item") correctly pushes the agent
to record each one, which is more than the remaining calls allow.

The cap stays at the spec's default rather than being raised to make this green: in the
real graph `dispatch` fans out up to `max_agents` (6) sub-agents, each with its own 8
calls, so a whole question gets far more budget than this single task does. If this
check proves too flaky to rely on, the fix is a decision about `MAX_TOOL_CALLS`, not a
looser assertion here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prime_search import events
from prime_search.agents.search_agent import run_search_agent
from prime_search.evidence.store import EvidenceStore
from prime_search.schemas import SearchTask
from prime_search.tracing import trace_run
from prime_search.workspace import new_workspace


@pytest.mark.live
def test_the_agent_cites_l33822_verbatim_with_dates(tmp_path: Path) -> None:
    events.set_runs_root(tmp_path)
    try:
        ws = new_workspace(
            "Current LCD coverage criteria for therapeutic CGM", depth="deep"
        )
        store = EvidenceStore(documents=ws.documents, items=ws.evidence)
        task = SearchTask(
            task_id="t1",
            branch_id="b1",
            round=0,
            instruction=(
                "Find the current LCD coverage criteria for therapeutic continuous "
                "glucose monitors under Medicare, and the revision date of that LCD."
            ),
            queries_hint=["LCD L33822 glucose monitors therapeutic CGM coverage criteria"],
            include_domains=["cms.gov"],
        )

        with trace_run("search_agent_check_1_6", tags=["check:1.6"]) as handle:
            result = run_search_agent(task, ws=ws, store=store)
        print(f"\nLangSmith trace: {handle.url}")
        print(f"summary: {result.summary}")
        print(f"unresolved: {result.unresolved}")
        for item in ws.evidence:
            print(
                f"  [{item.stance:11}] p{item.location.paragraph_index:<4} "
                f"{item.effective_date} {item.evidence_text[:70]!r}"
            )

        # "the agent fetches L33822"
        external = {
            ws.documents[doc_id].document_id_external for doc_id in result.documents_fetched
        }
        assert "L33822" in external, f"fetched {external}"

        # "adds >= 3 evidence items"
        assert len(result.evidence_ids) >= 3, f"only {len(result.evidence_ids)}"

        # "with verbatim passages" — every stored passage still slices exactly out of
        # the persisted document text (docs/04 §3 rule 2).
        assert store.verify() == []

        # "and dates"
        dated = [item for item in ws.evidence if item.effective_date]
        assert len(dated) >= 3, f"only {len(dated)} of {len(ws.evidence)} carry a date"

        # docs/03 §4 rule 4: the document's own revision date, as context evidence.
        assert any(item.stance == "context" for item in ws.evidence)

        # docs/03 §4: ids travel to the root, documents do not.
        assert "http" not in result.model_dump_json()
        assert result.summary

        # The events the UI replays (docs/02 §4).
        types = [event["type"] for event in events.replay(ws.run_id)]
        assert types[0] == "task.started" and types[-1] == "task.done"
        assert {"search", "fetch", "evidence"} <= set(types)
    finally:
        events.set_runs_root("runs")

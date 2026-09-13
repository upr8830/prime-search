"""`eval/searchbench/sync.py` against an in-memory stand-in for the LangSmith client.

The property docs/05 §1 asks for is idempotence keyed by `id`, so the tests that matter
run the sync twice and assert the second run changes nothing.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from eval.searchbench.schema import load_records
from eval.searchbench.sync import DATASET_NAME, check, example_id, plan_sync, sync
from eval.searchbench.schema import BenchRecord


def _record(record_id: str = "cgm-elig-001", split: str = "train", **key) -> BenchRecord:
    answer_key = {"summary": "s", "as_of": "2026-09-13", "validated_by": "reviewer"}
    answer_key.update(key)
    return BenchRecord.model_validate(
        {
            "id": record_id,
            "domain": "cgm",
            "tier": 2,
            "question_type": "eligibility",
            "question": "q",
            "split": split,
            "answer_key": answer_key,
        }
    )


class FakeClient:
    def __init__(self) -> None:
        self.dataset = None
        self.examples: dict[str, SimpleNamespace] = {}
        self.calls: list[str] = []

    def has_dataset(self, *, dataset_name: str) -> bool:
        return self.dataset is not None and self.dataset.name == dataset_name

    def read_dataset(self, *, dataset_name: str):
        return self.dataset

    def create_dataset(self, name: str, **_):
        self.calls.append("create_dataset")
        self.dataset = SimpleNamespace(id=uuid.uuid4(), name=name)
        return self.dataset

    def list_examples(self, *, dataset_id):
        return list(self.examples.values())

    def _store(self, payload: dict) -> None:
        self.examples[payload["id"]] = SimpleNamespace(
            id=uuid.UUID(payload["id"]),
            inputs=payload["inputs"],
            outputs=payload["outputs"],
            # LangSmith returns the split inside metadata, as a list.
            metadata={**payload["metadata"], "dataset_split": [payload["split"]]},
        )

    def create_examples(self, *, dataset_id, examples):
        self.calls.append("create_examples")
        for payload in examples:
            self._store(payload)

    def update_examples(self, *, dataset_id, updates):
        self.calls.append("update_examples")
        for payload in updates:
            self._store(payload)

    def delete_examples(self, example_ids):
        self.calls.append("delete_examples")
        for example in example_ids:
            del self.examples[example]


def test_example_ids_are_stable_and_distinct_per_record() -> None:
    assert example_id("cgm-elig-001") == example_id("cgm-elig-001")
    assert example_id("cgm-elig-001") != example_id("cgm-elig-002")


def test_a_second_sync_changes_nothing() -> None:
    client = FakeClient()
    records = [_record("a"), _record("b", split="dev")]

    first = sync(records, client)
    client.calls.clear()
    second = sync(records, client)

    assert len(first.create) == 2 and client.dataset.name == DATASET_NAME
    assert second.unchanged == ["a", "b"]
    assert not (second.create or second.update or second.delete)
    assert client.calls == []


def test_an_edited_key_or_split_is_updated_in_place_and_a_removed_record_deleted() -> None:
    client = FakeClient()
    sync([_record("a"), _record("b")], client)

    plan = sync([_record("a", summary="corrected"), ], client)

    assert [e["id"] for e in plan.update] == [example_id("a")]
    assert plan.delete == [example_id("b")]
    assert client.examples[example_id("a")].outputs["summary"] == "corrected"
    assert plan_sync([_record("a", split="dev", summary="corrected")], client.examples).update


def test_unvalidated_keys_and_wrong_split_sizes_are_refused() -> None:
    problems = check([_record("a", validated_by=None)])

    assert any("validated_by" in p and "a" in p for p in problems)
    assert any("split sizes" in p for p in problems)


def test_the_committed_dataset_is_ready_to_freeze() -> None:
    """The docs/09 §2.1 gate: 30 records validated, splits 15/5/10."""
    assert check(load_records()) == []

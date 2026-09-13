"""Push SearchBench v0 to LangSmith as `searchbench-v0` (docs/08 §2 step 4, docs/05 §1).

**Idempotent, keyed by `id`** (docs/05 §1). Each record's LangSmith example id is a
UUIDv5 of the record id, so a re-run updates the example it created rather than adding
a second copy, and an unchanged record costs nothing. An example whose record no longer
exists is deleted: the dataset is a mirror of the committed `.jsonl`, and a stale key
left behind would be scored by every later experiment.

**Refuses unvalidated keys.** docs/08 §1: a run against a key nobody validated
measures the author's memory, not the system. It also refuses split sizes other than
docs/08 §6's 15/5/10, because the split is part of the dataset version (§6) and the
holdout guarantee (never run GEPA on holdout) is only as good as the split field.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval.searchbench.schema import DATASET, SPLIT_SIZES, BenchRecord, load_records

DATASET_NAME = "searchbench-v0"
_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "prime-search/searchbench-v0")

__all__ = ["DATASET_NAME", "Plan", "check", "example_id", "plan_sync", "sync", "to_example"]


def example_id(record_id: str) -> str:
    """Stable per record: the same `id` always addresses the same LangSmith example."""
    return str(uuid.uuid5(_NAMESPACE, record_id))


def to_example(record: BenchRecord) -> dict[str, Any]:
    """`inputs` is what a run sees; `outputs` is the answer key the evaluators read."""
    return {
        "id": example_id(record.id),
        "inputs": {"question": record.question, "question_id": record.id},
        "outputs": record.answer_key.model_dump(mode="json"),
        "metadata": {
            "id": record.id,
            "domain": record.domain,
            "tier": record.tier,
            "question_type": record.question_type,
        },
        "split": record.split,
    }


def check(records: Sequence[BenchRecord]) -> list[str]:
    """Why these records must not be frozen yet; empty when they may be."""
    problems: list[str] = []
    duplicates = sorted(i for i, n in Counter(r.id for r in records).items() if n > 1)
    if duplicates:
        problems.append(f"duplicate ids: {', '.join(duplicates)}")
    unvalidated = [r.id for r in records if not r.answer_key.is_validated]
    if unvalidated:
        problems.append(
            f"{len(unvalidated)} record(s) lack validated_by/as_of (docs/08 §2 step 3): "
            + ", ".join(unvalidated)
        )
    sizes = dict(Counter(r.split for r in records))
    if sizes != SPLIT_SIZES:
        problems.append(f"split sizes {sizes} differ from docs/08 §6 {SPLIT_SIZES}")
    return problems


@dataclass
class Plan:
    create: list[dict[str, Any]] = field(default_factory=list)
    update: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)  # LangSmith example ids


def plan_sync(records: Sequence[BenchRecord], existing: Mapping[str, Any]) -> Plan:
    """Diff the records against `existing` (example id -> example as LangSmith returned it)."""
    plan = Plan()
    wanted: set[str] = set()
    for record in records:
        example = to_example(record)
        wanted.add(example["id"])
        current = existing.get(example["id"])
        if current is None:
            plan.create.append(example)
        elif _differs(example, current):
            plan.update.append(example)
        else:
            plan.unchanged.append(record.id)
    plan.delete = sorted(set(existing) - wanted)
    return plan


def _differs(example: Mapping[str, Any], current: Any) -> bool:
    metadata = dict(current.metadata or {})
    split = metadata.pop("dataset_split", None)
    if isinstance(split, list) and len(split) == 1:
        split = split[0]
    return (
        current.inputs != example["inputs"]
        or current.outputs != example["outputs"]
        or {k: metadata.get(k) for k in example["metadata"]} != example["metadata"]
        or split != example["split"]
    )


def sync(records: Sequence[BenchRecord], client: Any) -> Plan:
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        dataset = client.create_dataset(
            DATASET_NAME,
            description="SearchBench v0: Medicare CGM / GLP-1 coverage questions with "
            "human-validated answer keys (docs/08).",
            metadata={"source": DATASET.as_posix()},
        )
    existing = {str(ex.id): ex for ex in client.list_examples(dataset_id=dataset.id)}
    plan = plan_sync(records, existing)
    if plan.create:
        client.create_examples(dataset_id=dataset.id, examples=plan.create)
    if plan.update:
        client.update_examples(dataset_id=dataset.id, updates=plan.update)
    if plan.delete:
        client.delete_examples(plan.delete)
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.searchbench.sync",
        description=f"Push SearchBench to LangSmith as {DATASET_NAME!r} (docs/08 §2 step 4).",
    )
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument(
        "--check", action="store_true", help="validate and print split counts; no network"
    )
    args = parser.parse_args(argv)

    records = load_records(args.dataset)
    counts = Counter(r.split for r in records)
    for split in SPLIT_SIZES:
        validated = sum(r.answer_key.is_validated for r in records if r.split == split)
        print(f"{split:<8} {counts[split]:>2} records, {validated:>2} validated")
    problems = check(records)
    if problems:
        for problem in problems:
            print(f"refusing to sync: {problem}", file=sys.stderr)
        return 1
    if args.check:
        return 0

    from langsmith import Client

    from prime_search.config import get_settings

    get_settings().export_sdk_env()
    plan = sync(records, Client())
    print(
        f"{DATASET_NAME}: {len(plan.create)} created, {len(plan.update)} updated, "
        f"{len(plan.unchanged)} unchanged, {len(plan.delete)} deleted"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

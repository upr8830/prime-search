"""`eval/searchbench/sync.py` against the real LangSmith dataset.

    uv run --env-file .env pytest tests/test_searchbench_sync_live.py -m live -q

`tests/test_searchbench_sync.py` proves idempotence against a fake that assumes LangSmith
returns an example's split as `metadata["dataset_split"]`, a one-element list. If the
real service returned it any other way, every sync would rewrite all 30 examples and the
fake would never notice. This runs the sync for real and asserts it changes nothing.
"""

from __future__ import annotations

import pytest

from eval.searchbench.schema import SPLIT_SIZES, load_records
from eval.searchbench.sync import DATASET_NAME, sync

pytestmark = pytest.mark.live


def test_syncing_the_committed_dataset_again_changes_nothing() -> None:
    from langsmith import Client

    from prime_search.config import get_settings

    get_settings().export_sdk_env()
    client = Client()
    records = load_records()

    sync(records, client)  # converge first, in case the file changed since the last sync
    plan = sync(records, client)

    assert not (plan.create or plan.update or plan.delete), plan
    assert len(plan.unchanged) == len(records) == sum(SPLIT_SIZES.values())
    dataset = client.read_dataset(dataset_name=DATASET_NAME)
    splits = [tuple(e.metadata.get("dataset_split") or ()) for e in client.list_examples(dataset_id=dataset.id)]
    assert {split: splits.count((split,)) for split in SPLIT_SIZES} == SPLIT_SIZES

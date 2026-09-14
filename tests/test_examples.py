"""The committed example runs (`runs/examples/`), which a reader without API keys browses in
the UI (docs/11 R8): valid records of both modes, no local paths, fetched text only from
.gov sources, and served by the API with no keys and no `.env`."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from prime_search.schemas import RunRecord

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "runs" / "examples"
RUN_DIRS = sorted(path for path in EXAMPLES.iterdir() if path.is_dir()) if EXAMPLES.is_dir() else []
KEY_VARIABLES = (
    "TAVILY_API_KEY", "NEBIUS_API_KEY", "LANGSMITH_API_KEY",
    "PRIME_TAVILY_API_KEY", "PRIME_NEBIUS_API_KEY", "PRIME_LANGSMITH_API_KEY",
)


def test_there_are_example_runs_of_both_modes() -> None:
    modes = {json.loads((run_dir / "state.json").read_text(encoding="utf-8"))["request"]["mode"] for run_dir in RUN_DIRS}
    assert modes == {"baseline", "prime"}


@pytest.mark.parametrize("run_dir", RUN_DIRS, ids=lambda path: path.name)
def test_an_example_is_a_valid_record_with_no_local_paths_and_only_public_text(run_dir: Path) -> None:
    record = RunRecord.model_validate_json((run_dir / "state.json").read_text(encoding="utf-8"))
    assert record.answer is not None and record.answer.body_markdown
    for path in run_dir.rglob("*"):
        if path.is_file():
            assert not re.search(r"[A-Za-z]:[\\/]+Users[\\/]", path.read_text(encoding="utf-8")), path
    docs = run_dir / "docs"
    for text_file in docs.glob("*.txt") if docs.is_dir() else []:
        host = (urlsplit(record.documents[text_file.stem].url).hostname or "").lower()
        assert host.endswith(".gov"), f"{text_file.name}: fetched text from {host} is not a .gov source"


def test_the_api_serves_the_examples_without_keys(tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from prime_search import events
    from prime_search.api import main
    from prime_search.config import get_settings

    root = tmp_path / "runs"
    shutil.copytree(EXAMPLES, root / "examples")
    for name in KEY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here, so settings cannot load keys
    get_settings.cache_clear()
    events.set_runs_root(root)
    try:
        with TestClient(main.app) as client:
            rows = client.get("/runs").json()
            assert {row["run_id"] for row in rows} == {run_dir.name for run_dir in RUN_DIRS}
            assert all(row["example"] for row in rows)
            for run_dir in RUN_DIRS:
                assert client.get(f"/runs/{run_dir.name}").json()["answer"]["body_markdown"]
                assert client.get(f"/runs/{run_dir.name}/events").json()
    finally:
        events.set_runs_root(REPO / "runs")
        get_settings.cache_clear()

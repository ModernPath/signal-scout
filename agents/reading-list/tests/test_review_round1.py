"""Regression tests from review round 1."""

from __future__ import annotations

import json
import os


def _rows():
    return [
        {"id": "item_a", "title": "A", "url": "https://e.com/a", "tags": ["dev"],
         "added_at": "2025-01-01T00:00:00+00:00"},
        {"id": "item_b", "title": "B", "url": "https://e.com/b", "tags": [],
         "added_at": "2025-01-02T00:00:00+00:00"},
    ]


def test_process_environment_wins_over_dotenv_files(tmp_path, monkeypatch):
    import agent_env

    folder = tmp_path / "agent"
    folder.mkdir()
    (folder / ".env").write_text("READING_LIST_DATA_DIR=/from/env\nRL_ONLY_IN_FILE=1\n")
    (folder / ".env.local").write_text(
        "READING_LIST_DATA_DIR=/from/env_local\nREADING_LIST_OFFLINE=0\n"
    )
    monkeypatch.setattr(agent_env, "AGENT_DIR", folder)
    monkeypatch.setenv("READING_LIST_DATA_DIR", "/from/process")
    monkeypatch.setenv("READING_LIST_OFFLINE", "1")
    monkeypatch.delenv("RL_ONLY_IN_FILE", raising=False)

    try:
        agent_env.load_agent_environment()
        assert os.environ["READING_LIST_DATA_DIR"] == "/from/process"
        assert os.environ["READING_LIST_OFFLINE"] == "1"
        # Variables not already set are still loaded from the files.
        assert os.environ["RL_ONLY_IN_FILE"] == "1"
    finally:
        os.environ.pop("RL_ONLY_IN_FILE", None)


def test_service_unnormalizable_tag_filter_never_returns_whole_list(seed):
    import reading_list_service as service
    from memory.memory import ReadingListStore

    seed(*_rows())
    try:
        result = service.list_items(ReadingListStore(), tag="!!!")
    except ValueError:
        return
    items = result["items"] if isinstance(result, dict) else result
    assert items == []


def test_core_filter_rejects_or_empties_unnormalizable_tag():
    import reading_list_core as core

    items = [core.Item.from_dict({"note": "", "read_at": None, **row}) for row in _rows()]
    try:
        out = core.filter_items(items, tag="!!!")
    except ValueError:
        return
    assert out == []


def test_list_items_tool_handles_unnormalizable_tag(run_script, seed):
    seed(*_rows())
    proc = run_script("tools/list_items.py", "--tag", "!!!")
    payload = json.loads(proc.stdout)
    if payload["status"] == "error":
        assert proc.returncode == 1 and payload["error"]
    else:
        assert payload["data"]["items"] == []

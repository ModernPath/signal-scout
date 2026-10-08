from __future__ import annotations

import json

import pytest


def _ok(proc) -> dict:
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "success"
    return payload["data"]


def _err(proc) -> dict:
    assert proc.returncode == 1, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["status"] == "error" and payload["error"]
    assert set(payload) == {"status", "error"}
    return payload


def test_tool_clis_emit_single_json_envelope_and_exit_codes(run_script):
    one = _ok(run_script("tools/add_item.py", "--title", "One", "--url", "https://e.com/1",
                         "--note", "hi", "--tags", "Dev, ai"))
    assert one["id"].startswith("item_") and one["tags"] == ["dev", "ai"]
    assert one["note"] == "hi" and one["read_at"] is None and one["added_at"]
    two = _ok(run_script("tools/add_item.py", "--title", "Two", "--url", "http://e.com/2", "--tags", "dev"))

    listed = _ok(run_script("tools/list_items.py"))["items"]
    assert {i["id"] for i in listed} == {one["id"], two["id"]}
    assert [i["added_at"] for i in listed] == sorted((i["added_at"] for i in listed), reverse=True)
    assert [i["id"] for i in _ok(run_script("tools/list_items.py", "--tag", "ai"))["items"]] == [one["id"]]

    tagged = _ok(run_script("tools/tag_item.py", "--id", two["id"], "--tags", "DEV, rust"))
    assert tagged["tags"] == ["dev", "rust"]

    ranking = _ok(run_script("tools/rank_items.py"))["ranking"]
    assert {r["id"] for r in ranking} == {one["id"], two["id"]}
    assert [r["rank"] for r in ranking] == [1, 2]
    assert all("tag_boost" in r and r["reason"] for r in ranking)

    read = _ok(run_script("tools/mark_read_item.py", "--id", one["id"]))
    assert read["read_at"]
    assert _ok(run_script("tools/mark_read_item.py", "--id", one["id"]))["read_at"] == read["read_at"]
    assert [i["id"] for i in _ok(run_script("tools/list_items.py", "--unread"))["items"]] == [two["id"]]
    assert [r["id"] for r in _ok(run_script("tools/rank_items.py"))["ranking"]] == [two["id"]]

    summary = _ok(run_script("tools/summarize_items.py"))
    assert (summary["total"], summary["unread"], summary["read"]) == (2, 1, 1)
    assert summary["tags"]["dev"] == 2

    deleted = _ok(run_script("tools/delete_item.py", "--id", one["id"]))
    assert deleted["id"] == one["id"]
    assert [i["id"] for i in _ok(run_script("tools/list_items.py"))["items"]] == [two["id"]]


@pytest.mark.parametrize(
    "script,args",
    [
        ("tools/add_item.py", ["--title", "", "--url", "https://e.com"]),
        ("tools/add_item.py", ["--title", "T", "--url", "ftp://e.com"]),
        ("tools/add_item.py", ["--title", "T", "--url", "https://e.com", "--note", "x" * 501]),
        ("tools/tag_item.py", ["--id", "item_missing", "--tags", "a"]),
        ("tools/mark_read_item.py", ["--id", "item_missing"]),
        ("tools/delete_item.py", ["--id", "item_missing"]),
    ],
)
def test_tool_error_envelopes(run_script, script, args):
    _err(run_script(script, *args))
    assert _ok(run_script("tools/list_items.py"))["items"] == []


def test_tag_tool_rejects_tags_that_normalize_to_nothing(run_script):
    item = _ok(run_script("tools/add_item.py", "--title", "T", "--url", "https://e.com"))
    _err(run_script("tools/tag_item.py", "--id", item["id"], "--tags", "!!!, ,"))


def test_empty_list_rank_and_summary_are_results_not_errors(run_script):
    assert _ok(run_script("tools/list_items.py")) == {"items": []}
    assert _ok(run_script("tools/rank_items.py")) == {"ranking": []}
    summary = _ok(run_script("tools/summarize_items.py"))
    assert (summary["total"], summary["unread"], summary["read"]) == (0, 0, 0)


def test_memory_cli_inspects_items_json(run_script, isolated_env):
    item = _ok(run_script("tools/add_item.py", "--title", "A", "--url", "https://e.com", "--tags", "x"))
    assert (isolated_env / "items.json").is_file()
    rows = _ok(run_script("memory/memory.py", "list"))
    assert [r["id"] for r in rows] == [item["id"]]
    assert _ok(run_script("memory/memory.py", "get", "--id", item["id"]))["title"] == "A"
    _ok(run_script("memory/memory.py", "delete", "--id", item["id"]))
    assert json.loads((isolated_env / "items.json").read_text()) == []

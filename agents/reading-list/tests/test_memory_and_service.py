from __future__ import annotations

import json

import pytest

import reading_list_service as service
from reading_list_core import NotFoundError

A = "2024-01-01T10:00:00+00:00"
B = "2024-01-02T10:00:00+00:00"


def _items(result):
    return result["items"] if isinstance(result, dict) else result


def _ranking(result):
    return result["ranking"] if isinstance(result, dict) else result


def test_items_persist_to_data_dir_and_delete_removes_record(store, isolated_env):
    assert store.all() == []
    item = service.add_item(store, "First", "https://example.com/1", "a note", "Dev, ai")
    other = service.add_item(store, "Second", "http://example.com/2")
    assert store.path == isolated_env / "items.json"

    rows = json.loads((isolated_env / "items.json").read_text())
    assert {r["id"] for r in rows} == {item["id"], other["id"]}
    saved = next(r for r in rows if r["id"] == item["id"])
    assert set(saved) >= {"id", "title", "url", "note", "tags", "added_at", "read_at"}
    assert saved["tags"] == ["dev", "ai"] and saved["note"] == "a note" and saved["read_at"] is None
    assert not (isolated_env / "items.tmp").exists()

    # a fresh store on the same directory sees the same records
    from memory.memory import ReadingListStore

    assert service.get_item(ReadingListStore(isolated_env), item["id"])["title"] == "First"

    deleted = service.delete_item(store, item["id"])
    assert deleted["id"] == item["id"]
    rows = json.loads((isolated_env / "items.json").read_text())
    assert [r["id"] for r in rows] == [other["id"]]
    with pytest.raises(NotFoundError):
        service.get_item(store, item["id"])
    with pytest.raises(LookupError):
        service.delete_item(store, item["id"])
    assert [i["id"] for i in _items(service.list_items(store))] == [other["id"]]
    assert item["id"] not in [r["id"] for r in _ranking(service.rank_items(store))]


def test_add_rejects_bad_input_without_writing(store, isolated_env):
    for args in [("", "https://e.com"), ("T", "ftp://e.com"), ("T", "e.com"), ("T", "https://e.com", "x" * 501)]:
        with pytest.raises(ValueError):
            service.add_item(store, *args)
    assert store.all() == []
    path = isolated_env / "items.json"
    assert not path.exists() or json.loads(path.read_text()) == []


def test_tag_item_merges_tags_case_insensitively_without_duplicates(store):
    item = service.add_item(store, "T", "https://e.com", tags="dev")
    updated = service.tag_item(store, item["id"], "DEV, AI, #ai, Rust")
    assert updated["tags"] == ["dev", "ai", "rust"]
    assert service.get_item(store, item["id"])["tags"] == ["dev", "ai", "rust"]
    assert service.tag_item(store, item["id"], ["ai", "go"])["tags"] == ["dev", "ai", "rust", "go"]
    with pytest.raises(NotFoundError):
        service.tag_item(store, "item_missing", "x")
    with pytest.raises(ValueError):
        service.tag_item(store, item["id"], "!!!, ,")
    assert service.get_item(store, item["id"])["tags"] == ["dev", "ai", "rust", "go"]


def test_mark_read_sets_read_at_once_and_is_idempotent(store):
    one = service.add_item(store, "One", "https://e.com/1")
    two = service.add_item(store, "Two", "https://e.com/2")
    first = service.mark_read_item(store, one["id"])
    assert first["read_at"]
    again = service.mark_read_item(store, one["id"])
    assert again["read_at"] == first["read_at"]
    assert service.get_item(store, one["id"])["read_at"] == first["read_at"]
    assert [r["id"] for r in _ranking(service.rank_items(store))] == [two["id"]]
    with pytest.raises(NotFoundError):
        service.mark_read_item(store, "item_missing")


def test_list_items_newest_first_with_filters(store, seed):
    assert _items(service.list_items(store)) == []
    seed(
        {"id": "item_a", "title": "A", "url": "https://e.com/a", "tags": ["dev"], "added_at": A},
        {"id": "item_b", "title": "B", "url": "https://e.com/b", "tags": ["ai"], "added_at": B},
        {"id": "item_c", "title": "C", "url": "https://e.com/c", "tags": ["dev"],
         "added_at": "2024-01-03T10:00:00+00:00", "read_at": "2024-02-01T00:00:00+00:00"},
    )
    assert [i["id"] for i in _items(service.list_items(store))] == ["item_c", "item_b", "item_a"]
    assert [i["id"] for i in _items(service.list_items(store, unread=True))] == ["item_b", "item_a"]
    assert [i["id"] for i in _items(service.list_items(store, tag="DEV"))] == ["item_c", "item_a"]
    assert [i["id"] for i in _items(service.list_items(store, tag="dev", unread=True))] == ["item_a"]
    assert set(_items(service.list_items(store))[0]) >= {"id", "title", "url", "note", "tags", "added_at", "read_at"}


def test_rank_and_summarize_use_stored_state(store, seed):
    seed(
        {"id": "item_a", "title": "A", "url": "https://e.com/a", "tags": ["dev"], "added_at": A},
        {"id": "item_b", "title": "B", "url": "https://e.com/b", "tags": ["dev", "ai"], "added_at": B},
        {"id": "item_c", "title": "C", "url": "https://e.com/c", "tags": ["dev"], "added_at": B,
         "read_at": "2024-02-01T00:00:00+00:00"},
    )
    ranking = _ranking(service.rank_items(store))
    assert [r["id"] for r in ranking] == ["item_b", "item_a"]
    assert ranking[0]["tag_boost"] == 4 and ranking[0]["rank"] == 1
    assert ranking == _ranking(service.rank_items(store))
    summary = service.summarize_items(store)
    assert (summary["total"], summary["unread"], summary["read"]) == (3, 2, 1)
    assert dict(summary["tags"]) == {"dev": 3, "ai": 1}

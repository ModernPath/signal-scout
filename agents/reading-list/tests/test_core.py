from __future__ import annotations

import pytest

import reading_list_core as core


def _row(id, added_at, tags=(), read_at=None, title=None):
    return {
        "id": id,
        "title": title or id,
        "url": f"https://example.com/{id}",
        "note": "",
        "tags": list(tags),
        "added_at": added_at,
        "read_at": read_at,
    }


def _items(*rows):
    return [core.Item.from_dict(r) for r in rows]


def test_add_item_requires_title_valid_url_and_normalizes_tags():
    item = core.Item.create(" Great read ", "https://example.com/a", "  worth it ", " Dev ,DEV, #AI news")
    assert item.id.startswith("item_") and len(item.id) == len("item_") + 10
    assert item.title == "Great read"
    assert item.url == "https://example.com/a"
    assert item.note == "worth it"
    assert tuple(item.tags) == ("dev", "ai-news")
    assert item.added_at and item.read_at is None

    assert core.Item.create("x", "http://example.com").url == "http://example.com"
    for bad_title in ("", "   ", None):
        with pytest.raises(ValueError):
            core.Item.create(bad_title, "https://example.com")
    for bad_url in ("", "example.com", "ftp://example.com", "javascript:alert(1)", None):
        with pytest.raises(ValueError):
            core.Item.create("Title", bad_url)
    with pytest.raises(ValueError):
        core.Item.create("Title", "https://example.com", "n" * 501)
    assert core.Item.create("Title", "https://example.com", "n" * 500).note == "n" * 500
    assert core.Item.create("A", "https://example.com").id != core.Item.create("A", "https://example.com").id


def test_read_next_orders_oldest_unread_first_boosted_by_used_tags():
    items = _items(
        _row("item_a", "2024-01-01T10:00:00+00:00", ["dev"]),
        _row("item_b", "2024-01-02T10:00:00+00:00", ["dev", "ai"]),
        _row("item_c", "2023-12-01T10:00:00+00:00"),
        _row("item_d", "2024-01-03T10:00:00+00:00", ["dev"], read_at="2024-02-01T00:00:00+00:00"),
        _row("item_e", "2024-01-04T10:00:00+00:00", ["misc"]),
        _row("item_f", "2024-01-03T09:00:00+00:00", ["misc"]),
    )
    ranking = core.read_next(items)
    # usage over the whole list: dev=3 (incl. the read item), ai=1, misc=2
    assert [r["id"] for r in ranking] == ["item_b", "item_a", "item_f", "item_e", "item_c"]
    assert [r["rank"] for r in ranking] == [1, 2, 3, 4, 5]
    assert [r["tag_boost"] for r in ranking] == [4, 3, 2, 2, 0]
    assert "item_d" not in [r["id"] for r in ranking]

    first = ranking[0]
    for key in ("id", "title", "url", "note", "tags", "added_at", "read_at"):
        assert key in first
    assert "dev" in first["reason"] and "(3)" in first["reason"]
    assert "ai" in first["reason"] and "(1)" in first["reason"]
    assert "2024-01-02" in first["reason"]
    assert "no tag boost" in ranking[-1]["reason"] and "2023-12-01" in ranking[-1]["reason"]

    assert core.read_next(items) == ranking
    assert core.read_next(list(reversed(items))) == ranking
    assert [r["id"] for r in core.read_next(items, limit=2)] == ["item_b", "item_a"]


def test_read_next_ties_break_by_oldest_added_then_id():
    items = _items(
        _row("item_z", "2024-01-01T00:00:00+00:00", ["x"]),
        _row("item_m", "2024-01-01T00:00:00+00:00", ["x"]),
        _row("item_o", "2023-06-01T00:00:00+00:00", ["x"]),
    )
    assert [r["id"] for r in core.read_next(items)] == ["item_o", "item_m", "item_z"]
    assert core.read_next([]) == []


def test_summarize_counts_total_unread_and_tags():
    items = _items(
        _row("item_a", "2024-01-01T00:00:00+00:00", ["dev", "ai"]),
        _row("item_b", "2024-01-02T00:00:00+00:00", ["dev"], read_at="2024-02-01T00:00:00+00:00"),
        _row("item_c", "2024-01-03T00:00:00+00:00"),
    )
    summary = core.summarize(items)
    assert summary["total"] == 3 and summary["unread"] == 2 and summary["read"] == 1
    assert dict(summary["tags"]) == {"dev": 2, "ai": 1}
    empty = core.summarize([])
    assert (empty["total"], empty["unread"], empty["read"]) == (0, 0, 0)
    assert dict(empty["tags"]) == {}

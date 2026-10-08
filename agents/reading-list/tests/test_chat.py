from __future__ import annotations

import reading_list_service as service
from reading_list_chat import chat_reply


def _ranking(result):
    return result["ranking"] if isinstance(result, dict) else result


def test_offline_chat_routes_all_commands_without_provider_key(store):
    added = chat_reply(store, "add Great Article https://example.com/a note: worth a look #Python #ai")
    assert added.used_llm is False and added.tools_used
    assert "Great Article" in added.reply
    items = store.all()
    assert len(items) == 1
    item = items[0]
    assert item.title == "Great Article" and item.url == "https://example.com/a"
    assert item.note == "worth a look" and tuple(item.tags) == ("python", "ai")
    assert item.read_at is None

    other = service.add_item(store, "Second Piece", "https://example.com/b", tags="python")

    listed = chat_reply(store, "list")
    assert "Great Article" in listed.reply and "Second Piece" in listed.reply
    assert listed.used_llm is False

    tagged = chat_reply(store, f"tag {item.id} Rust, PYTHON")
    assert "rust" in tagged.reply.lower()
    assert list(service.get_item(store, item.id)["tags"]) == ["python", "ai", "rust"]

    ranked = chat_reply(store, "rank")
    expected = [r["title"] for r in _ranking(service.rank_items(store))]
    assert len(expected) == 2
    positions = [ranked.reply.index(t) for t in expected]
    assert positions == sorted(positions)

    read = chat_reply(store, f"read {item.id}")
    assert read.used_llm is False and "Great Article" in read.reply
    assert service.get_item(store, item.id)["read_at"]
    unread = chat_reply(store, "list unread")
    assert "Second Piece" in unread.reply and "Great Article" not in unread.reply
    assert "Great Article" not in chat_reply(store, "rank").reply

    summary = chat_reply(store, "summarize")
    assert "2" in summary.reply and "python" in summary.reply.lower()

    deleted = chat_reply(store, f"delete {other['id']}")
    assert "Second Piece" in deleted.reply
    assert [i.id for i in store.all()] == [item.id]


def test_offline_chat_errors_and_help(store):
    for bad in ("add No Url Here", "add Title ftp://example.com/x", "add https://example.com/only-url"):
        result = chat_reply(store, bad)
        assert result.reply and "Traceback" not in result.reply
    assert store.all() == []

    missing = chat_reply(store, "read item_missing")
    assert "item_missing" in missing.reply and "Traceback" not in missing.reply
    assert "item_missing" in chat_reply(store, "delete item_missing").reply
    assert chat_reply(store, "tag item_missing x").reply

    empty = chat_reply(store, "list")
    assert empty.reply and "Traceback" not in empty.reply
    assert chat_reply(store, "rank").reply

    helped = chat_reply(store, "what is the weather")
    assert helped.tools_used == [] and helped.used_llm is False
    for command in ("add", "list", "tag", "rank", "summarize", "read", "delete"):
        assert command in helped.reply
    assert store.all() == []

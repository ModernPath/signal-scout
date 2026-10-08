"""Use cases shared by every interface (CLI, tools, API, chat).

Each function takes a ReadingListStore and returns plain dicts, so callers can
serialize results directly to JSON or LLM tool responses.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import reading_list_core as core
from reading_list_core import Item, Tags
from memory.memory import ReadingListStore


def add_item(
    store: ReadingListStore,
    title: Optional[str],
    url: Optional[str],
    note: Optional[str] = "",
    tags: Tags = None,
) -> Dict[str, Any]:
    return store.add(Item.create(title, url, note, tags)).to_dict()


def get_item(store: ReadingListStore, item_id: str) -> Dict[str, Any]:
    return store.get(item_id).to_dict()


def list_items(
    store: ReadingListStore, *, unread: bool = False, tag: Optional[str] = None
) -> Dict[str, Any]:
    return {"items": [i.to_dict() for i in core.filter_items(store.all(), unread=unread, tag=tag)]}


def rank_items(store: ReadingListStore, *, limit: Optional[int] = None) -> Dict[str, Any]:
    return {"ranking": core.read_next(store.all(), limit=limit)}


def tag_item(store: ReadingListStore, item_id: str, tags: Tags) -> Dict[str, Any]:
    return store.update(store.get(item_id).with_tags(tags)).to_dict()


def mark_read_item(store: ReadingListStore, item_id: str) -> Dict[str, Any]:
    item = store.get(item_id)
    return (store.update(item.mark_read()) if not item.read_at else item).to_dict()


def delete_item(store: ReadingListStore, item_id: str) -> Dict[str, Any]:
    return store.delete(item_id).to_dict()


def summarize_items(store: ReadingListStore) -> Dict[str, Any]:
    return core.summarize(store.all())

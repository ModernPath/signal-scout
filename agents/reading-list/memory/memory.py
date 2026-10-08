#!/usr/bin/env python3
"""
Memory — JSON file store for reading-list items, plus a CLI for direct inspection.

Storage location: memory/data/items.json, or $READING_LIST_DATA_DIR if set.
Retention: items are kept until explicitly deleted; nothing expires.

Usage:
  python memory/memory.py list
  python memory/memory.py get --id item_ab12cd34ef
  python memory/memory.py delete --id item_ab12cd34ef
  python memory/memory.py stats
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

from reading_list_core import Item, NotFoundError, tag_counts  # noqa: E402

DATA_DIR_ENV = "READING_LIST_DATA_DIR"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def default_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else DEFAULT_DATA_DIR


class ReadingListStore:
    """Persists Item objects as a single JSON array. Small, simple, inspectable."""

    FILENAME = "items.json"

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.data_dir / self.FILENAME

    def all(self) -> List[Item]:
        if not self.path.exists():
            return []
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        return [Item.from_dict(row) for row in rows]

    def get(self, item_id: str) -> Item:
        for item in self.all():
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item not found: {item_id}")

    def add(self, item: Item) -> Item:
        self._write([*self.all(), item])
        return item

    def update(self, item: Item) -> Item:
        items = self.all()
        if item.id not in {i.id for i in items}:
            raise NotFoundError(f"Item not found: {item.id}")
        self._write([item if i.id == item.id else i for i in items])
        return item

    def delete(self, item_id: str) -> Item:
        item = self.get(item_id)
        self._write([i for i in self.all() if i.id != item_id])
        return item

    def _write(self, items: List[Item]) -> None:
        # Write to a temp file and rename, so a crash never leaves half-written JSON.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)


def main() -> None:
    from agent_cli import make_parser, run_and_print

    parser = make_parser("Reading List memory CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List all items")
    sub.add_parser("get", help="Show one item").add_argument("--id", required=True)
    sub.add_parser("delete", help="Delete one item").add_argument("--id", required=True)
    sub.add_parser("stats", help="Item and tag counts")
    args = parser.parse_args()

    store = ReadingListStore()
    commands = {
        "list": lambda: [i.to_dict() for i in store.all()],
        "get": lambda: store.get(args.id).to_dict(),
        "delete": lambda: store.delete(args.id).to_dict(),
        "stats": lambda: {"total": len(store.all()), "tags": tag_counts(store.all())},
    }
    run_and_print(commands[args.command])


if __name__ == "__main__":
    main()

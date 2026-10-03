#!/usr/bin/env python3
"""
Memory — JSON file store for notes, plus a CLI for direct inspection.

Storage location: memory/data/notes.json, or $EXAMPLE_AGENT_DATA_DIR if set.

Usage:
  python memory/memory.py list
  python memory/memory.py get --id note_ab12cd34ef
  python memory/memory.py delete --id note_ab12cd34ef
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

from example_core import Note, NotFoundError, tag_counts  # noqa: E402

DATA_DIR_ENV = "EXAMPLE_AGENT_DATA_DIR"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def default_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else DEFAULT_DATA_DIR


class NoteStore:
    """Persists Note objects as a single JSON array. Small, simple, inspectable."""

    FILENAME = "notes.json"

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.data_dir / self.FILENAME

    def all(self) -> List[Note]:
        if not self.path.exists():
            return []
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        return [Note.from_dict(row) for row in rows]

    def get(self, note_id: str) -> Note:
        for note in self.all():
            if note.id == note_id:
                return note
        raise NotFoundError(f"Note not found: {note_id}")

    def add(self, note: Note) -> Note:
        self._write([*self.all(), note])
        return note

    def delete(self, note_id: str) -> Note:
        note = self.get(note_id)
        self._write([n for n in self.all() if n.id != note_id])
        return note

    def _write(self, notes: List[Note]) -> None:
        # Write to a temp file and rename, so a crash never leaves half-written JSON.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([n.to_dict() for n in notes], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)


def main() -> None:
    from agent_cli import run_and_print

    parser = argparse.ArgumentParser(description="Example Agent memory CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List all notes")
    sub.add_parser("get", help="Show one note").add_argument("--id", required=True)
    sub.add_parser("delete", help="Delete one note").add_argument("--id", required=True)
    sub.add_parser("stats", help="Note and tag counts")
    args = parser.parse_args()

    store = NoteStore()
    commands = {
        "list": lambda: [n.to_dict() for n in store.all()],
        "get": lambda: store.get(args.id).to_dict(),
        "delete": lambda: store.delete(args.id).to_dict(),
        "stats": lambda: {"total": len(store.all()), "tags": tag_counts(store.all())},
    }
    run_and_print(commands[args.command])


if __name__ == "__main__":
    main()

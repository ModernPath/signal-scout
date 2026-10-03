#!/usr/bin/env python3
"""Tool: search notes by keywords and/or tag. No arguments lists recent notes.

Usage:
  python tools/search_notes.py --query "bob offer" --tag work --limit 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import run_and_print  # noqa: E402
from example_service import find_notes  # noqa: E402
from memory.memory import NoteStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Search notes")
    parser.add_argument("--query", default="", help="Space-separated keywords")
    parser.add_argument("--tag", help="Only notes with this tag")
    parser.add_argument("--limit", type=int, default=20, help="Max results (default 20)")
    args = parser.parse_args()

    run_and_print(lambda: find_notes(NoteStore(), args.query, tag=args.tag, limit=args.limit))


if __name__ == "__main__":
    main()

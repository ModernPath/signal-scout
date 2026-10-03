#!/usr/bin/env python3
"""Tool: save a note.

Usage:
  python tools/add_note.py --title "Call Bob" --body "About the offer" --tags "work, sales"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import run_and_print  # noqa: E402
from example_service import add_note  # noqa: E402
from memory.memory import NoteStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Save a note")
    parser.add_argument("--title", required=True, help="One-line title")
    parser.add_argument("--body", default="", help="Optional longer text")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    args = parser.parse_args()

    run_and_print(lambda: add_note(NoteStore(), args.title, args.body, args.tags))


if __name__ == "__main__":
    main()

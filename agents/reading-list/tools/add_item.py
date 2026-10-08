#!/usr/bin/env python3
"""Tool: save a reading-list item.

Usage:
  python tools/add_item.py --title "Great read" --url https://example.com --note "why" --tags "dev, ai"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import make_parser, run_and_print  # noqa: E402
from reading_list_service import add_item  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402


def main() -> None:
    parser = make_parser("Save a reading-list item")
    parser.add_argument("--title", required=True, help="Item title")
    parser.add_argument("--url", required=True, help="http(s) URL")
    parser.add_argument("--note", default="", help="Optional note (max 500 chars)")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    args = parser.parse_args()

    run_and_print(lambda: add_item(ReadingListStore(), args.title, args.url, args.note, args.tags))


if __name__ == "__main__":
    main()

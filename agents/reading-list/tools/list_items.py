#!/usr/bin/env python3
"""Tool: list items, newest first.

Usage:
  python tools/list_items.py [--unread] [--tag dev]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import make_parser, run_and_print  # noqa: E402
from reading_list_service import list_items  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402


def main() -> None:
    parser = make_parser("List reading-list items")
    parser.add_argument("--unread", action="store_true", help="Only unread items")
    parser.add_argument("--tag", default=None, help="Only items with this tag")
    args = parser.parse_args()

    run_and_print(lambda: list_items(ReadingListStore(), unread=args.unread, tag=args.tag))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Tool: rank unread items to read next, with a reason for each.

Usage:
  python tools/rank_items.py [--limit 5]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import make_parser, run_and_print  # noqa: E402
from reading_list_service import rank_items  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402


def main() -> None:
    parser = make_parser("Rank unread items to read next")
    parser.add_argument("--limit", type=int, default=None, help="Maximum entries")
    args = parser.parse_args()

    run_and_print(lambda: rank_items(ReadingListStore(), limit=args.limit))


if __name__ == "__main__":
    main()

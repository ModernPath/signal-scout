#!/usr/bin/env python3
"""Tool: merge tags into an item.

Usage:
  python tools/tag_item.py --id item_ab12cd34ef --tags "dev, rust"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import make_parser, run_and_print  # noqa: E402
from reading_list_service import tag_item  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402


def main() -> None:
    parser = make_parser("Add tags to an item")
    parser.add_argument("--id", required=True, help="Item id")
    parser.add_argument("--tags", required=True, help="Comma-separated tags")
    args = parser.parse_args()

    run_and_print(lambda: tag_item(ReadingListStore(), args.id, args.tags))


if __name__ == "__main__":
    main()

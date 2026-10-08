#!/usr/bin/env python3
"""Tool: delete an item by id.

Usage:
  python tools/delete_item.py --id item_ab12cd34ef
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import make_parser, run_and_print  # noqa: E402
from reading_list_service import delete_item  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402


def main() -> None:
    parser = make_parser("Delete an item")
    parser.add_argument("--id", required=True, help="Item id")
    args = parser.parse_args()

    run_and_print(lambda: delete_item(ReadingListStore(), args.id))


if __name__ == "__main__":
    main()

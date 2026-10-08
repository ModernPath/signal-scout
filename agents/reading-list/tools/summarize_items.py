#!/usr/bin/env python3
"""Tool: total/unread/read counts and per-tag counts.

Usage:
  python tools/summarize_items.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import make_parser, run_and_print  # noqa: E402
from reading_list_service import summarize_items  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402


def main() -> None:
    make_parser("Summarize the reading list").parse_args()
    run_and_print(lambda: summarize_items(ReadingListStore()))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Tool: delete a note by id.

Usage:
  python tools/delete_note.py --id note_ab12cd34ef
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import run_and_print  # noqa: E402
from example_service import delete_note  # noqa: E402
from memory.memory import NoteStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete a note")
    parser.add_argument("--id", required=True, help="Note id, e.g. note_ab12cd34ef")
    args = parser.parse_args()

    run_and_print(lambda: delete_note(NoteStore(), args.id))


if __name__ == "__main__":
    main()

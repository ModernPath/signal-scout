#!/usr/bin/env python3
"""
Subagent: summarize notes.

An independent CLI with one job. The main agent runs it as a separate process
(see example_service.run_subagent) and reads the JSON envelope from stdout.
Uses Gemini when an API key is available, otherwise a deterministic summary.

Usage:
  python subagents/note_summarizer.py
  python subagents/note_summarizer.py --tag work
  python subagents/note_summarizer.py --offline
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_llm  # noqa: E402
from agent_cli import run_and_print  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from example_core import Note, search_notes, summarize_offline  # noqa: E402
from memory.memory import NoteStore  # noqa: E402

SUBAGENT_NAME = "note_summarizer"
MAX_NOTES_FOR_LLM = 50

SYSTEM_PROMPT = (
    "You summarize a user's personal notes. Write 2-4 sentences: the main themes, "
    "anything that looks like an open action item, and nothing that is not in the notes."
)


def summarize(store: NoteStore, *, tag: Optional[str], offline: bool) -> Dict[str, Any]:
    notes = search_notes(store.all(), tag=tag, limit=MAX_NOTES_FOR_LLM)
    use_llm = bool(notes) and not offline and agent_llm.llm_available()
    summary = _llm_summary(notes) if use_llm else summarize_offline(notes)
    return {"summary": summary, "note_count": len(notes), "tag": tag, "used_llm": use_llm}


def _llm_summary(notes: Sequence[Note]) -> str:
    lines = [f"- {n.title} [{', '.join(n.tags)}]: {n.body}" for n in notes]
    return agent_llm.generate_text("Notes:\n" + "\n".join(lines), system=SYSTEM_PROMPT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize notes (subagent)")
    parser.add_argument("--tag", help="Only summarize notes with this tag")
    parser.add_argument("--offline", action="store_true", help="Skip the LLM")
    args = parser.parse_args()

    load_agent_environment()
    run_and_print(
        lambda: summarize(NoteStore(), tag=args.tag, offline=args.offline),
        subagent=SUBAGENT_NAME,
    )


if __name__ == "__main__":
    main()

"""Use cases shared by every interface (CLI, tools, API, UI, chat).

Each function takes a NoteStore and returns plain dicts, so callers can
serialize results directly to JSON, templates, or LLM tool responses.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional, Union

from agent_env import AGENT_DIR
from example_core import Note, search_notes, tag_counts
from memory.memory import DATA_DIR_ENV, NoteStore

SUBAGENTS_DIR = AGENT_DIR / "subagents"
SUBAGENT_TIMEOUT_SECONDS = 90


class SubagentError(RuntimeError):
    """A subagent exited with an error or returned malformed output."""


def add_note(
    store: NoteStore,
    title: str,
    body: str = "",
    tags: Union[str, Iterable[str], None] = None,
) -> Dict[str, Any]:
    return store.add(Note.create(title, body, tags)).to_dict()


def get_note(store: NoteStore, note_id: str) -> Dict[str, Any]:
    return store.get(note_id).to_dict()


def delete_note(store: NoteStore, note_id: str) -> Dict[str, Any]:
    return store.delete(note_id).to_dict()


def find_notes(
    store: NoteStore,
    query: str = "",
    *,
    tag: Optional[str] = None,
    limit: Optional[int] = 20,
) -> List[Dict[str, Any]]:
    return [n.to_dict() for n in search_notes(store.all(), query, tag=tag, limit=limit)]


def overview(store: NoteStore, *, recent: int = 5) -> Dict[str, Any]:
    """Compact snapshot used by dashboards and the LLM system prompt."""
    notes = store.all()
    return {
        "total": len(notes),
        "tags": tag_counts(notes),
        "recent": [n.to_dict() for n in search_notes(notes, limit=recent)],
    }


def summarize_notes(
    store: NoteStore,
    *,
    tag: Optional[str] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """Delegate summarization to the note_summarizer subagent."""
    args = ["--tag", tag] if tag else []
    if offline:
        args.append("--offline")
    return run_subagent("note_summarizer", args, store=store)


def run_subagent(name: str, args: List[str], *, store: NoteStore) -> Dict[str, Any]:
    """Run subagents/<name>.py as a separate process and return its `data` payload.

    Subagents are independent CLIs; the only contract is the JSON envelope on stdout.
    The store's data dir is passed through so both processes see the same memory.
    """
    script = SUBAGENTS_DIR / f"{name}.py"
    if not script.is_file():
        raise SubagentError(f"Unknown subagent: {name}")

    env = {**os.environ, DATA_DIR_ENV: str(store.data_dir)}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=SUBAGENT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise SubagentError(f"{name} timed out after {SUBAGENT_TIMEOUT_SECONDS}s") from exc
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SubagentError(f"{name} returned invalid JSON: {proc.stderr.strip()}") from exc
    if payload.get("status") != "success":
        raise SubagentError(payload.get("error") or f"{name} failed")
    return payload["data"]

"""Use cases shared by every interface (CLI, API, chat).

Every function takes the store and the acting user first. The user always
comes from the caller's session (an API token, or the local CLI user), never
from a model's tool arguments, so a model cannot act as someone else.

Deleting from the agent is two steps: `request_delete` records what would be
deleted, and only `approve_action`, called by a person, runs it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Union

from agent_env import AGENT_DIR
from example_core import (
    ActionStateError,
    Note,
    PendingAction,
    parse_note_ids,
    search_notes,
    tag_counts,
    validate_query,
)
from memory.memory import DATA_DIR_ENV, ActionStore, NoteStore

SUBAGENTS_DIR = AGENT_DIR / "subagents"
SUBAGENT_TIMEOUT_SECONDS = 90
ACTION_TTL_ENV = "SECURE_AGENT_ACTION_TTL_SECONDS"
DEFAULT_ACTION_TTL_SECONDS = 15 * 60
MAX_RESULTS = 20


class SubagentError(RuntimeError):
    """A subagent exited with an error or returned malformed output."""


def action_ttl_seconds() -> int:
    return int(os.environ.get(ACTION_TTL_ENV, DEFAULT_ACTION_TTL_SECONDS))


def add_note(
    store: NoteStore,
    user: str,
    title: str,
    body: str = "",
    tags: Union[str, Iterable[str], None] = None,
) -> Dict[str, Any]:
    return store.add(Note.create(user, title, body, tags)).public()


def get_note(store: NoteStore, user: str, note_id: str) -> Dict[str, Any]:
    return store.get(user, note_id).public()


def delete_note(store: NoteStore, user: str, note_id: str) -> Dict[str, Any]:
    """A person deleting their own note directly (API). The agent cannot reach this."""
    return store.delete(user, note_id).public()


def find_notes(
    store: NoteStore,
    user: str,
    query: str = "",
    *,
    tag: Optional[str] = None,
    limit: Optional[int] = MAX_RESULTS,
) -> List[Dict[str, Any]]:
    limit = min(limit or MAX_RESULTS, MAX_RESULTS)
    return [n.public() for n in search_notes(store.all(user), validate_query(query), tag=tag, limit=limit)]


def overview(store: NoteStore, user: str, *, recent: int = 5) -> Dict[str, Any]:
    notes = store.all(user)
    return {
        "total": len(notes),
        "tags": tag_counts(notes),
        "recent": [n.public() for n in search_notes(notes, limit=recent)],
    }


# --------------------------------------------------------------------------- #
# Pending actions
# --------------------------------------------------------------------------- #


def request_delete(store: NoteStore, user: str, note_ids: Union[str, List[str]]) -> Dict[str, Any]:
    """Record a deletion for the user to approve. Deletes nothing."""
    ids = parse_note_ids(note_ids)
    notes = [store.get(user, note_id) for note_id in ids]  # NotFoundError for another user's id
    action = PendingAction.propose_delete(user, notes, ttl_seconds=action_ttl_seconds())
    ActionStore(store.data_dir).add(action)
    return action.public()


def list_actions(store: NoteStore, user: str, *, status: Optional[str] = "pending") -> List[Dict[str, Any]]:
    actions = ActionStore(store.data_dir).all(user)
    return [a.public() for a in actions if status is None or a.status == status]


def get_action(store: NoteStore, user: str, action_id: str) -> Dict[str, Any]:
    return ActionStore(store.data_dir).get(user, action_id).public()


def approve_action(store: NoteStore, user: str, action_id: str, digest: str) -> Dict[str, Any]:
    """Run a pending action once, if it is the user's, unexpired, and unchanged since it was shown."""
    actions = ActionStore(store.data_dir)
    now = datetime.now(timezone.utc)
    deleted: List[Note] = []
    expired: List[bool] = []

    def run(action: PendingAction) -> str:
        try:
            action.check_approvable(digest, now)
        except ActionStateError:
            if action.status == "pending" and action.is_expired(now):
                expired.append(True)
            raise
        ids = [n["id"] for n in action.payload["notes"]]
        deleted.extend(store.delete_many(user, ids))
        return "done"

    try:
        action = actions.decide(user, action_id, run, now=now.isoformat(timespec="seconds"))
    except ActionStateError:
        if expired:
            actions.mark_expired(user, action_id, now=now.isoformat(timespec="seconds"))
        raise
    return {**action.public(), "deleted": [n.public() for n in deleted]}


def reject_action(store: NoteStore, user: str, action_id: str) -> Dict[str, Any]:
    def run(action: PendingAction) -> str:
        if action.status != "pending":
            raise ActionStateError(f"Action is already {action.status}.")
        return "rejected"

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return ActionStore(store.data_dir).decide(user, action_id, run, now=now).public()


# --------------------------------------------------------------------------- #
# Subagent
# --------------------------------------------------------------------------- #


def summarize_notes(
    store: NoteStore,
    user: str,
    *,
    tag: Optional[str] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """Delegate summarization to the note_summarizer subagent, for this user's notes only."""
    args = ["--user", user]
    if tag:
        args += ["--tag", tag]
    if offline:
        args.append("--offline")
    return run_subagent("note_summarizer", args, store=store)


def run_subagent(name: str, args: List[str], *, store: NoteStore) -> Dict[str, Any]:
    """Run subagents/<name>.py as a separate process and return its `data` payload."""
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

"""
Memory — JSON file stores for notes, pending actions, daily usage and API users.

Storage location: memory/data/, or $SECURE_AGENT_DATA_DIR if set.

Every read-modify-write holds an exclusive file lock, so two processes (or two
requests) approving the same action at the same moment cannot both run it.
Every read and write of user data takes the owner, so a store method cannot
return another user's record by mistake.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from example_core import Note, NotFoundError, PendingAction, validate_user_id

DATA_DIR_ENV = "SECURE_AGENT_DATA_DIR"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


def default_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else DEFAULT_DATA_DIR


class JsonFile:
    """One JSON document on disk with locked, atomic read-modify-write."""

    def __init__(self, data_dir: Path, name: str, empty: Any) -> None:
        self.path = data_dir / name
        # One lock per file. Approving holds the actions lock while it deletes
        # notes; a shared lock file would deadlock against itself there.
        self._lock_path = data_dir / f".{name}.lock"
        self._empty = empty

    def read(self) -> Any:
        if not self.path.exists():
            return json.loads(json.dumps(self._empty))
        return json.loads(self.path.read_text(encoding="utf-8"))

    @contextlib.contextmanager
    def locked(self) -> Iterator[None]:
        with open(self._lock_path, "a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def update(self, change: Callable[[Any], Any]) -> Any:
        """Apply `change` to the current content under the lock; write what it returns."""
        with self.locked():
            data = self.read()
            result = change(data)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
            return result


class NoteStore:
    """Notes of every user in one file; every method is scoped to one owner."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._file = JsonFile(self.data_dir, "notes.json", [])

    @property
    def path(self) -> Path:
        return self._file.path

    def all(self, owner: str) -> List[Note]:
        return [Note.from_dict(row) for row in self._file.read() if row.get("owner") == owner]

    def get(self, owner: str, note_id: str) -> Note:
        for note in self.all(owner):
            if note.id == note_id:
                return note
        # Same answer whether the note is missing or belongs to someone else:
        # a different error would tell an attacker which ids exist.
        raise NotFoundError(f"Note not found: {note_id}")

    def add(self, note: Note) -> Note:
        self._file.update(lambda rows: rows.append(note.to_dict()))
        return note

    def delete(self, owner: str, note_id: str) -> Note:
        def remove(rows: List[Dict[str, Any]]) -> Note:
            for i, row in enumerate(rows):
                if row["id"] == note_id and row.get("owner") == owner:
                    return Note.from_dict(rows.pop(i))
            raise NotFoundError(f"Note not found: {note_id}")

        return self._file.update(remove)

    def delete_many(self, owner: str, note_ids: List[str]) -> List[Note]:
        """Delete the owner's notes among `note_ids` in one locked write; missing ids are skipped."""
        wanted = set(note_ids)

        def remove(rows: List[Dict[str, Any]]) -> List[Note]:
            gone = [Note.from_dict(r) for r in rows if r["id"] in wanted and r.get("owner") == owner]
            rows[:] = [r for r in rows if not (r["id"] in wanted and r.get("owner") == owner)]
            return gone

        return self._file.update(remove)


class ActionStore:
    """Pending actions. The only way an action runs is `decide`, which is atomic."""

    def __init__(self, data_dir: Path) -> None:
        self._file = JsonFile(Path(data_dir), "actions.json", [])

    def add(self, action: PendingAction) -> PendingAction:
        self._file.update(lambda rows: rows.append(action.to_dict()))
        return action

    def all(self, owner: str) -> List[PendingAction]:
        return [PendingAction.from_dict(r) for r in self._file.read() if r["owner"] == owner]

    def get(self, owner: str, action_id: str) -> PendingAction:
        for action in self.all(owner):
            if action.id == action_id:
                return action
        raise NotFoundError(f"Action not found: {action_id}")

    def decide(self, owner: str, action_id: str, decide: Callable[[PendingAction], str], *, now: str) -> PendingAction:
        """Under the lock: load the owner's action, let `decide` run it and return the new status, save.

        `decide` raises to leave the action unchanged. Because the status check
        and the change happen under one lock, a second approval arriving at the
        same moment sees `done` and raises instead of running the action again.
        """

        def change(rows: List[Dict[str, Any]]) -> PendingAction:
            for row in rows:
                if row["id"] == action_id and row["owner"] == owner:
                    new_status = decide(PendingAction.from_dict(row))
                    row["status"] = new_status
                    row["decided_at"] = now
                    return PendingAction.from_dict(row)
            raise NotFoundError(f"Action not found: {action_id}")

        return self._file.update(change)

    def mark_expired(self, owner: str, action_id: str, *, now: str) -> None:
        def change(rows: List[Dict[str, Any]]) -> None:
            for row in rows:
                if row["id"] == action_id and row["owner"] == owner and row["status"] == "pending":
                    row["status"] = "expired"
                    row["decided_at"] = now

        self._file.update(change)


class UsageStore:
    """Per-user daily counters for model turns."""

    def __init__(self, data_dir: Path) -> None:
        self._file = JsonFile(Path(data_dir), "usage.json", {})

    def consume(self, owner: str, day: str, limit: int) -> bool:
        """Count one unit for owner on day. False, without counting, once the limit is reached."""

        def change(data: Dict[str, Dict[str, int]]) -> bool:
            today = data.setdefault(day, {})
            if today.get(owner, 0) >= limit:
                return False
            today[owner] = today.get(owner, 0) + 1
            for old in [d for d in data if d != day]:  # keep only today's counters
                del data[old]
            return True

        return self._file.update(change)

    def used(self, owner: str, day: str) -> int:
        return self._file.read().get(day, {}).get(owner, 0)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UserStore:
    """API users. Only a hash of each token is stored; the token is shown once, at creation."""

    def __init__(self, data_dir: Path) -> None:
        self._file = JsonFile(Path(data_dir), "users.json", {})

    def add(self, user_id: str) -> str:
        validate_user_id(user_id)
        token = secrets.token_urlsafe(32)

        def change(users: Dict[str, str]) -> None:
            if user_id in users:
                raise ValueError(f"User exists: {user_id}")
            users[user_id] = _token_hash(token)

        self._file.update(change)
        return token

    def authenticate(self, token: Optional[str]) -> Optional[str]:
        """The user id for this token, or None. Compares in constant time."""
        if not token:
            return None
        presented = _token_hash(token)
        for user_id, stored in self._file.read().items():
            if hmac.compare_digest(stored, presented):
                return user_id
        return None

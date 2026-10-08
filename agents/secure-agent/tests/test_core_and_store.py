"""Pure core and file stores: validation limits, owner scoping, digests and locked updates."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from example_core import (
    MAX_BODY_LENGTH,
    MAX_NOTES_PER_DELETE,
    ActionStateError,
    Note,
    NotFoundError,
    PendingAction,
    extract_hashtags,
    normalize_tags,
    parse_note_ids,
    search_notes,
    summarize_offline,
    validate_query,
    validate_user_id,
)
from memory.memory import NoteStore, UsageStore, UserStore


class TestNote:
    def test_create_normalizes_and_records_owner(self):
        note = Note.create("alice", "  Call Bob ", tags="Work, #ideas")
        assert (note.owner, note.title, note.tags) == ("alice", "Call Bob", ("work", "ideas"))
        assert "owner" not in note.public()

    @pytest.mark.parametrize("kwargs, message", [
        ({"title": ""}, "title is required"),
        ({"title": "x" * 121}, "at most 120"),
        ({"title": "ok", "body": "x" * (MAX_BODY_LENGTH + 1)}, "body must be at most"),
        ({"title": "ok", "tags": [f"t{i}" for i in range(11)]}, "at most 10 tags"),
    ])
    def test_limits(self, kwargs, message):
        with pytest.raises(ValueError, match=message):
            Note.create("alice", **kwargs)

    @pytest.mark.parametrize("user", ["", "A", "x", "alice; drop", "../bob", "a" * 40])
    def test_user_ids_are_validated(self, user):
        with pytest.raises(ValueError):
            validate_user_id(user)


class TestInputs:
    def test_parse_note_ids(self):
        assert parse_note_ids("note_abc123, note_abc123 ,note_def456") == ["note_abc123", "note_def456"]

    @pytest.mark.parametrize("raw", ["", "note_x; rm -rf /", "../notes.json", ",".join(f"note_{i:06d}" for i in range(MAX_NOTES_PER_DELETE + 1))])
    def test_parse_note_ids_rejects(self, raw):
        with pytest.raises(ValueError):
            parse_note_ids(raw)

    def test_query_length(self):
        with pytest.raises(ValueError):
            validate_query("x" * 201)

    def test_tags_search_and_summary_still_work(self):
        assert normalize_tags(["A b", "#c"]) == ("a-b", "c")
        assert extract_hashtags("Buy milk #shopping") == ("Buy milk", ("shopping",))
        notes = [Note.create("alice", "Buy milk", tags="home"), Note.create("alice", "Call Bob")]
        assert [n.title for n in search_notes(notes, "milk")] == ["Buy milk"]
        assert "2 note(s)." in summarize_offline(notes)


class TestPendingAction:
    def _action(self, now):
        note = Note.create("alice", "Old receipt")
        return PendingAction.propose_delete("alice", [note], ttl_seconds=60, now=now)

    def test_preview_and_digest_bind_the_content(self):
        now = datetime.now(timezone.utc)
        action = self._action(now)
        assert action.preview == "Delete 1 note(s): 'Old receipt'"
        assert action.status == "pending"
        action.check_approvable(action.digest, now)  # no raise

    @pytest.mark.parametrize("change, message", [
        (lambda a, now: (a, a.digest, now + timedelta(seconds=61)), "expired"),
        (lambda a, now: (a, "0" * 16, now), "changed"),
        (lambda a, now: (PendingAction(**{**a.to_dict(), "status": "done"}), a.digest, now), "already done"),
    ])
    def test_not_approvable(self, change, message):
        now = datetime.now(timezone.utc)
        action, digest, when = change(self._action(now), now)
        with pytest.raises(ActionStateError, match=message):
            action.check_approvable(digest, when)

    def test_cannot_propose_for_another_owner(self):
        with pytest.raises(NotFoundError):
            PendingAction.propose_delete("bob", [Note.create("alice", "x")], ttl_seconds=60)


class TestStores:
    def test_notes_are_scoped_to_their_owner(self, store: NoteStore):
        mine = store.add(Note.create("alice", "Mine"))
        store.add(Note.create("bob", "Bob's"))
        assert [n.title for n in store.all("alice")] == ["Mine"]
        with pytest.raises(NotFoundError):
            store.get("bob", mine.id)
        with pytest.raises(NotFoundError):
            store.delete("bob", mine.id)
        assert store.delete_many("bob", [mine.id]) == []
        assert store.get("alice", mine.id).title == "Mine"

    def test_rows_without_owner_are_invisible(self, store: NoteStore):
        # Data copied from example-agent has no owner; nobody may read it as theirs.
        store.path.write_text(json.dumps([{"id": "note_legacy01", "title": "Old", "created_at": "2026-01-01"}]))
        assert store.all("alice") == []

    def test_daily_usage_counter(self, store: NoteStore):
        usage = UsageStore(store.data_dir)
        assert [usage.consume("alice", "2026-10-07", 2) for _ in range(3)] == [True, True, False]
        assert usage.consume("bob", "2026-10-07", 2) is True
        assert usage.consume("alice", "2026-10-08", 2) is True  # a new day starts again
        assert usage.used("alice", "2026-10-07") == 0  # old days are dropped

    def test_tokens_are_stored_hashed(self, store: NoteStore):
        users = UserStore(store.data_dir)
        token = users.add("alice")
        assert users.authenticate(token) == "alice"
        assert users.authenticate(token + "x") is None
        assert users.authenticate(None) is None
        assert token not in (store.data_dir / "users.json").read_text()
        with pytest.raises(ValueError, match="exists"):
            users.add("alice")

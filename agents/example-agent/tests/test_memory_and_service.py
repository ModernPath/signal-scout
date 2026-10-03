from __future__ import annotations

import json

import pytest

import example_service as service
from example_core import Note, NotFoundError
from memory.memory import NoteStore


class TestNoteStore:
    def test_empty_store(self, store: NoteStore):
        assert store.all() == []
        assert not store.path.exists()

    def test_add_get_delete(self, store: NoteStore):
        note = store.add(Note.create("Call Bob"))
        assert store.get(note.id) == note
        assert store.delete(note.id) == note
        assert store.all() == []

    def test_missing_note_raises(self, store: NoteStore):
        with pytest.raises(NotFoundError):
            store.get("note_missing")
        with pytest.raises(NotFoundError):
            store.delete("note_missing")

    def test_persists_as_json_without_temp_file(self, store: NoteStore):
        store.add(Note.create("A", tags="x"))
        rows = json.loads(store.path.read_text())
        assert rows[0]["title"] == "A" and rows[0]["tags"] == ["x"]
        assert not store.path.with_suffix(".tmp").exists()

    def test_default_dir_comes_from_env(self, isolated_env):
        assert NoteStore().data_dir == isolated_env


class TestService:
    def test_add_and_find(self, store: NoteStore):
        service.add_note(store, "Buy milk", tags="home")
        service.add_note(store, "Call Bob", tags="work")
        assert [n["title"] for n in service.find_notes(store, "milk")] == ["Buy milk"]
        assert [n["title"] for n in service.find_notes(store, tag="work")] == ["Call Bob"]

    def test_overview(self, store: NoteStore):
        service.add_note(store, "A", tags="x")
        snapshot = service.overview(store)
        assert snapshot["total"] == 1
        assert snapshot["tags"] == {"x": 1}
        assert snapshot["recent"][0]["title"] == "A"

    def test_summarize_delegates_to_subagent(self, store: NoteStore):
        service.add_note(store, "Call Bob", tags="work")
        service.add_note(store, "Buy milk", tags="home")
        result = service.summarize_notes(store, tag="work")
        assert result["note_count"] == 1
        assert result["used_llm"] is False
        assert "Call Bob" in result["summary"]

    def test_unknown_subagent(self, store: NoteStore):
        with pytest.raises(service.SubagentError, match="Unknown subagent"):
            service.run_subagent("nope", [], store=store)

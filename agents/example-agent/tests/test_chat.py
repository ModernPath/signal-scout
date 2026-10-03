from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

import agent_llm
import example_chat
import example_service as service
from example_chat import OFFLINE_HELP, build_tools, chat_reply
from memory.memory import NoteStore


class TestOfflineRouter:
    def test_add_with_hashtags(self, store: NoteStore):
        result = chat_reply(store, "add Buy oat milk #shopping")
        assert result.reply.startswith("Saved - Buy oat milk (#shopping)")
        assert result.tools_used == ["add_note"]
        assert result.used_llm is False
        assert store.all()[0].tags == ("shopping",)

    def test_find_and_list(self, store: NoteStore):
        service.add_note(store, "Buy milk")
        service.add_note(store, "Call Bob")
        assert "Buy milk" in chat_reply(store, "find milk").reply
        assert "Call Bob" not in chat_reply(store, "find milk").reply
        assert "Call Bob" in chat_reply(store, "list notes").reply
        assert "No notes match" in chat_reply(store, "search zebra").reply

    def test_delete(self, store: NoteStore):
        note = service.add_note(store, "Temp")
        assert chat_reply(store, f"delete {note['id']}").reply == "Deleted 'Temp'."
        assert "Sorry" in chat_reply(store, "delete note_missing").reply

    def test_summarize(self, store: NoteStore):
        service.add_note(store, "Call Bob", tags="work")
        assert "#work (1)" in chat_reply(store, "summarize").reply

    def test_unknown_command_shows_help(self, store: NoteStore):
        result = chat_reply(store, "hello there")
        assert result.reply == OFFLINE_HELP
        assert result.tools_used == []

    def test_empty_message(self, store: NoteStore):
        assert chat_reply(store, "   ").reply == "Please enter a message."

    def test_history_is_appended_and_capped(self, store: NoteStore, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(example_chat, "MAX_HISTORY_TURNS", 2)
        history = []
        for i in range(3):
            history = chat_reply(store, f"hello {i}", history=history).history
        assert len(history) == 4
        assert history[-2] == {"role": "user", "content": "hello 2"}


class TestTools:
    def test_tools_call_service_and_record_usage(self, store: NoteStore):
        used = []
        tools = {fn.__name__: fn for fn in build_tools(store, used)}
        note = tools["add_note"](title="Call Bob", tags="work")
        assert tools["search_notes"](tag="work")["notes"][0]["id"] == note["id"]
        assert tools["delete_note"](note_id=note["id"])["title"] == "Call Bob"
        assert used == ["add_note", "search_notes", "delete_note"]

    def test_tool_annotations_are_real_types(self, store: NoteStore):
        # google-genai calls isinstance(arg, annotation); string annotations break every tool call.
        for fn in build_tools(store, []):
            for param in inspect.signature(fn).parameters.values():
                assert isinstance(param.annotation, type), f"{fn.__name__}.{param.name}"

    def test_tool_errors_are_returned_not_raised(self, store: NoteStore):
        tools = {fn.__name__: fn for fn in build_tools(store, [])}
        assert "error" in tools["delete_note"](note_id="note_missing")
        assert "error" in tools["add_note"](title="")

    def test_system_prompt_includes_state_and_skills(self, store: NoteStore):
        service.add_note(store, "A", tags="work")
        prompt = example_chat.build_system_prompt(store)
        assert "1 note(s)" in prompt and "#work" in prompt
        assert "name: note-search" in prompt


class FakeChat:
    """Mimics a Gemini chat that calls one tool, then answers."""

    def __init__(self, config, history):
        self.config = config
        self.history = history

    def send_message(self, text):
        tools = {fn.__name__: fn for fn in self.config.tools}
        found = tools["search_notes"](query=text)
        return SimpleNamespace(text=f"Found {len(found['notes'])} note(s).")


class TestLlmMode:
    @pytest.fixture
    def fake_llm(self, monkeypatch: pytest.MonkeyPatch):
        created = []

        def create(model, config, history):
            created.append(FakeChat(config, history))
            return created[-1]

        client = SimpleNamespace(chats=SimpleNamespace(create=create))
        monkeypatch.setattr(agent_llm, "llm_available", lambda: True)
        monkeypatch.setattr(agent_llm, "get_client", lambda: client)
        return created

    def test_llm_reply_uses_tools(self, store: NoteStore, fake_llm):
        service.add_note(store, "milk")
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        result = chat_reply(store, "milk", history=history)
        assert result.used_llm is True
        assert result.reply == "Found 1 note(s)."
        assert result.tools_used == ["search_notes"]
        assert [c.role for c in fake_llm[0].history] == ["user", "model"]

    def test_offline_flag_skips_llm(self, store: NoteStore, fake_llm):
        result = chat_reply(store, "list notes", offline=True)
        assert result.used_llm is False
        assert fake_llm == []

    def test_llm_failure_falls_back_to_offline(self, store: NoteStore, monkeypatch: pytest.MonkeyPatch):
        def boom():
            raise RuntimeError("network down")

        monkeypatch.setattr(agent_llm, "llm_available", lambda: True)
        monkeypatch.setattr(agent_llm, "get_client", boom)
        result = chat_reply(store, "list notes")
        assert result.used_llm is False
        assert result.reply.startswith("No notes yet")

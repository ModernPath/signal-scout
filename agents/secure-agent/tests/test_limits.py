"""Step 3: limits on consumption, enforced in code whatever the model asks for."""

from __future__ import annotations

import time

import pytest

import agent_llm
import example_chat
from conftest import ALICE, BOB
from example_chat import LIMIT_REPLY, Budget, chat_reply
from memory.memory import NoteStore


def test_daily_model_turn_cap_per_user(store: NoteStore, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(example_chat.DAILY_TURNS_ENV, "2")
    calls = []

    def model(system, history, text, tools):
        calls.append(text)
        return "ok"

    replies = [chat_reply(store, ALICE, f"hi {i}", model=model) for i in range(3)]

    assert calls == ["hi 0", "hi 1"]  # the third turn never reached the model
    assert replies[2].reply == LIMIT_REPLY and replies[2].limited
    assert chat_reply(store, BOB, "hi", model=model).reply == "ok"  # one user's cap is not another's


def test_offline_commands_do_not_count_against_the_cap(store: NoteStore, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(example_chat.DAILY_TURNS_ENV, "1")
    for _ in range(3):
        assert "No notes yet" in chat_reply(store, ALICE, "list notes", offline=True).reply


def test_turn_deadline_refuses_further_tool_calls():
    budget = Budget(calls=5, seconds=0.01)
    assert budget.spend() is None
    time.sleep(0.02)
    assert "Time limit" in budget.spend()


def test_model_requests_have_a_timeout(monkeypatch: pytest.MonkeyPatch):
    from google import genai

    seen = {}
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(genai, "Client", lambda **kwargs: seen.update(kwargs) or object())
    agent_llm.get_client()
    assert seen["http_options"].timeout == agent_llm.REQUEST_TIMEOUT_MS

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app, get_store
from memory.memory import NoteStore


@pytest.fixture
def client(store: NoteStore):
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}


def test_note_crud(client: TestClient):
    created = client.post("/notes", json={"title": "Call Bob", "tags": ["Work"]})
    assert created.status_code == 201
    note = created.json()
    assert note["tags"] == ["work"]

    assert client.get(f"/notes/{note['id']}").json() == note
    assert client.get("/notes", params={"q": "bob"}).json() == [note]
    assert client.get("/notes", params={"tag": "home"}).json() == []

    assert client.delete(f"/notes/{note['id']}").status_code == 200
    assert client.get(f"/notes/{note['id']}").status_code == 404


def test_validation_errors(client: TestClient):
    assert client.post("/notes", json={"title": ""}).status_code == 422
    assert client.post("/notes", json={"title": "   "}).status_code == 400
    assert client.delete("/notes/note_missing").status_code == 404


def test_overview_and_summary(client: TestClient):
    client.post("/notes", json={"title": "Call Bob", "tags": ["work"]})
    assert client.get("/overview").json()["total"] == 1
    summary = client.post("/summary", json={"tag": "work"}).json()
    assert summary["note_count"] == 1 and "Call Bob" in summary["summary"]


def test_chat_round_trip(client: TestClient):
    first = client.post("/chat", json={"message": "add Buy milk #home"}).json()
    assert first["tools_used"] == ["add_note"]
    assert first["used_llm"] is False

    second = client.post("/chat", json={"message": "find milk", "history": first["history"]}).json()
    assert "Buy milk" in second["reply"]
    assert len(second["history"]) == 4


def test_chat_requires_message(client: TestClient):
    assert client.post("/chat", json={"message": ""}).status_code == 422

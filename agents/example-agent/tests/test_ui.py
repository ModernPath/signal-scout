from __future__ import annotations

import pytest

from memory.memory import NoteStore
from ui.app import create_app


@pytest.fixture
def client(store: NoteStore):
    app = create_app(store)
    app.config["TESTING"] = True
    return app.test_client()


def test_empty_dashboard(client):
    page = client.get("/").get_data(as_text=True)
    assert "No notes yet" in page
    assert "offline" in page


def test_create_search_and_delete(client, store: NoteStore):
    page = client.post(
        "/notes", data={"title": "Call Bob", "body": "offer", "tags": "work"}, follow_redirects=True
    ).get_data(as_text=True)
    assert "Saved “Call Bob”." in page
    assert "#work · 1" in page

    assert "Call Bob" in client.get("/?q=bob").get_data(as_text=True)
    assert "No notes match" in client.get("/?q=zebra").get_data(as_text=True)
    assert "Call Bob" in client.get("/?tag=work").get_data(as_text=True)

    note_id = store.all()[0].id
    page = client.post(f"/notes/{note_id}/delete", follow_redirects=True).get_data(as_text=True)
    assert "Deleted “Call Bob”." in page
    assert store.all() == []


def test_create_shows_validation_error(client):
    page = client.post("/notes", data={"title": "  "}, follow_redirects=True).get_data(as_text=True)
    assert "Note title is required." in page


def test_delete_missing_shows_error(client):
    page = client.post("/notes/note_missing/delete", follow_redirects=True).get_data(as_text=True)
    assert "Note not found" in page


def test_summary(client):
    client.post("/notes", data={"title": "Call Bob", "tags": "work"})
    page = client.post("/summary", data={"tag": "work"}, follow_redirects=True).get_data(as_text=True)
    assert "1 note(s)." in page


def test_chat_api(client):
    assert client.get("/chat").status_code == 200
    response = client.post("/api/chat", json={"message": "add Buy milk #home"})
    assert response.status_code == 200
    assert response.get_json()["tools_used"] == ["add_note"]
    assert client.post("/api/chat", json={"message": " "}).status_code == 400

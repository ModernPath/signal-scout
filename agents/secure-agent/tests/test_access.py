"""Step 2: access control. Anonymous is refused, own data is allowed, another user's data is refused.

Every route and every agent tool gets all three. The refusing tests are the
point of this file; docs/learning-log.md records that they fail when the
ownership check in memory/memory.py is removed.
"""

from __future__ import annotations

from typing import Dict

import pytest

import example_service as service
from conftest import ALICE, BOB, auth
from example_chat import build_tools, chat_reply, ChatResult
from memory.memory import NoteStore


@pytest.fixture
def bobs_note(store: NoteStore, tokens) -> Dict:
    return service.add_note(store, BOB, "Bob's salary negotiation", "Asking for 7 000 €")


@pytest.fixture
def bobs_action(store: NoteStore, bobs_note) -> Dict:
    return service.request_delete(store, BOB, bobs_note["id"])


ROUTES = [
    ("get", "/notes", None),
    ("post", "/notes", {"title": "x"}),
    ("get", "/notes/note_abc12345", None),
    ("delete", "/notes/note_abc12345", None),
    ("get", "/overview", None),
    ("post", "/summary", {"offline": True}),
    ("post", "/chat", {"message": "list notes", "offline": True}),
    ("get", "/actions", None),
    ("get", "/actions/act_000000000000", None),
    ("post", "/actions/act_000000000000/approve", {"digest": "x"}),
    ("post", "/actions/act_000000000000/reject", None),
]


class TestAnonymous:
    @pytest.mark.parametrize("method, path, body", ROUTES)
    def test_every_data_route_needs_a_token(self, client, tokens, method, path, body):
        kwargs = {"json": body} if body is not None else {}
        assert getattr(client, method)(path, **kwargs).status_code == 401
        assert getattr(client, method)(path, headers=auth("not-a-token"), **kwargs).status_code == 401

    def test_health_is_public(self, client):
        assert client.get("/health").status_code == 200


class TestOwnData:
    def test_alice_reads_and_deletes_her_own_note(self, client, tokens):
        created = client.post("/notes", json={"title": "Mine"}, headers=auth(tokens[ALICE])).json()
        assert client.get(f"/notes/{created['id']}", headers=auth(tokens[ALICE])).json()["title"] == "Mine"
        assert client.delete(f"/notes/{created['id']}", headers=auth(tokens[ALICE])).status_code == 200


class TestCrossUserThroughTheApi:
    def test_cannot_read_other_users_note(self, client, tokens, bobs_note):
        r = client.get(f"/notes/{bobs_note['id']}", headers=auth(tokens[ALICE]))
        assert r.status_code == 404  # the same answer as a missing note: no hint that it exists

    def test_cannot_delete_other_users_note(self, client, store, tokens, bobs_note):
        assert client.delete(f"/notes/{bobs_note['id']}", headers=auth(tokens[ALICE])).status_code == 404
        assert service.get_note(store, BOB, bobs_note["id"])

    def test_lists_and_overview_show_only_own_notes(self, client, tokens, bobs_note):
        assert client.get("/notes", headers=auth(tokens[ALICE])).json() == []
        assert client.get("/overview", headers=auth(tokens[ALICE])).json()["total"] == 0
        summary = client.post("/summary", json={"offline": True}, headers=auth(tokens[ALICE])).json()
        assert summary["note_count"] == 0

    def test_cannot_see_approve_or_reject_other_users_action(self, client, store, tokens, bobs_action):
        a = auth(tokens[ALICE])
        assert client.get("/actions", headers=a).json() == []
        assert client.get(f"/actions/{bobs_action['id']}", headers=a).status_code == 404
        r = client.post(f"/actions/{bobs_action['id']}/approve", json={"digest": bobs_action["digest"]}, headers=a)
        assert r.status_code == 404
        assert client.post(f"/actions/{bobs_action['id']}/reject", headers=a).status_code == 404
        assert service.get_action(store, BOB, bobs_action["id"])["status"] == "pending"
        assert service.find_notes(store, BOB)  # Bob's note is still there


class TestCrossUserThroughTheAgent:
    def test_tools_have_no_user_parameter(self, store):
        # If a tool took a user id, the model could fill it with anyone's.
        import inspect

        for tool in build_tools(store, ALICE, ChatResult(reply="")):
            assert not {"user", "user_id", "owner"} & set(inspect.signature(tool).parameters)

    def test_agent_search_returns_only_own_notes(self, store, bobs_note):
        tools = {t.__name__: t for t in build_tools(store, ALICE, ChatResult(reply=""))}
        assert tools["search_notes"](query="salary")["notes_data"] == []

    def test_agent_cannot_request_deleting_other_users_note(self, store, bobs_note):
        result = ChatResult(reply="")
        tools = {t.__name__: t for t in build_tools(store, ALICE, result)}
        answer = tools["request_delete"](note_ids=bobs_note["id"])
        assert "not found" in answer["error"].lower()
        assert result.pending_actions == []
        assert service.list_actions(store, ALICE) == service.list_actions(store, BOB) == []

    def test_offline_router_is_scoped_too(self, store, bobs_note):
        reply = chat_reply(store, ALICE, f"delete {bobs_note['id']}").reply
        assert reply.startswith("Sorry: Note not found")
        assert "salary" not in chat_reply(store, ALICE, "list notes").reply.lower()

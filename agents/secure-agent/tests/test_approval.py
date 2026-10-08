"""Step 4: human approval for the agent's deletions.

The agent can only create a pending action. These tests prove the negative
paths: unapproved, rejected, expired, changed and other-user approvals leave
the notes untouched, and an approval sent twice, even at the same moment,
deletes once.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List

import pytest

import example_service as service
from conftest import ALICE, BOB, auth
from example_chat import chat_reply
from example_core import ActionStateError, NotFoundError
from memory.memory import NoteStore


@pytest.fixture
def proposed(store: NoteStore) -> Dict[str, Any]:
    keep = service.add_note(store, ALICE, "Passport renewal form")
    old = service.add_note(store, ALICE, "Old parking receipt")
    action = chat_reply(store, ALICE, f"delete {old['id']}", offline=True).pending_actions[0]
    return {"keep": keep, "old": old, "action": action}


def ids(store: NoteStore, user: str = ALICE) -> List[str]:
    return sorted(n["id"] for n in service.find_notes(store, user))


def test_the_agent_only_proposes(store, proposed):
    assert proposed["old"]["id"] in ids(store)
    assert proposed["action"]["preview"] == "Delete 1 note(s): 'Old parking receipt'"
    assert proposed["action"]["status"] == "pending"


def test_approval_deletes_exactly_what_was_shown(store, proposed):
    done = service.approve_action(store, ALICE, proposed["action"]["id"], proposed["action"]["digest"])
    assert done["status"] == "done"
    assert [n["id"] for n in done["deleted"]] == [proposed["old"]["id"]]
    assert ids(store) == [proposed["keep"]["id"]]


def test_rejected_action_never_runs(store, proposed):
    before = ids(store)
    service.reject_action(store, ALICE, proposed["action"]["id"])
    with pytest.raises(ActionStateError, match="rejected"):
        service.approve_action(store, ALICE, proposed["action"]["id"], proposed["action"]["digest"])
    assert ids(store) == before


def test_expired_action_never_runs(store, monkeypatch):
    monkeypatch.setenv(service.ACTION_TTL_ENV, "0")
    note = service.add_note(store, ALICE, "Old")
    action = service.request_delete(store, ALICE, note["id"])
    with pytest.raises(ActionStateError, match="expired"):
        service.approve_action(store, ALICE, action["id"], action["digest"])
    assert ids(store) == [note["id"]]
    assert service.get_action(store, ALICE, action["id"])["status"] == "expired"


def test_approval_must_quote_the_digest_it_was_shown(store, proposed):
    before = ids(store)
    with pytest.raises(ActionStateError, match="changed"):
        service.approve_action(store, ALICE, proposed["action"]["id"], "0123456789abcdef")
    assert ids(store) == before


def test_another_user_cannot_approve(store, proposed):
    before = ids(store)
    with pytest.raises(NotFoundError):
        service.approve_action(store, BOB, proposed["action"]["id"], proposed["action"]["digest"])
    assert ids(store) == before


def test_double_approval_runs_once(store, proposed):
    a = proposed["action"]
    service.approve_action(store, ALICE, a["id"], a["digest"])
    with pytest.raises(ActionStateError, match="already done"):
        service.approve_action(store, ALICE, a["id"], a["digest"])


def test_simultaneous_approvals_run_once(store, proposed, monkeypatch):
    # Slow the delete down so both approvals are in flight together. Without the
    # lock around check-and-change, both would see "pending" and both would run.
    real_delete_many = NoteStore.delete_many
    deletes = []

    def slow_delete_many(self, owner, note_ids):
        deletes.append(note_ids)
        threading.Event().wait(0.1)
        return real_delete_many(self, owner, note_ids)

    monkeypatch.setattr(NoteStore, "delete_many", slow_delete_many)
    a = proposed["action"]
    outcomes = []

    def approve():
        try:
            service.approve_action(store, ALICE, a["id"], a["digest"])
            outcomes.append("ran")
        except ActionStateError:
            outcomes.append("refused")

    threads = [threading.Thread(target=approve) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["ran", "refused"]
    assert len(deletes) == 1


def test_approval_through_the_api(client, store, tokens, proposed):
    a, headers = proposed["action"], auth(tokens[ALICE])
    pending = client.get("/actions", headers=headers).json()
    assert [p["id"] for p in pending] == [a["id"]]
    assert client.post(f"/actions/{a['id']}/approve", json={"digest": "wrong"}, headers=headers).status_code == 409
    assert client.post(f"/actions/{a['id']}/approve", json={"digest": a["digest"]}, headers=headers).status_code == 200
    assert client.post(f"/actions/{a['id']}/approve", json={"digest": a["digest"]}, headers=headers).status_code == 409
    assert ids(store) == [proposed["keep"]["id"]]


def test_chat_over_the_api_returns_the_pending_action(client, store, tokens):
    note = service.add_note(store, ALICE, "Old")
    r = client.post("/chat", json={"message": f"delete {note['id']}", "offline": True}, headers=auth(tokens[ALICE]))
    body = r.json()
    assert body["pending_actions"][0]["preview"] == "Delete 1 note(s): 'Old'"
    assert ids(store) == [note["id"]]

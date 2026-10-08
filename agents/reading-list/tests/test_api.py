from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import reading_list_service as service


@pytest.fixture
def client(store):
    from api.main import app, get_store

    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _unwrap(payload, key):
    return payload[key] if isinstance(payload, dict) else payload


def test_api_routes_match_service_state_and_error_mapping(client, store):
    assert client.get("/health").json() == {"status": "ok"}
    assert _unwrap(client.get("/items").json(), "items") == []

    created = client.post(
        "/items",
        json={"title": "One", "url": "https://e.com/1", "note": "n", "tags": ["Dev", "dev", "AI"]},
    )
    assert created.status_code == 201
    item = created.json()
    assert item["id"].startswith("item_") and item["tags"] == ["dev", "ai"]
    assert item["read_at"] is None and item["added_at"]
    assert service.get_item(store, item["id"]) == item
    assert client.get(f"/items/{item['id']}").json() == item

    two = client.post("/items", json={"title": "Two", "url": "http://e.com/2"}).json()

    listed = _unwrap(client.get("/items").json(), "items")
    assert {i["id"] for i in listed} == {item["id"], two["id"]}
    by_tag = _unwrap(client.get("/items", params={"tag": "ai"}).json(), "items")
    assert [i["id"] for i in by_tag] == [item["id"]]

    tagged = client.post(f"/items/{two['id']}/tags", json={"tags": ["DEV", "rust"]})
    assert tagged.status_code == 200 and tagged.json()["tags"] == ["dev", "rust"]
    assert service.get_item(store, two["id"])["tags"] == ["dev", "rust"]

    ranking = _unwrap(client.get("/rank").json(), "ranking")
    assert {r["id"] for r in ranking} == {item["id"], two["id"]}
    assert [r["rank"] for r in ranking] == [1, 2]
    assert all("tag_boost" in r and r["reason"] for r in ranking)

    read = client.post(f"/items/{item['id']}/read")
    assert read.status_code == 200 and read.json()["read_at"]
    assert client.post(f"/items/{item['id']}/read").json()["read_at"] == read.json()["read_at"]
    ranking = _unwrap(client.get("/rank").json(), "ranking")
    assert [r["id"] for r in ranking] == [two["id"]]

    summary = client.get("/summary").json()
    assert (summary["total"], summary["unread"], summary["read"]) == (2, 1, 1)
    assert summary["tags"]["dev"] == 2

    assert client.delete(f"/items/{item['id']}").status_code == 200
    assert client.get(f"/items/{item['id']}").status_code == 404
    assert [i.id for i in store.all()] == [two["id"]]

    # bad input -> 400, unknown id -> 404, and nothing is written
    assert client.post("/items", json={"title": "   ", "url": "https://e.com"}).status_code == 400
    assert client.post("/items", json={"title": "T", "url": "ftp://e.com"}).status_code == 400
    long_note = {"title": "T", "url": "https://e.com", "note": "x" * 501}
    assert client.post("/items", json=long_note).status_code in (400, 422)
    assert client.post("/items", json={"url": "https://e.com"}).status_code in (400, 422)
    assert client.post(f"/items/{two['id']}/tags", json={"tags": ["!!!"]}).status_code == 400
    for call in (
        lambda: client.get("/items/item_missing"),
        lambda: client.post("/items/item_missing/tags", json={"tags": ["a"]}),
        lambda: client.post("/items/item_missing/read"),
        lambda: client.delete("/items/item_missing"),
    ):
        assert call().status_code == 404
    assert len(store.all()) == 1


def test_api_empty_list_rank_summary_are_not_errors(client):
    assert client.get("/rank").status_code == 200
    summary = client.get("/summary")
    assert summary.status_code == 200 and summary.json()["total"] == 0


def test_api_chat_offline_shares_state(client, store):
    first = client.post("/chat", json={"message": "add Chat Item https://e.com/c #x"}).json()
    assert first["used_llm"] is False
    assert [i.title for i in store.all()] == ["Chat Item"]
    assert "Chat Item" in client.get("/items").text
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_api_binds_loopback_on_default_port():
    from pathlib import Path

    import api.main as main

    assert main.DEFAULT_PORT == 8013
    source = (Path(main.__file__)).read_text(encoding="utf-8")
    assert 'host="127.0.0.1"' in source
    assert "0.0.0.0" not in source
    assert "API_PORT" in source

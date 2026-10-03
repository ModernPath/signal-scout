import os

import pytest
from fastapi.testclient import TestClient

from signalscout.config import Settings
from signalscout.web import create_app


def test_root_serves_application_page_without_scope_prototype():
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))

    response = TestClient(app, base_url="http://localhost").get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SignalScout" in response.text
    assert "Phase 1 scope prototype" not in response.text
    assert "sample signals" not in response.text
    assert "runCollection(" not in response.text


def test_health_returns_safe_503_when_postgres_is_unavailable():
    app = create_app(Settings("postgresql+psycopg://scout:topsecret@127.0.0.1:1/signalscout"))

    response = TestClient(app, base_url="http://localhost").get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "topsecret" not in response.text


def test_cross_origin_mutation_is_rejected_before_future_api_routes():
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))

    response = TestClient(app, base_url="http://localhost").post(
        "/api/future-action",
        headers={"origin": "https://elsewhere.example"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin request forbidden"}


def test_mutation_without_origin_evidence_is_rejected():
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))

    response = TestClient(app, base_url="http://localhost").post("/api/future-action")

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin request forbidden"}


@pytest.mark.parametrize(
    "headers",
    [{"origin": "http://localhost"}, {"sec-fetch-site": "same-origin"}],
)
def test_same_origin_mutation_reaches_its_route(headers):
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))

    @app.post("/api/test-action")
    def test_action():
        return {"status": "accepted"}

    response = TestClient(app, base_url="http://localhost").post(
        "/api/test-action", headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


@pytest.mark.parametrize(
    ("method", "path", "headers"),
    [
        ("get", "/api/health", {}),
        ("post", "/api/future-action", {"origin": "http://attacker.example"}),
    ],
)
def test_untrusted_host_is_rejected_before_routing(method, path, headers):
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))
    client = TestClient(app, base_url="http://attacker.example")

    response = getattr(client, method)(path, headers=headers)

    assert response.status_code == 400


def test_unhandled_api_error_has_safe_json_response(caplog):
    app = create_app(Settings("postgresql+psycopg://scout:secret@localhost:5432/signalscout"))

    @app.get("/api/broken")
    def broken():
        raise RuntimeError("private provider detail")

    with caplog.at_level("ERROR", logger="signalscout.web"):
        response = TestClient(app, base_url="http://localhost", raise_server_exceptions=False).get(
            "/api/broken"
        )

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Internal server error"}
    assert "private provider detail" not in caplog.text


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="needs disposable PostgreSQL")
def test_health_queries_live_postgres_and_logs_readiness(caplog):
    app = create_app(Settings.from_env({"DATABASE_URL": os.environ["TEST_DATABASE_URL"]}))

    with caplog.at_level("INFO", logger="signalscout.web"):
        response = TestClient(app, base_url="http://localhost").get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "Web ready" in caplog.text

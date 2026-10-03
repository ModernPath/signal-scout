"""Monitoring profile behavior against disposable PostgreSQL."""

import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from signalscout.config import Settings
from signalscout.web import create_app


URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="needs disposable PostgreSQL")


@pytest.fixture
def client():
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": URL},
        check=True,
        capture_output=True,
    )
    with psycopg.connect(URL.replace("postgresql+psycopg://", "postgresql://")) as connection:
        if connection.execute("SELECT to_regclass('collection_run')").fetchone()[0]:
            connection.execute("TRUNCATE collection_run, source_config, monitor_rule, monitor_profile RESTART IDENTITY CASCADE")
    with TestClient(
        create_app(Settings(URL)), base_url="http://localhost", headers={"Origin": "http://localhost"}
    ) as client:
        yield client


def profile(**changes):
    data = {
        "topics": ["AI Agents"],
        "include": ["Agent workflows"],
        "exclude": ["Job listings"],
        "competitors": ["Acme Labs"],
        "people": ["@mayachen"],
        "sources": {key: True for key in ("x", "web", "hn", "reddit", "github", "rss")},
    }
    data.update(changes)
    return data


def test_profile_round_trip_and_initial_run_snapshot(client):
    saved = client.put("/api/profile", json=profile())
    assert saved.status_code == 200, saved.text
    assert saved.json()["topics"] == ["AI Agents"]
    assert saved.json()["schedule_hours"] == 4
    assert client.get("/api/profile").json() == saved.json()

    runs = client.get("/api/collection-runs").json()
    assert len(runs) == 1
    assert runs[0]["trigger"] == "initial"
    assert runs[0]["status"] == "queued"
    assert runs[0]["profile_snapshot"]["topics"] == ["AI Agents"]

    changed = profile(topics=["Developer Experience"], sources={**profile()["sources"], "x": False})
    assert client.put("/api/profile", json=changed).status_code == 200
    assert client.get("/api/profile").json()["sources"]["x"] is False
    assert len(client.get("/api/collection-runs").json()) == 1
    assert client.get("/api/collection-runs").json()[0]["profile_snapshot"]["topics"] == ["AI Agents"]


@pytest.mark.parametrize("changes", [
    {"topics": ["  "]},
    {"topics": ["AI Agents", " ai   agents "]},
    {"topics": ["x" * 101]},
    {"sources": {"unknown": True}},
])
def test_invalid_profile_is_atomic_and_explained(client, changes):
    assert client.put("/api/profile", json=profile()).status_code == 200
    invalid = client.put("/api/profile", json=profile(**changes))
    assert invalid.status_code == 422
    assert invalid.json()["detail"]
    assert client.get("/api/profile").json()["topics"] == ["AI Agents"]


def test_empty_save_does_not_queue_initial_run_or_expose_credentials(client, monkeypatch):
    monkeypatch.setenv("XAIGROK_API_KEY", "monitoring-placeholder-secret")
    blank = profile(topics=[], include=[], exclude=[], competitors=[], people=[])
    assert client.put("/api/profile", json=blank).status_code == 200
    assert client.get("/api/collection-runs").json() == []
    response = client.get("/api/profile")
    assert "monitoring-placeholder-secret" not in response.text
    assert client.put("/api/profile", json=profile()).status_code == 200
    assert len(client.get("/api/collection-runs").json()) == 1


def test_profile_edit_during_running_job_affects_only_next_run(client):
    from signalscout.collection import SourceResult, process_one

    client.put("/api/profile", json=profile())
    initial = client.get("/api/collection-runs").json()[0]
    edited = profile(topics=["New focus"], sources={**profile()["sources"], "x":False})
    assert client.put("/api/profile", json=edited).status_code == 200
    seen=[]
    def inspect(snapshot, budget):
        seen.append(snapshot["topics"])
        return SourceResult()
    factory=client.app.state.session_factory
    process_one(factory, {key:inspect for key in edited["sources"]})
    assert seen and all(topics==["AI Agents"] for topics in seen)
    manual=client.post("/api/collection-runs").json()
    assert manual["id"]!=initial["id"]
    assert manual["profile_snapshot"]["topics"]==["New focus"]
    assert manual["profile_snapshot"]["sources"]["x"] is False

"""Collection queue and worker orchestration with fixture adapters."""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from signalscout.config import Settings
from signalscout.web import create_app


URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="needs disposable PostgreSQL")


@pytest.fixture
def harness():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=Path(__file__).resolve().parents[1],
                   env={**os.environ, "DATABASE_URL": URL}, check=True, capture_output=True)
    with psycopg.connect(URL.replace("postgresql+psycopg://", "postgresql://")) as connection:
        if connection.execute("SELECT to_regclass('source_run')").fetchone()[0]:
            connection.execute("TRUNCATE source_run, source_item, signal_topic, signal_state, signal, "
                               "collection_run, source_config, monitor_rule, monitor_profile RESTART IDENTITY CASCADE")
    app = create_app(Settings(URL))
    with TestClient(app, base_url="http://localhost", headers={"Origin": "http://localhost"}) as client:
        yield client, app.state.session_factory


def profile():
    return {"topics": ["AI agents"], "include": [], "exclude": [], "competitors": [], "people": [],
            "sources": {key: key in {"hn", "rss"} for key in ("x", "web", "hn", "reddit", "github", "rss")}}


def test_manual_collection_requires_search_terms_and_enabled_sources(harness):
    client, _ = harness
    response = client.post('/api/collection-runs')
    assert response.status_code == 400
    assert 'Monitoring' in response.json()['detail']
    assert client.get('/api/collection-runs').json() == []
    exclusion_only = profile()
    exclusion_only['topics'] = []
    exclusion_only['exclude'] = ['spam']
    client.put('/api/profile', json=exclusion_only)
    assert client.post('/api/collection-runs').status_code == 400
    assert client.get('/api/collection-runs').json() == []
    disabled = profile()
    disabled['sources'] = {key: False for key in disabled['sources']}
    client.put('/api/profile', json=disabled)
    assert client.post('/api/collection-runs').status_code == 400
    assert client.get('/api/collection-runs').json() == []


def test_legacy_empty_run_does_not_report_success_or_call_adapters(harness):
    from sqlalchemy import text
    from signalscout.collection import _insert_run, process_one
    from signalscout.monitoring import empty_profile
    client, factory = harness
    with factory.begin() as session:
        _insert_run(session, 'manual', empty_profile())
    def unexpected(*_):
        pytest.fail('No provider should be contacted without monitoring terms')
    process_one(factory, {key:unexpected for key in empty_profile()['sources']})
    run = client.get('/api/collection-runs').json()[0]
    assert run['status'] == 'failed'
    assert all(row['status'] == 'unavailable' and row['error_code'] == 'missing_monitoring_terms'
               for row in run['sources'])


def test_public_source_results_are_visible_before_model_search(harness):
    from signalscout.collection import SourceResult, process_one
    client, factory = harness
    config = profile()
    config['sources']['x'] = True
    client.put('/api/profile', json=config)
    def public_source(*_):
        return SourceResult(items=[{'source_key':'hn','external_id':'101',
            'source_url':'https://news.ycombinator.com/item?id=101',
            'title':'AI agents in production','snippet':'Public source',
            'published_at':datetime.now(timezone.utc),'topics':['AI agents']}],hit_count=1)
    def model_search(*_):
        assert client.get('/api/signals').json()['total'] == 1
        return SourceResult()
    process_one(factory, {'hn':public_source,'rss':lambda *_:SourceResult(),'x':model_search})
    assert client.get('/api/collection-runs').json()[0]['status'] == 'complete'


def test_manual_requests_reuse_active_run_and_snapshot(harness):
    from sqlalchemy import text

    client, factory = harness
    client.put("/api/profile", json=profile())
    first = client.post("/api/collection-runs")
    second = client.post("/api/collection-runs")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["trigger"] == "initial"
    assert len(client.get("/api/collection-runs").json()) == 1
    with factory.begin() as session:
        session.execute(text("UPDATE collection_run SET status='running' WHERE id=:id"),
                        {"id": first.json()["id"]})
    running = client.post("/api/collection-runs")
    assert running.json()["id"] == first.json()["id"]
    assert len(client.get("/api/collection-runs").json()) == 1


def test_one_scheduled_run_per_utc_slot(harness):
    from signalscout.collection import queue_scheduled

    client, factory = harness
    client.put("/api/profile", json=profile())
    with factory.begin() as session:
        session.execute(__import__("sqlalchemy").text("UPDATE collection_run SET status='complete'"))
    first = queue_scheduled(factory, datetime(2026, 9, 29, 9, 30, tzinfo=timezone.utc))
    second = queue_scheduled(factory, datetime(2026, 9, 29, 11, 59, tzinfo=timezone.utc))
    assert first == second
    runs = client.get("/api/collection-runs").json()
    assert len([run for run in runs if run["trigger"] == "scheduled"]) == 1
    assert runs[0]["scheduled_slot"].startswith("2026-09-29T08:00:00")


def test_partial_run_commits_success_and_safe_source_error(harness):
    from signalscout.collection import SourceResult, process_one

    client, factory = harness
    client.put("/api/profile", json=profile())

    def success(snapshot, budget):
        assert snapshot["topics"] == ["AI agents"]
        return SourceResult(items=[{
            "source_key": "hn", "external_id": "123", "source_url": "https://news.ycombinator.com/item?id=123",
            "content_url": "https://example.org/ai", "title": "AI agents in practice", "snippet": "Useful discussion",
            "published_at": datetime(2026, 9, 29, 9, tzinfo=timezone.utc),
            "metric_name": "points", "metric_value": 15, "topics": ["AI agents"],
            "matched_terms": ["AI agents"],
        }], hit_count=1)

    def timeout(snapshot, budget):
        raise TimeoutError("provider-secret-must-not-leak")

    assert process_one(factory, {"hn": success, "rss": timeout}) is not None
    run = client.get("/api/collection-runs").json()[0]
    assert run["status"] == "partial"
    assert {row["source_key"]: row["status"] for row in run["sources"]}["hn"] == "complete"
    rss = next(row for row in run["sources"] if row["source_key"] == "rss")
    assert rss["status"] == "failed"
    assert "provider-secret" not in str(run)
    assert client.get("/api/signals").json()["total"] == 1


def test_malformed_candidate_is_rejected_and_counted(harness):
    from signalscout.collection import SourceResult, process_one

    client, factory = harness
    client.put("/api/profile", json=profile())

    def bad(snapshot, budget):
        return SourceResult(items=[{"source_key": "hn", "title": "Model narrative only"}], hit_count=1)

    process_one(factory, {"hn": bad, "rss": lambda *_: SourceResult(items=[], hit_count=0)})
    run = client.get("/api/collection-runs").json()[0]
    hn = next(row for row in run["sources"] if row["source_key"] == "hn")
    assert hn["accepted_count"] == 0
    assert hn["error_count"] == 1
    assert client.get("/api/signals").json()["total"] == 0


def test_worker_cycle_processes_initial_then_schedules_later(harness):
    from signalscout.collection import SourceResult
    from signalscout.worker import run_cycle

    client, factory = harness
    client.put("/api/profile", json=profile())
    adapters = {key: lambda *_: SourceResult() for key in ("hn", "rss")}
    assert run_cycle(factory, adapters, datetime(2026, 9, 29, 9, tzinfo=timezone.utc)) is not None
    assert client.get("/api/collection-runs").json()[0]["status"] == "complete"
    assert run_cycle(factory, adapters, datetime(2026, 9, 29, 9, tzinfo=timezone.utc)) is not None
    runs = client.get("/api/collection-runs").json()
    assert [run["trigger"] for run in runs] == ["scheduled", "initial"]
    assert all(run["status"] == "complete" for run in runs)


def test_transient_timeout_retries_once_with_bounded_budget(harness):
    from signalscout.collection import SourceResult, process_one

    client, factory = harness
    client.put("/api/profile", json=profile())
    budgets = []

    def flaky(snapshot, budget):
        budgets.append(budget)
        if len(budgets) == 1:
            raise TimeoutError("temporary provider timeout")
        return SourceResult(items=[], request_count=1)

    process_one(factory, {"hn": flaky, "rss": lambda *_: SourceResult()})
    run = client.get("/api/collection-runs").json()[0]
    hn = next(row for row in run["sources"] if row["source_key"] == "hn")
    assert budgets == [10, 10]
    assert hn["status"] == "complete"
    assert hn["request_count"] >= 2


def test_adapter_receives_incremental_cursor_after_prior_success(harness):
    from signalscout.collection import SourceResult, process_one

    client, factory = harness
    client.put("/api/profile", json=profile())
    published = datetime(2026, 9, 29, 9, tzinfo=timezone.utc)
    item = {"source_key":"hn", "source_url":"https://news.ycombinator.com/item?id=99",
            "external_id":"99", "content_url":"https://example.org/99", "title":"AI agents",
            "snippet":"Signal", "published_at":published, "topics":["AI agents"]}
    process_one(factory, {"hn": lambda *_: SourceResult(items=[item]),
                          "rss": lambda *_: SourceResult()})
    queued = client.post("/api/collection-runs")
    assert queued.json()["trigger"] == "manual"
    seen = []
    def inspect(snapshot, budget):
        seen.append(snapshot.get("_since"))
        return SourceResult()
    process_one(factory, {"hn": inspect, "rss": lambda *_: SourceResult()})
    assert seen == [published.isoformat()]


def test_missing_provider_configuration_has_actionable_safe_status(harness):
    from signalscout.adapters import build_adapters
    from signalscout.collection import process_one

    client, factory = harness
    only_unavailable = profile()
    only_unavailable["sources"] = {key: key in {"x", "rss"} for key in only_unavailable["sources"]}
    client.put("/api/profile", json=only_unavailable)
    process_one(factory, build_adapters({}))
    run = client.get("/api/collection-runs").json()[0]
    rows = {row["source_key"]:row for row in run["sources"]}
    assert run["status"] == "failed"
    assert rows["x"]["error_code"] == "missing_xai_key"
    assert "XAIGROK_API_KEY" in rows["x"]["error_message"]
    assert rows["rss"]["error_code"] == "no_rss_feeds"
    assert "RSS_FEED_URLS" in rows["rss"]["error_message"]


def test_stale_running_job_recovers_without_repeating_completed_source(harness):
    from sqlalchemy import text
    from signalscout.collection import SourceResult, process_one, recover_stale_runs

    client, factory = harness
    client.put("/api/profile", json=profile())
    run_id = client.get("/api/collection-runs").json()[0]["id"]
    with factory.begin() as session:
        session.execute(text("UPDATE collection_run SET status='running', "
                             "started_at='2026-09-29T08:00:00+00:00' WHERE id=:id"), {"id":run_id})
        session.execute(text("INSERT INTO source_run (run_id, source_key, status) "
                             "VALUES (:id, 'hn', 'complete')"), {"id":run_id})
    assert recover_stale_runs(factory, datetime(2026, 9, 29, 9, tzinfo=timezone.utc)) == 1
    def should_not_repeat(*_):
        raise AssertionError('completed HN source reran')
    assert process_one(factory, {"hn":should_not_repeat, "rss":lambda *_:SourceResult()}) == run_id
    run = client.get("/api/collection-runs").json()[0]
    assert run["status"] == "complete"
    assert len([source for source in run["sources"] if source["source_key"] == "hn"]) == 1

"""Feed ingest, grouping, filtering, and triage contracts."""

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from signalscout.config import Settings
from signalscout.web import create_app


URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="needs disposable PostgreSQL")
NOW = datetime(2026, 9, 29, 10, tzinfo=timezone.utc)


@pytest.fixture
def harness():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=Path(__file__).resolve().parents[1],
                   env={**os.environ, "DATABASE_URL": URL}, check=True, capture_output=True)
    with psycopg.connect(URL.replace("postgresql+psycopg://", "postgresql://")) as connection:
        if connection.execute("SELECT to_regclass('source_item')").fetchone()[0]:
            connection.execute("TRUNCATE source_item, signal_topic, signal_state, signal, collection_run, "
                               "source_config, monitor_rule, monitor_profile RESTART IDENTITY CASCADE")
    app = create_app(Settings(URL))
    with TestClient(app, base_url="http://localhost", headers={"Origin": "http://localhost"}) as client:
        yield client, app.state.session_factory


def candidate(source="hn", external_id="one", source_url="https://news.ycombinator.com/item?id=1",
              content_url="https://example.org/story?utm_source=hn", title="A useful story",
              published_at=NOW, metric_value=12, topics=None, **changes):
    item = dict(source_key=source, external_id=external_id, source_url=source_url,
                content_url=content_url, title=title, snippet="Full available snippet",
                published_at=published_at, metric_name="points", metric_value=metric_value,
                matched_terms=["AI agents"], topics=topics or ["AI agents"])
    item.update(changes)
    return item


def test_canonical_grouping_keeps_contributors_and_repeat_is_idempotent(harness):
    from signalscout.feed import ingest_candidate

    client, factory = harness
    with factory.begin() as session:
        first = ingest_candidate(session, candidate())
        second = ingest_candidate(session, candidate(source="rss", external_id="two",
            source_url="https://feed.example.net/entry/2",
            content_url="https://example.org/story?utm_campaign=daily", metric_value=4))
        again = ingest_candidate(session, candidate())
    assert first == second == again
    feed = client.get("/api/signals").json()
    assert feed["total"] == 1
    detail = client.get(f"/api/signals/{first}").json()
    assert len(detail["source_items"]) == 2
    assert {item["source_key"] for item in detail["source_items"]} == {"hn", "rss"}
    assert detail["topics"] == ["AI agents"]


def test_conservative_title_grouping_and_safe_urls(harness):
    from signalscout.feed import ingest_candidate

    client, factory = harness
    with factory.begin() as session:
        one = ingest_candidate(session, candidate())
        same_target = ingest_candidate(session, candidate(source="rss", external_id="two",
            source_url="https://feed.example.net/2", content_url="https://example.org/another",
            published_at=NOW + timedelta(hours=1)))
        different_host = ingest_candidate(session, candidate(source="github", external_id="three",
            source_url="https://github.com/a/b/issues/3", content_url="https://elsewhere.org/story"))
        old = ingest_candidate(session, candidate(source="web", external_id="four",
            source_url="https://news.example.net/four", content_url="https://example.org/old",
            published_at=NOW - timedelta(days=5)))
        invalid = ingest_candidate(session, candidate(source="web", external_id="bad",
            source_url="javascript:alert(1)"))
        private = ingest_candidate(session, candidate(source="web", external_id="private",
            source_url="http://127.0.0.1/private"))
    assert one == same_target
    assert len({one, different_host, old}) == 3
    assert invalid is None
    assert private is None
    assert client.get("/api/signals").json()["total"] == 3


def test_filters_triage_and_summary_are_persistent(harness):
    from signalscout.feed import ingest_candidate

    client, factory = harness
    with factory.begin() as session:
        older = ingest_candidate(session, candidate(topics=["AI agents"], metric_value=5))
        newer = ingest_candidate(session, candidate(source="github", external_id="two",
            source_url="https://github.com/a/b/issues/2", content_url="https://example.org/new",
            title="New signal", published_at=NOW + timedelta(hours=2), metric_value=50,
            metric_name="stars", topics=["Open source"]))
    result = client.get("/api/signals", params={"source": "github", "topic": "Open source",
        "from": NOW.isoformat(), "min_engagement": 25, "state": "all", "page_size": 1}).json()
    assert result["total"] == 1
    assert result["items"][0]["id"] == newer
    assert result["items"][0]["metric_name"] == "stars"
    assert client.patch(f"/api/signals/{newer}/state", json={"saved": True, "interesting": True,
        "dismissed": True}).status_code == 200
    assert [item["id"] for item in client.get("/api/signals").json()["items"]] == [older]
    assert client.get("/api/signals", params={"state": "saved"}).json()["total"] == 1
    assert client.get("/api/signals", params={"state": "interesting"}).json()["total"] == 1
    assert client.get("/api/signals", params={"state": "dismissed"}).json()["total"] == 1
    assert client.patch(f"/api/signals/{newer}/state", json={"dismissed": False}).json()["saved"] is True
    assert client.get("/api/signals").json()["items"][0]["id"] == newer
    cleared = client.patch(f"/api/signals/{newer}/state",
                           json={"saved": False, "interesting": False}).json()
    assert cleared == {"saved": False, "dismissed": False, "interesting": False}
    assert client.get("/api/signals", params={"state": "saved"}).json()["total"] == 0
    assert client.get("/api/signals", params={"state": "interesting"}).json()["total"] == 0
    assert client.get("/api/summary").json()["found"] == 2


def test_review_marker_is_stable_within_visit(harness):
    from signalscout.feed import ingest_candidate

    client, factory = harness
    with factory.begin() as session:
        ingest_candidate(session, candidate())
    before = client.get("/api/summary").json()
    assert before["new_since_last_visit"] == 1
    review = client.post("/api/feed-reviewed")
    assert review.status_code == 200
    assert review.json()["new_since_last_visit"] == 1
    assert client.get("/api/summary").json()["new_since_last_visit"] == 0
    with factory.begin() as session:
        ingest_candidate(session, candidate(source="github", external_id="later",
            source_url="https://github.com/a/b/issues/4", content_url="https://example.org/later",
            title="A later story"))
    assert client.get("/api/summary").json()["new_since_last_visit"] == 1


def test_equal_publication_time_prefers_contributor_with_metric(harness):
    from signalscout.feed import ingest_candidate

    client, factory = harness
    with factory.begin() as session:
        signal_id = ingest_candidate(session, candidate(metric_value=24))
        ingest_candidate(session, candidate(source="rss", external_id="rss-1",
            source_url="https://feeds.example.org/entry/1", content_url="https://example.org/story",
            metric_name=None, metric_value=None))
    filtered = client.get("/api/signals", params={"source":"rss", "min_engagement":20}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == signal_id
    assert filtered["items"][0]["metric_name"] == "points"


def test_composed_filters_keep_newest_order_across_pages(harness):
    from signalscout.feed import ingest_candidate

    client, factory = harness
    with factory.begin() as session:
        for index in range(5):
            ingest_candidate(session, candidate(
                source="hn", external_id=str(index),
                source_url=f"https://news.ycombinator.com/item?id={index+1}",
                content_url=f"https://example.org/story-{index}", title=f"AI agents story {index}",
                published_at=NOW+timedelta(hours=index), metric_value=20+index,
                topics=["AI agents"]))
    params={"source":"hn", "topic":"AI agents", "from":NOW.isoformat(),
            "to":(NOW+timedelta(hours=5)).isoformat(), "min_engagement":20,
            "state":"all", "page_size":2}
    first=client.get("/api/signals",params={**params,"page":1}).json()
    second=client.get("/api/signals",params={**params,"page":2}).json()
    assert first["total"]==second["total"]==5
    assert [item["title"] for item in first["items"]]==["AI agents story 4","AI agents story 3"]
    assert [item["title"] for item in second["items"]]==["AI agents story 2","AI agents story 1"]
    assert client.get("/api/signals",params={**params,"page_size":51}).status_code==422

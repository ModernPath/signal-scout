import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from intelligence_service import IntelligenceService, public_url
from intelligence_store import IntelligenceStore


@pytest.fixture
def service():
    url = os.environ.get("SIGNAL_INTELLIGENCE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set SIGNAL_INTELLIGENCE_TEST_DATABASE_URL to a disposable migrated PostgreSQL database")
    assert url.rsplit("/", 1)[-1] == "signalscout_intelligence_test"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE content_draft, research_evidence, research_run, opportunity, "
                          "conversation_signal, conversation, intelligence_run, company_content, "
                          "company_brief, source_item, signal_topic, signal_state, signal CASCADE"))
        for id, title, source in ((1, "Acme launches agent security toolkit", "web"),
                                  (2, "Acme agent security toolkit released", "github"),
                                  (3, "Beta announces hiring platform", "web")):
            conn.execute(text("INSERT INTO signal (id,title,snippet,canonical_url_key,published_at) "
                              "VALUES (:id,:title,:title,:url,now())"),
                         {"id": id, "title": title, "url": f"https://example.com/{id}"})
            conn.execute(text("INSERT INTO source_item (signal_id,source_key,external_id,source_url,"
                              "content_url,canonical_url_key,target_host,title,normalized_title,snippet,"
                              "published_at) VALUES (:id,:source,:external,:url,:url,:url,'example.com',"
                              ":title,:title,:title,now())"),
                         {"id": id, "source": source, "external": str(id),
                          "url": f"https://example.com/{id}", "title": title})
    yield IntelligenceService(IntelligenceStore(engine), now=lambda: datetime.now(timezone.utc))
    engine.dispose()


def test_analysis_persists_in_shared_postgres_and_is_idempotent(service):
    service.set_brief({"description": "Security platform for AI agents",
                       "audience": "Security leaders", "expertise": "Agent security",
                       "point_of_view": "Verify agent actions", "voice": "Practical",
                       "avoid_claims": "Guaranteed safety"})
    service.add_content({"title": "Our prior take", "text": "AI agent security needs verification",
                         "url": "https://company.example/prior", "channel": "blog"})
    first = service.analyze()
    second = service.analyze()
    assert first["run_id"] == second["run_id"]
    assert len(first["opportunities"]) == 2
    assert sorted(sorted(item["signal_ids"]) for item in first["opportunities"]) == [[1, 2], [3]]
    assert all(item["evidence_source_item_ids"] for item in first["opportunities"])


def test_research_and_drafts_require_provider_and_evidence(service):
    service.set_brief({"description": "Security platform for AI agents",
                       "audience": "Security leaders", "expertise": "Agent security",
                       "point_of_view": "Verify agent actions", "voice": "Practical",
                       "avoid_claims": "Guaranteed safety"})
    opportunity = service.analyze()["opportunities"][0]
    with pytest.raises(RuntimeError, match="provider"):
        service.research(opportunity["id"])
    with pytest.raises(ValueError, match="research"):
        service.draft(opportunity["id"], "linkedin", "post")


def test_private_ip_urls_are_not_accepted():
    assert not public_url("http://10.1.2.3/internal")
    assert not public_url("http://[::1]/internal")
    assert public_url("https://example.com/story")


def test_signal_without_published_time_uses_collection_time(service):
    with service.store.engine.begin() as connection:
        connection.execute(text("INSERT INTO signal (id,title,snippet,canonical_url_key,published_at) "
                                "VALUES (4,'Gamma release','Gamma release','https://example.com/4',NULL)"))
        connection.execute(text("INSERT INTO source_item (signal_id,source_key,external_id,source_url,"
                                "content_url,canonical_url_key,target_host,title,normalized_title,snippet) "
                                "VALUES (4,'rss','4','https://example.com/4','https://example.com/4',"
                                "'https://example.com/4','example.com','Gamma release','Gamma release',"
                                "'Gamma release')"))
    result = service.analyze()
    assert any(4 in item["signal_ids"] for item in result["opportunities"])


def test_grounded_research_and_all_draft_formats_are_saved(service):
    from intelligence_service import IntelligenceService

    class Provider:
        model = "test-model"

        def research(self, opportunity, source_items):
            return {"status": "complete", "summary": "Two sources describe the release.",
                    "evidence": [{"source_url": item["source_url"], "claim": item["title"],
                                  "stance": "support", "retrieved": True}
                                 for item in source_items[:2]]}

        def draft(self, opportunity, research, brief, channel, format):
            return {"text": f"{channel} {format}: Why verify agent actions?",
                    "evidence_ids": [research["evidence"][0]["id"]]}

    agent = IntelligenceService(service.store, provider=Provider(), now=service.now)
    agent.set_brief({"description": "Security platform for AI agents",
                     "audience": "Security leaders", "expertise": "Agent security",
                     "point_of_view": "Verify agent actions", "voice": "Practical",
                     "avoid_claims": "Guaranteed safety"})
    opportunity = next(item for item in agent.analyze()["opportunities"]
                       if len(item["signal_ids"]) == 2)
    research = agent.research(opportunity["id"])
    assert research["status"] == "complete"
    assert len(research["evidence"]) == 2
    drafts = [agent.draft(opportunity["id"], channel, format)
              for channel in ("linkedin", "x") for format in ("post", "reply")]
    assert len({item["id"] for item in drafts}) == 4
    assert all(item["research_run_id"] == research["id"] for item in drafts)
    with service.store.engine.connect() as connection:
        assert connection.execute(text("SELECT model_version FROM research_run WHERE id=:id"),
                                  {"id": research["id"]}).scalar_one() == "test-model"
        assert connection.execute(text("SELECT model_version FROM content_draft WHERE id=:id"),
                                  {"id": drafts[0]["id"]}).scalar_one() == "test-model"

    class BadProvider(Provider):
        def draft(self, *args):
            return {"text": "Guaranteed safety for 99% of users", "evidence_ids": [research["evidence"][0]["id"]]}

    bad = IntelligenceService(service.store, provider=BadProvider(), now=service.now)
    with pytest.raises(RuntimeError, match="unsupported|prohibited"):
        bad.draft(opportunity["id"], "linkedin", "post")


def test_context_replacement_and_deletion_keep_only_active_memory(service):
    first = service.add_content({"title": "Old view", "text": "Old claim", "channel": "blog"})
    updated = service.replace_content(first["id"], {"title": "New view", "text": "New claim",
                                                      "channel": "blog"})
    assert updated["id"] != first["id"]
    assert [item["title"] for item in service.list_content()] == ["New view"]
    service.delete_content(updated["id"])
    assert service.list_content() == []
    with service.store.engine.connect() as connection:
        historical = connection.execute(text("SELECT title,content_text FROM company_content "
                                             "WHERE id IN (:old,:new) ORDER BY id"),
                                        {"old": first["id"], "new": updated["id"]}).all()
    assert historical == [("[deleted]", ""), ("[deleted]", "")]


def test_deleted_content_can_be_added_again(service):
    item = {"title": "Company view", "text": "Verified message", "channel": "blog"}
    first = service.add_content(item)
    service.delete_content(first["id"])
    added = service.add_content(item)
    assert added["id"] != first["id"]
    assert [row["text"] for row in service.list_content()] == ["Verified message"]


def test_company_brief_can_be_cleared_without_leaking_its_text(service):
    saved = service.set_brief({"description": "Private company position",
                               "audience": "Security leaders", "expertise": "Security",
                               "point_of_view": "Verify claims", "voice": "Practical"})
    assert service.clear_brief() == {"id": saved["id"], "deleted": True}
    assert service.get_brief() is None
    with service.store.engine.connect() as connection:
        row = connection.execute(text("SELECT brief,active FROM company_brief WHERE id=:id"),
                                 {"id": saved["id"]}).one()
    assert row.brief == {}
    assert row.active is False


def test_research_without_selected_source_confirmation_stays_partial(service):
    class UnrelatedProvider:
        model = "test-model"

        def research(self, opportunity, source_items):
            return {"status": "complete", "summary": "Similar company topic",
                    "evidence": [
                        {"source_url": "https://other.example/one", "claim": "Agent security advice",
                         "stance": "unknown", "retrieved": True},
                        {"source_url": "https://different.example/two", "claim": "More agent security advice",
                         "stance": "unknown", "retrieved": True},
                    ]}

    agent = IntelligenceService(service.store, provider=UnrelatedProvider(), now=service.now)
    opportunity = agent.analyze()["opportunities"][0]
    result = agent.research(opportunity["id"])
    assert result["status"] == "partial"
    assert "starting source" in result["summary"].lower()
    with pytest.raises(ValueError, match="Complete research"):
        agent.draft(opportunity["id"], "linkedin", "post")


def test_provider_failure_records_partial_research_without_exposing_details(service):
    class FailingProvider:
        model = "test-model"

        def research(self, opportunity, source_items):
            raise RuntimeError("secret credential in provider failure")

    agent = IntelligenceService(service.store, provider=FailingProvider(), now=service.now)
    opportunity = agent.analyze()["opportunities"][0]
    with pytest.raises(RuntimeError, match="Research provider failed"):
        agent.research(opportunity["id"])
    record = agent.store.latest_research(opportunity["id"])
    assert record["status"] == "partial"
    assert record["evidence"] == []
    assert "secret credential" not in str(record)
    assert record["error_summary"] == "Research provider failed or returned unusable evidence"


def test_chat_memory_is_bounded_and_can_be_deleted(service):
    session = service.create_chat_session()
    service.append_chat_turn(session["id"], "user", "Find opportunities")
    service.append_chat_turn(session["id"], "assistant", "Two opportunities")
    assert [turn["role"] for turn in service.chat_history(session["id"])] == ["user", "assistant"]
    service.delete_chat_session(session["id"])
    with pytest.raises(LookupError):
        service.chat_history(session["id"])


def test_service_uses_bounded_subagents_for_all_three_jobs(service):
    class Runner:
        calls = []

        def run(self, name, payload):
            self.calls.append((name, payload))
            if name == "topic_analyst":
                return {"label": "Agent security toolkit", "summary": "A release", "accepted": True}
            if name == "evidence_researcher":
                items = service.store.source_evidence(
                    service.opportunity(payload["opportunity_id"])["evidence_source_item_ids"])
                return {"status": "complete", "summary": "Two sources confirm release.",
                        "evidence": [{"source_url": item["source_url"], "claim": item["title"],
                                      "stance": "support", "retrieved": True}
                                     for item in items[:2]]}
            research = service.store.latest_research(payload["opportunity_id"])
            return {"text": "Verify agent actions before adopting the toolkit.",
                    "evidence_ids": [research["evidence"][0]["id"]]}

    runner = Runner()
    agent = IntelligenceService(service.store, subagent_runner=runner, now=service.now)
    agent.set_brief({"description": "Security platform for AI agents",
                     "audience": "Security leaders", "expertise": "Agent security",
                     "point_of_view": "Verify agent actions", "voice": "Practical"})
    opportunity = next(item for item in agent.analyze()["opportunities"]
                       if len(item["signal_ids"]) == 2)
    assert opportunity["label"] == "Agent security toolkit"
    agent.research(opportunity["id"])
    agent.draft(opportunity["id"], "linkedin", "post")
    assert {name for name, _ in runner.calls} == {
        "topic_analyst", "evidence_researcher", "draft_writer"}


def test_research_excerpts_have_retention_deadline_and_cleanup_preserves_url(service):
    class Provider:
        def research(self, opportunity, source_items):
            return {"status": "partial", "summary": "One source", "evidence": [{
                "source_url": source_items[0]["source_url"], "claim": "A cited claim",
                "stance": "unknown", "retrieved": True}]}

    agent = IntelligenceService(service.store, provider=Provider(), now=service.now)
    opportunity = agent.analyze()["opportunities"][0]
    research = agent.research(opportunity["id"])
    with service.store.engine.connect() as connection:
        expiry = connection.execute(text("SELECT excerpt_expires_at FROM research_evidence "
                                         "WHERE id=:id"),
                                    {"id": research["evidence"][0]["id"]}).scalar_one()
    assert expiry is not None
    with service.store.engine.begin() as connection:
        connection.execute(text("UPDATE research_evidence SET excerpt_expires_at=now()-interval '1 day' "
                                "WHERE id=:id"), {"id": research["evidence"][0]["id"]})
    assert agent.cleanup_expired()["research_excerpts_expired"] == 1
    stored = agent.store.latest_research(opportunity["id"])["evidence"][0]
    assert stored["claim"] == "[expired]"
    assert stored["source_url"] == research["evidence"][0]["source_url"]

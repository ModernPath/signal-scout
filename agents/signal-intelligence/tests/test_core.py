from datetime import datetime, timedelta, timezone

from intelligence_core import cluster_signals, rank_conversation


NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def signal(id, title, days_ago=0, topics=("AI",), source="web"):
    return {"id": id, "title": title, "snippet": title,
            "published_at": NOW - timedelta(days=days_ago),
            "topics": topics, "sources": (source,),
            "source_items": ({"id": id * 10, "source_url": f"https://example.com/{id}"},)}


def test_related_signals_cluster_without_merging_broad_topic_neighbors():
    signals = [
        signal(1, "Acme releases agent security toolkit", source="github"),
        signal(2, "Acme agent security toolkit launches", source="web"),
        signal(3, "Beta unveils AI hiring platform", source="web"),
    ]
    groups = cluster_signals(signals)
    assert sorted(sorted(group["signal_ids"]) for group in groups) == [[1, 2], [3]]
    assert all(group["reason"] for group in groups)


def test_rank_preserves_unknown_novelty_and_no_cross_source_engagement_arithmetic():
    group = [signal(1, "Acme releases agent security toolkit", 0, source="github"),
             signal(2, "Acme agent security toolkit launches", 1, source="web")]
    brief = {"description": "Security platform for AI agents", "audience": "Security leaders",
             "expertise": "Agent security", "point_of_view": "Verify agent actions",
             "voice": "Practical", "avoid_claims": ""}
    first = rank_conversation(group, brief, [], NOW, topics=("agent security",))
    assert set(first["components"]) == {"relevance", "velocity", "novelty", "pov_fit"}
    assert first["components"]["novelty"] is None
    assert first["components"]["velocity"] is None  # Too little history for a trend.
    assert first["confidence"] < 1
    assert "unknown" in first["why_now"].lower()

    old = [{"title": "Agent security toolkit launch", "text":
            "Acme releases an agent security toolkit and how to verify agent actions"}]
    with_history = rank_conversation(group, brief, old, NOW, topics=("agent security",))
    assert with_history["components"]["novelty"] is not None
    assert with_history["components"]["novelty"] < 50
    assert with_history["prior_content_matches"]


def test_company_fit_is_unknown_when_brief_is_missing():
    result = rank_conversation([signal(1, "Acme releases agent security toolkit")],
                               None, [], NOW, topics=("agent security",))
    assert result["components"]["pov_fit"] is None
    assert "unavailable" in result["why_us"].lower()


def test_weak_company_match_does_not_claim_relevance():
    brief = {"description": "Security platform for AI agents", "audience": "Security leaders",
             "expertise": "Agent security", "point_of_view": "Verify agent actions",
             "voice": "Practical", "avoid_claims": ""}
    result = rank_conversation([signal(3, "Beta announces hiring platform")],
                               brief, [], NOW, topics=("agent security",))
    assert result["components"]["pov_fit"] < 50
    assert "weak" in result["why_us"].lower()

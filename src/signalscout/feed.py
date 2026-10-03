"""Conservative signal grouping, provenance, filtering, and triage."""

import hashlib
import ipaddress
import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from .monitoring import SOURCE_KEYS


TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def safe_http_url(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.port == 0):
            return None
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".local", ".internal")):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
    except ValueError:
        return None
    return value.strip()


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    query = urlencode([(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
                       if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS])
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))


def normalized_title(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def ingest_candidate(session: Session, candidate: dict) -> int | None:
    """Accept one provider candidate; return its grouped signal ID, or reject it."""
    source = candidate.get("source_key")
    source_url = safe_http_url(candidate.get("source_url"))
    title = candidate.get("title")
    if source not in SOURCE_KEYS or not source_url or not isinstance(title, str) or not title.strip():
        return None
    content_url = safe_http_url(candidate.get("content_url")) or source_url
    published = candidate.get("published_at")
    if published is not None and (not isinstance(published, datetime) or published.tzinfo is None):
        return None
    metric = candidate.get("metric_value")
    if metric is not None and (not isinstance(metric, int) or metric < 0):
        return None
    external_id = candidate.get("external_id") or hashlib.sha256(source_url.encode()).hexdigest()
    existing = session.execute(text(
        "SELECT signal_id FROM source_item WHERE source_key = :source AND external_id = :external_id"
    ), {"source": source, "external_id": str(external_id)}).scalar_one_or_none()
    if existing is not None:
        return existing

    key = canonical_url(content_url)
    host = urlsplit(content_url).hostname.lower()
    title_key = normalized_title(title)
    same_url = session.execute(text(
        "SELECT DISTINCT signal_id FROM source_item WHERE canonical_url_key = :key LIMIT 2"
    ), {"key": key}).scalars().all()
    signal_id = same_url[0] if len(same_url) == 1 else None
    if signal_id is None and published is not None and title_key:
        matches = session.execute(text(
            "SELECT DISTINCT signal_id FROM source_item WHERE target_host = :host "
            "AND normalized_title = :title_key AND published_at BETWEEN :after AND :before LIMIT 2"
        ), {"host": host, "title_key": title_key,
            "after": published - timedelta(hours=48), "before": published + timedelta(hours=48)}).scalars().all()
        if len(matches) == 1:
            signal_id = matches[0]
    if signal_id is None:
        signal_id = session.execute(text(
            "INSERT INTO signal (title, snippet, canonical_url_key, published_at) "
            "VALUES (:title, :snippet, :key, :published) RETURNING id"
        ), {"title": title.strip()[:500], "snippet": str(candidate.get("snippet") or "")[:4000],
            "key": key, "published": published}).scalar_one()
    else:
        session.execute(text(
            "UPDATE signal SET title = :title, snippet = :snippet, published_at = :published, "
            "updated_at = now() WHERE id = :id AND (published_at IS NULL OR "
            "(:published IS NOT NULL AND published_at < :published))"
        ), {"title": title.strip()[:500], "snippet": str(candidate.get("snippet") or "")[:4000],
            "published": published, "id": signal_id})
    session.execute(text(
        "INSERT INTO source_item (signal_id, source_key, external_id, source_url, content_url, "
        "canonical_url_key, target_host, title, normalized_title, snippet, published_at, "
        "metric_name, metric_value, matched_terms) VALUES (:signal_id, :source, :external_id, "
        ":source_url, :content_url, :key, :host, :title, :title_key, :snippet, :published, "
        ":metric_name, :metric_value, :matched_terms)"
    ).bindparams(bindparam("matched_terms", type_=JSONB())), {
        "signal_id": signal_id, "source": source, "external_id": str(external_id),
        "source_url": source_url, "content_url": content_url, "key": key, "host": host,
        "title": title.strip()[:500], "title_key": title_key,
        "snippet": str(candidate.get("snippet") or "")[:4000], "published": published,
        "metric_name": str(candidate.get("metric_name") or "")[:40] or None,
        "metric_value": metric, "matched_terms": candidate.get("matched_terms") or [],
    })
    for topic in candidate.get("topics") or []:
        if isinstance(topic, str) and topic.strip():
            session.execute(text(
                "INSERT INTO signal_topic (signal_id, topic) VALUES (:id, :topic) ON CONFLICT DO NOTHING"
            ), {"id": signal_id, "topic": topic.strip()[:100]})
    return signal_id


CARD_FROM = """
FROM signal s
JOIN LATERAL (
    SELECT source_key, source_url, metric_name, metric_value, published_at
    FROM source_item WHERE signal_id = s.id
    ORDER BY published_at DESC NULLS LAST, (metric_value IS NULL), id DESC LIMIT 1
) primary_item ON true
LEFT JOIN signal_state st ON st.signal_id = s.id
"""


class StatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saved: bool | None = None
    dismissed: bool | None = None
    interesting: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Provide at least one boolean state flag")
        return self


def make_router(session_factory: Callable[[], Session]) -> APIRouter:
    router = APIRouter()

    @router.get("/signals")
    def list_signals(
        source: str | None = None, topic: str | None = None,
        from_: datetime | None = Query(None, alias="from"), to: datetime | None = None,
        min_engagement: int = Query(0, ge=0), state: str = "all",
        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
    ):
        if state not in {"all", "saved", "interesting", "dismissed"}:
            raise HTTPException(422, "Invalid state")
        if source and source not in SOURCE_KEYS:
            raise HTTPException(422, "Invalid source")
        predicates = ["COALESCE(primary_item.metric_value, 0) >= :minimum"]
        params = {"minimum": min_engagement, "limit": page_size, "offset": (page - 1) * page_size}
        if state == "all":
            predicates.append("NOT COALESCE(st.dismissed, false)")
        else:
            predicates.append(f"COALESCE(st.{state}, false)")
        if source:
            predicates.append("EXISTS (SELECT 1 FROM source_item si WHERE si.signal_id = s.id AND si.source_key = :source)")
            params["source"] = source
        if topic:
            predicates.append("EXISTS (SELECT 1 FROM signal_topic t WHERE t.signal_id = s.id AND t.topic = :topic)")
            params["topic"] = topic
        if from_:
            predicates.append("s.published_at >= :from_time")
            params["from_time"] = from_
        if to:
            predicates.append("s.published_at <= :to_time")
            params["to_time"] = to
        where = " WHERE " + " AND ".join(predicates)
        with session_factory() as session:
            total = session.execute(text("SELECT count(*) " + CARD_FROM + where), params).scalar_one()
            rows = session.execute(text(
                "SELECT s.id, s.title, s.snippet, s.published_at, primary_item.source_key, "
                "primary_item.source_url, primary_item.metric_name, primary_item.metric_value, "
                "COALESCE(st.saved, false) AS saved, COALESCE(st.dismissed, false) AS dismissed, "
                "COALESCE(st.interesting, false) AS interesting, "
                "(SELECT count(*) FROM source_item si WHERE si.signal_id = s.id) AS source_count "
                + CARD_FROM + where +
                " ORDER BY s.published_at DESC NULLS LAST, s.id DESC LIMIT :limit OFFSET :offset"
            ), params).mappings().all()
            items = []
            for row in rows:
                card = dict(row)
                card["topics"] = session.execute(text(
                    "SELECT topic FROM signal_topic WHERE signal_id = :id ORDER BY topic"
                ), {"id": card["id"]}).scalars().all()
                items.append(card)
            return {"items": items, "total": total, "page": page, "page_size": page_size}

    @router.get("/signals/{signal_id}")
    def get_signal(signal_id: int):
        with session_factory() as session:
            row = session.execute(text(
                "SELECT s.id, s.title, s.snippet, s.published_at, "
                "COALESCE(st.saved, false) AS saved, COALESCE(st.dismissed, false) AS dismissed, "
                "COALESCE(st.interesting, false) AS interesting "
                "FROM signal s LEFT JOIN signal_state st ON st.signal_id = s.id WHERE s.id = :id"
            ), {"id": signal_id}).mappings().first()
            if row is None:
                raise HTTPException(404, "Signal not found")
            result = dict(row)
            result["topics"] = session.execute(text(
                "SELECT topic FROM signal_topic WHERE signal_id = :id ORDER BY topic"
            ), {"id": signal_id}).scalars().all()
            result["source_items"] = [dict(item) for item in session.execute(text(
                "SELECT source_key, source_url, content_url, title, snippet, published_at, "
                "metric_name, metric_value, matched_terms FROM source_item WHERE signal_id = :id "
                "ORDER BY published_at DESC NULLS LAST, (metric_value IS NULL), id DESC"
            ), {"id": signal_id}).mappings().all()]
            result["matched_terms"] = sorted({term for item in result["source_items"]
                                               for term in item["matched_terms"]})
            return result

    @router.patch("/signals/{signal_id}/state")
    def patch_state(signal_id: int, patch: StatePatch):
        with session_factory.begin() as session:
            exists = session.execute(text("SELECT 1 FROM signal WHERE id = :id"), {"id": signal_id}).first()
            if not exists:
                raise HTTPException(404, "Signal not found")
            session.execute(text("INSERT INTO signal_state (signal_id) VALUES (:id) ON CONFLICT DO NOTHING"),
                            {"id": signal_id})
            for field in patch.model_fields_set:
                session.execute(text(
                    f"UPDATE signal_state SET {field} = :value, {field}_at = "
                    f"CASE WHEN :value THEN now() ELSE NULL END WHERE signal_id = :id"
                ), {"value": getattr(patch, field), "id": signal_id})
            return dict(session.execute(text(
                "SELECT saved, dismissed, interesting FROM signal_state WHERE signal_id = :id"
            ), {"id": signal_id}).mappings().one())

    @router.get("/summary")
    def summary():
        with session_factory() as session:
            marker = session.execute(text(
                "SELECT last_reviewed_at FROM monitor_profile WHERE id = 1"
            )).scalar_one_or_none()
            found = session.execute(text("SELECT count(*) FROM signal")).scalar_one()
            duplicates = session.execute(text("SELECT count(*) FROM source_item")).scalar_one() - found
            if marker is None:
                new_count = found
            else:
                new_count = session.execute(text(
                    "SELECT count(*) FROM signal WHERE created_at > :marker"
                ), {"marker": marker}).scalar_one()
            return {"found": found, "new_since_last_visit": new_count, "grouped_duplicate_hits": duplicates}

    @router.post("/feed-reviewed")
    def feed_reviewed():
        with session_factory.begin() as session:
            session.execute(text("INSERT INTO monitor_profile (id) VALUES (1) ON CONFLICT DO NOTHING"))
            previous = session.execute(text(
                "SELECT last_reviewed_at FROM monitor_profile WHERE id = 1 FOR UPDATE"
            )).scalar_one_or_none()
            if previous is None:
                new_count = session.execute(text("SELECT count(*) FROM signal")).scalar_one()
            else:
                new_count = session.execute(text(
                    "SELECT count(*) FROM signal WHERE created_at > :marker"
                ), {"marker": previous}).scalar_one()
            session.execute(text("UPDATE monitor_profile SET last_reviewed_at = now() WHERE id = 1"))
            return {"status": "ok", "new_since_last_visit": new_count}

    return router

"""Database-backed collection queue and isolated source execution."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter

from fastapi import APIRouter, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from .feed import ingest_candidate
from .monitoring import SOURCE_KEYS, collection_ready, has_search_terms, load_profile


@dataclass
class SourceResult:
    items: list[dict] = field(default_factory=list)
    hit_count: int = 0
    request_count: int = 0
    rejected_count: int = 0


class SourceUnavailable(Exception):
    """A source cannot run with current access or configuration."""


class SourceTransientError(Exception):
    """A source request may succeed on one bounded retry."""


class SourceRateLimited(Exception):
    """A provider refused requests because its rate limit was reached."""


Adapter = Callable[[dict, int], SourceResult]
UNAVAILABLE_REASONS = {
    "missing_monitoring_terms": "Add a topic, keyword, competitor or person in Monitoring and save before collecting",
    "missing_xai_key": "XAIGROK_API_KEY is not configured",
    "no_rss_feeds": "RSS_FEED_URLS is empty",
    "rss_url_not_public": "Configured RSS URL is not a public HTTP URL",
    "reddit_access_unavailable": "Approved Reddit API access is not configured",
    "reddit_token_unavailable": "Reddit OAuth token was not granted",
    "provider_access_rejected": "Provider rejected the configured access; check credentials or permissions",
}


def _active_run(session: Session) -> dict | None:
    row = session.execute(text(
        "SELECT id, trigger, status, scheduled_slot, profile_snapshot, queued_at, started_at, finished_at "
        "FROM collection_run WHERE status IN ('queued', 'running') ORDER BY id LIMIT 1"
    )).mappings().first()
    return dict(row) if row else None


def _insert_run(session: Session, trigger: str, snapshot: dict,
                scheduled_slot: datetime | None = None) -> dict:
    row = session.execute(text(
        "INSERT INTO collection_run (trigger, status, scheduled_slot, profile_snapshot) "
        "VALUES (:trigger, 'queued', :slot, :snapshot) "
        "RETURNING id, trigger, status, scheduled_slot, profile_snapshot, queued_at, started_at, finished_at"
    ).bindparams(bindparam("snapshot", type_=JSONB())),
        {"trigger": trigger, "slot": scheduled_slot, "snapshot": snapshot}).mappings().one()
    return dict(row)


def queue_manual(session_factory: Callable[[], Session]) -> dict:
    with session_factory.begin() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(771921)"))
        active = _active_run(session)
        if active:
            return active
        snapshot = load_profile(session)
        if not has_search_terms(snapshot):
            raise ValueError(UNAVAILABLE_REASONS['missing_monitoring_terms'])
        if not any(snapshot['sources'].values()):
            raise ValueError('Enable at least one source in Monitoring and save before collecting')
        return _insert_run(session, "manual", snapshot)


def queue_scheduled(session_factory: Callable[[], Session], now: datetime | None = None) -> int | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    slot = now.replace(hour=(now.hour // 4) * 4, minute=0, second=0, microsecond=0)
    with session_factory.begin() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(771921)"))
        existing = session.execute(text(
            "SELECT id FROM collection_run WHERE scheduled_slot = :slot"
        ), {"slot": slot}).scalar_one_or_none()
        if existing is not None:
            return existing
        active = _active_run(session)
        if active:
            return active["id"]
        snapshot = load_profile(session)
        if not collection_ready(snapshot):
            return None
        return _insert_run(session, "scheduled", snapshot, slot)["id"]


def recover_stale_runs(session_factory: Callable[[], Session], now: datetime | None = None,
                       *, force: bool = False) -> int:
    """Return interrupted work to the queue; source rows make the resume idempotent."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=20)
    with session_factory.begin() as session:
        rows = session.execute(text(
            "UPDATE collection_run SET status = 'queued' WHERE status = 'running' "
            "AND (:force OR started_at < :cutoff) RETURNING id"
        ), {"force": force, "cutoff": cutoff}).scalars().all()
        return len(rows)


def _record_source(session_factory: Callable[[], Session], run_id: int, source: str,
                   status: str, *, hits: int = 0, accepted: int = 0, errors: int = 0,
                   requests: int = 0, duration_ms: int = 0, code: str | None = None,
                   message: str | None = None, items: list[dict] | None = None) -> None:
    with session_factory.begin() as session:
        if items:
            for item in items:
                if item.get("source_key") != source or ingest_candidate(session, item) is None:
                    errors += 1
                else:
                    accepted += 1
        session.execute(text(
            "INSERT INTO source_run (run_id, source_key, status, hit_count, accepted_count, error_count, "
            "request_count, duration_ms, error_code, error_message, started_at, finished_at) "
            "VALUES (:run_id, :source, :status, :hits, :accepted, :errors, :requests, :duration, "
            ":code, :message, now(), now())"
        ), {"run_id": run_id, "source": source, "status": status, "hits": hits,
            "accepted": accepted, "errors": errors, "requests": requests,
            "duration": duration_ms, "code": code, "message": message})


def process_one(session_factory: Callable[[], Session], adapters: Mapping[str, Adapter]) -> int | None:
    """Claim and execute one queued run; each source commits independently."""
    with session_factory.begin() as session:
        row = session.execute(text(
            "SELECT id, profile_snapshot FROM collection_run WHERE status = 'queued' "
            "ORDER BY queued_at, id FOR UPDATE SKIP LOCKED LIMIT 1"
        )).mappings().first()
        if row is None:
            return None
        run_id, snapshot = row["id"], row["profile_snapshot"]
        session.execute(text(
            "UPDATE collection_run SET status = 'running', started_at = now() WHERE id = :id"
        ), {"id": run_id})

    with session_factory() as session:
        existing_statuses = dict(session.execute(text(
            "SELECT source_key, status FROM source_run WHERE run_id = :id"
        ), {"id": run_id}).all())
    success_count = sum(status == "complete" for status in existing_statuses.values())
    failure_count = sum(status in {"failed", "unavailable"} for status in existing_statuses.values())
    # Publish inexpensive public-source batches before slower model search.
    for source in ('hn', 'rss', 'github', 'web', 'x', 'reddit'):
        if source in existing_statuses:
            continue
        if not snapshot.get("sources", {}).get(source, False):
            _record_source(session_factory, run_id, source, "skipped")
            continue
        if not has_search_terms(snapshot):
            failure_count += 1
            _record_source(session_factory, run_id, source, 'unavailable',
                           code='missing_monitoring_terms',
                           message=UNAVAILABLE_REASONS['missing_monitoring_terms'])
            continue
        adapter = adapters.get(source)
        if adapter is None:
            failure_count += 1
            _record_source(session_factory, run_id, source, "unavailable", code="adapter_unavailable",
                           message="Source adapter is not configured")
            continue
        started = perf_counter()
        with session_factory() as session:
            since = session.execute(text(
                "SELECT max(published_at) FROM source_item WHERE source_key = :source"
            ), {"source": source}).scalar_one()
        source_snapshot = {**snapshot, "_since": since.isoformat() if since else None}
        failed_attempts = 0
        try:
            for attempt in range(2):
                try:
                    result = adapter(source_snapshot, 10)
                    break
                except (TimeoutError, SourceTransientError):
                    failed_attempts += 1
                    if attempt == 1:
                        raise
            _record_source(session_factory, run_id, source, "complete", hits=result.hit_count,
                           errors=result.rejected_count,
                           requests=result.request_count + failed_attempts,
                           duration_ms=int((perf_counter() - started) * 1000), items=result.items)
            success_count += 1
        except SourceUnavailable as error:
            failure_count += 1
            code = str(error) if str(error) in UNAVAILABLE_REASONS else "access_unavailable"
            _record_source(session_factory, run_id, source, "unavailable", code=code,
                           message=UNAVAILABLE_REASONS.get(code, "Required source access is unavailable"),
                           duration_ms=int((perf_counter() - started) * 1000))
        except SourceRateLimited:
            failure_count += 1
            _record_source(session_factory, run_id, source, "failed", code="rate_limited",
                           message="Provider rate limit reached; try a later run",
                           duration_ms=int((perf_counter() - started) * 1000))
        except (TimeoutError, SourceTransientError) as error:
            failure_count += 1
            is_timeout = isinstance(error, TimeoutError)
            _record_source(session_factory, run_id, source, "failed",
                           code="source_timeout" if is_timeout else "source_unavailable",
                           message="Source request timed out" if is_timeout else "Provider is temporarily unavailable",
                           requests=failed_attempts,
                           duration_ms=int((perf_counter() - started) * 1000))
        except Exception:
            failure_count += 1
            _record_source(session_factory, run_id, source, "failed", code="source_error",
                           message="Source request failed",
                           duration_ms=int((perf_counter() - started) * 1000))
    status = "complete" if success_count and not failure_count else "partial" if success_count else "failed"
    with session_factory.begin() as session:
        session.execute(text(
            "UPDATE collection_run SET status = :status, finished_at = now() WHERE id = :id"
        ), {"status": status, "id": run_id})
    return run_id


def make_router(session_factory: Callable[[], Session]) -> APIRouter:
    router = APIRouter()

    @router.post("/collection-runs")
    def create_run():
        try:
            return queue_manual(session_factory)
        except ValueError as error:
            raise HTTPException(400, str(error)) from None

    return router

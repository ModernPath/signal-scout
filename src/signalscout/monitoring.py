"""Validated singleton monitoring profile and initial collection enqueue."""

from collections.abc import Callable

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session


SOURCE_KEYS = ("x", "web", "hn", "reddit", "github", "rss")
RULE_FIELDS = {
    "topics": "topic",
    "include": "include",
    "exclude": "exclude",
    "competitors": "competitor",
    "people": "person",
}


def has_search_terms(profile: dict) -> bool:
    return any(profile.get(field) for field in ('topics', 'include', 'competitors', 'people'))


def collection_ready(profile: dict) -> bool:
    return has_search_terms(profile) and any(profile.get('sources', {}).values())


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topics: list[str]
    include: list[str]
    exclude: list[str]
    competitors: list[str]
    people: list[str]
    sources: dict[str, bool]

    @model_validator(mode="after")
    def validate_profile(self):
        for field in RULE_FIELDS:
            values = getattr(self, field)
            cleaned = [" ".join(value.split()) for value in values]
            if any(not value for value in cleaned):
                raise ValueError(f"{field}: blank entries are not allowed")
            if any(len(value) > 100 for value in cleaned):
                raise ValueError(f"{field}: entries must be at most 100 characters")
            if len({value.casefold() for value in cleaned}) != len(cleaned):
                raise ValueError(f"{field}: duplicate entries are not allowed")
            setattr(self, field, cleaned)
        if set(self.sources) != set(SOURCE_KEYS):
            raise ValueError("sources: provide exactly x, web, hn, reddit, github, and rss")
        return self


def empty_profile() -> dict:
    return {
        **{field: [] for field in RULE_FIELDS},
        "sources": {key: True for key in SOURCE_KEYS},
        "schedule_hours": 4,
    }


def load_profile(session: Session) -> dict:
    profile = empty_profile()
    rules = session.execute(text("SELECT kind, value FROM monitor_rule WHERE profile_id = 1 ORDER BY id")).all()
    for kind, value in rules:
        field = next(field for field, rule_kind in RULE_FIELDS.items() if rule_kind == kind)
        profile[field].append(value)
    source_rows = session.execute(text("SELECT source_key, enabled FROM source_config WHERE profile_id = 1")).all()
    for key, enabled in source_rows:
        profile["sources"][key] = enabled
    return profile


def make_router(session_factory: Callable[[], Session]) -> APIRouter:
    router = APIRouter()

    @router.get("/profile")
    def get_profile():
        with session_factory() as session:
            return load_profile(session)

    @router.put("/profile")
    def put_profile(payload: ProfileInput):
        with session_factory.begin() as session:
            session.execute(text("INSERT INTO monitor_profile (id) VALUES (1) ON CONFLICT (id) DO NOTHING"))
            session.execute(text("SELECT id FROM monitor_profile WHERE id = 1 FOR UPDATE"))
            session.execute(text("DELETE FROM monitor_rule WHERE profile_id = 1"))
            for field, kind in RULE_FIELDS.items():
                for value in getattr(payload, field):
                    session.execute(
                        text("INSERT INTO monitor_rule (profile_id, kind, value, normalized_value) "
                             "VALUES (1, :kind, :value, :normalized)"),
                        {"kind": kind, "value": value, "normalized": value.casefold()},
                    )
            session.execute(text("DELETE FROM source_config WHERE profile_id = 1"))
            for key, enabled in payload.sources.items():
                session.execute(
                    text("INSERT INTO source_config (profile_id, source_key, enabled) VALUES (1, :key, :enabled)"),
                    {"key": key, "enabled": enabled},
                )
            session.execute(text("UPDATE monitor_profile SET updated_at = now() WHERE id = 1"))
            has_rules = collection_ready(payload.model_dump())
            has_initial = session.execute(
                text("SELECT EXISTS (SELECT 1 FROM collection_run WHERE trigger = 'initial')")
            ).scalar_one()
            if has_rules and not has_initial:
                snapshot = payload.model_dump()
                session.execute(
                    text("INSERT INTO collection_run (trigger, status, profile_snapshot) "
                         "VALUES ('initial', 'queued', :snapshot)").bindparams(bindparam("snapshot", type_=JSONB())),
                    {"snapshot": snapshot},
                )
            return load_profile(session)

    @router.get("/collection-runs")
    def get_collection_runs():
        with session_factory() as session:
            rows = session.execute(text("SELECT id, trigger, status, scheduled_slot, profile_snapshot, "
                                        "queued_at, started_at, finished_at FROM collection_run "
                                        "ORDER BY queued_at DESC, id DESC LIMIT 50")).mappings().all()
            runs = []
            for row in rows:
                run = dict(row)
                run["sources"] = [dict(item) for item in session.execute(text(
                    "SELECT source_key, status, hit_count, accepted_count, error_count, "
                    "request_count, duration_ms, error_code, error_message, started_at, finished_at "
                    "FROM source_run WHERE run_id = :id ORDER BY source_key"
                ), {"id": run["id"]}).mappings().all()]
                runs.append(run)
            return runs

    return router

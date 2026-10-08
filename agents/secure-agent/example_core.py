"""Pure domain logic for Secure Agent: no file I/O, no network, no LLM.

Compared with example-agent, every note has an owner, every input has a size
limit, and deleting goes through a PendingAction that a person must approve.
All of it is deterministic and unit-testable in isolation.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

MAX_TITLE_LENGTH = 120
MAX_BODY_LENGTH = 2000
MAX_TAGS = 10
MAX_QUERY_LENGTH = 200
MAX_NOTES_PER_DELETE = 10

NOTE_ID = re.compile(r"^note_[0-9a-z]{6,20}$")
USER_ID = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")

_TAG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_HASHTAG = re.compile(r"(?<!\w)#([\w-]+)")


class NotFoundError(LookupError):
    """The record does not exist for this user. Another user's record is reported the same way."""


class ActionStateError(RuntimeError):
    """A pending action cannot make the requested transition (already done, rejected or expired)."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_user_id(user_id: str) -> str:
    if not isinstance(user_id, str) or not USER_ID.match(user_id):
        raise ValueError("User id must be 2–32 lowercase letters, digits, '-' or '_', starting with a letter.")
    return user_id


@dataclass(frozen=True)
class Note:
    id: str
    owner: str
    title: str
    body: str
    tags: Tuple[str, ...]
    created_at: str

    @classmethod
    def create(
        cls,
        owner: str,
        title: str,
        body: str = "",
        tags: Union[str, Iterable[str], None] = None,
    ) -> "Note":
        cleaned_title = (title or "").strip()
        if not cleaned_title:
            raise ValueError("Note title is required.")
        if len(cleaned_title) > MAX_TITLE_LENGTH:
            raise ValueError(f"Note title must be at most {MAX_TITLE_LENGTH} characters.")
        cleaned_body = (body or "").strip()
        if len(cleaned_body) > MAX_BODY_LENGTH:
            raise ValueError(f"Note body must be at most {MAX_BODY_LENGTH} characters.")
        normalized = normalize_tags(tags)
        if len(normalized) > MAX_TAGS:
            raise ValueError(f"A note can have at most {MAX_TAGS} tags.")
        return cls(
            id=f"note_{uuid.uuid4().hex[:10]}",
            owner=validate_user_id(owner),
            title=cleaned_title,
            body=cleaned_body,
            tags=normalized,
            created_at=utc_now(),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Note":
        return cls(
            id=data["id"],
            owner=data["owner"],
            title=data["title"],
            body=data.get("body", ""),
            tags=tuple(data.get("tags", ())),
            created_at=data["created_at"],
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "tags": list(self.tags)}

    def public(self) -> dict:
        """What callers see. The owner is implied by who asked, so it is not echoed back."""
        data = self.to_dict()
        data.pop("owner")
        return data


def normalize_tags(tags: Union[str, Iterable[str], None]) -> Tuple[str, ...]:
    """Accept "a, b" or ["A", "#b"]; return lowercase slugs, deduplicated, in order."""
    if tags is None:
        return ()
    raw = tags.split(",") if isinstance(tags, str) else tags
    slugs = (_TAG_INVALID_CHARS.sub("-", str(t).strip().lstrip("#").lower()).strip("-") for t in raw)
    return tuple(dict.fromkeys(slug for slug in slugs if slug))


def extract_hashtags(text: str) -> Tuple[str, Tuple[str, ...]]:
    """Split "Buy milk #shopping" into ("Buy milk", ("shopping",))."""
    tags = normalize_tags(_HASHTAG.findall(text))
    remaining = " ".join(_HASHTAG.sub("", text).split())
    return remaining, tags


def validate_query(query: str) -> str:
    query = query or ""
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Search text must be at most {MAX_QUERY_LENGTH} characters.")
    return query


def parse_note_ids(note_ids: Union[str, Sequence[str]]) -> List[str]:
    """Accept "note_a, note_b" or a list; reject anything that is not a well-formed id."""
    raw = note_ids.split(",") if isinstance(note_ids, str) else list(note_ids)
    ids = list(dict.fromkeys(str(i).strip() for i in raw if str(i).strip()))
    if not ids:
        raise ValueError("Give at least one note id.")
    if len(ids) > MAX_NOTES_PER_DELETE:
        raise ValueError(f"At most {MAX_NOTES_PER_DELETE} notes can be deleted in one request.")
    bad = [i for i in ids if not NOTE_ID.match(i)]
    if bad:
        raise ValueError(f"Not a note id: {', '.join(bad[:3])}")
    return ids


def score_note(note: Note, terms: Sequence[str]) -> int:
    """Relevance score: title hits weigh most, then tags, then body."""
    title, body = note.title.lower(), note.body.lower()
    score = 0
    for term in terms:
        score += 3 * (term in title) + 2 * (term in note.tags) + (term in body)
    return score


def search_notes(
    notes: Iterable[Note],
    query: str = "",
    *,
    tag: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Note]:
    """Filter by tag, rank by relevance to `query`, newest first on ties."""
    candidates = [n for n in notes if not tag or tag.lower() in n.tags]
    newest_first = sorted(candidates, key=lambda n: n.created_at, reverse=True)

    terms = query.lower().split()
    if terms:
        scored = [(score_note(n, terms), n) for n in newest_first]
        newest_first = [n for s, n in sorted(scored, key=lambda pair: -pair[0]) if s > 0]

    return newest_first[:limit] if limit is not None else newest_first


def tag_counts(notes: Iterable[Note]) -> dict:
    counts = Counter(tag for note in notes for tag in note.tags)
    return dict(counts.most_common())


def summarize_offline(notes: Sequence[Note], *, max_titles: int = 5) -> str:
    """Deterministic summary used when no LLM is available."""
    if not notes:
        return "No notes to summarize."
    latest = sorted(notes, key=lambda n: n.created_at, reverse=True)[:max_titles]
    parts = [f"{len(notes)} note(s)."]
    top_tags = list(tag_counts(notes).items())[:3]
    if top_tags:
        parts.append("Top tags: " + ", ".join(f"#{t} ({c})" for t, c in top_tags) + ".")
    parts.append("Latest: " + "; ".join(n.title for n in latest) + ".")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Pending actions: irreversible work waits for a person
# --------------------------------------------------------------------------- #

ACTION_KINDS = ("delete_notes",)
STATUSES = ("pending", "done", "rejected", "expired")


def payload_digest(kind: str, payload: Mapping[str, Any]) -> str:
    """Fingerprint of exactly what the person is shown. Approval must quote it back."""
    canonical = json.dumps({"kind": kind, "payload": payload}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class PendingAction:
    id: str
    owner: str
    kind: str
    payload: Mapping[str, Any]
    preview: str
    digest: str
    status: str
    created_at: str
    expires_at: str
    decided_at: Optional[str] = None

    @classmethod
    def propose_delete(cls, owner: str, notes: Sequence[Note], *, ttl_seconds: int, now: Optional[datetime] = None) -> "PendingAction":
        if not notes:
            raise ValueError("Nothing to delete.")
        if any(n.owner != owner for n in notes):  # the service checks first; this keeps the core honest
            raise NotFoundError("Note not found.")
        now = now or datetime.now(timezone.utc)
        payload = {"notes": [{"id": n.id, "title": n.title} for n in notes]}
        titles = ", ".join(f"'{n.title}'" for n in notes)
        return cls(
            id=f"act_{uuid.uuid4().hex[:12]}",
            owner=owner,
            kind="delete_notes",
            payload=payload,
            preview=f"Delete {len(notes)} note(s): {titles}",
            digest=payload_digest("delete_notes", payload),
            status="pending",
            created_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds"),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PendingAction":
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)

    def public(self) -> dict:
        data = self.to_dict()
        data.pop("owner")
        return data

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now >= datetime.fromisoformat(self.expires_at)

    def check_approvable(self, digest: str, now: Optional[datetime] = None) -> None:
        """Raise unless this action can run now with exactly the content the person saw."""
        if self.status != "pending":
            raise ActionStateError(f"Action is already {self.status}.")
        if self.is_expired(now):
            raise ActionStateError("Action has expired; ask the agent again.")
        if digest != self.digest:
            raise ActionStateError("The action changed after it was shown; review it again.")

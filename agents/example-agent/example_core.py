"""Pure domain logic for Example Agent: no file I/O, no network, no LLM.

This is the module you replace when copying the template for a new domain.
Everything here is deterministic and unit-testable in isolation.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

MAX_TITLE_LENGTH = 120

_TAG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_HASHTAG = re.compile(r"(?<!\w)#([\w-]+)")


class NotFoundError(LookupError):
    """Raised when a requested record does not exist."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    body: str
    tags: Tuple[str, ...]
    created_at: str

    @classmethod
    def create(
        cls,
        title: str,
        body: str = "",
        tags: Union[str, Iterable[str], None] = None,
    ) -> "Note":
        cleaned_title = (title or "").strip()
        if not cleaned_title:
            raise ValueError("Note title is required.")
        if len(cleaned_title) > MAX_TITLE_LENGTH:
            raise ValueError(f"Note title must be at most {MAX_TITLE_LENGTH} characters.")
        return cls(
            id=f"note_{uuid.uuid4().hex[:10]}",
            title=cleaned_title,
            body=(body or "").strip(),
            tags=normalize_tags(tags),
            created_at=utc_now(),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Note":
        return cls(
            id=data["id"],
            title=data["title"],
            body=data.get("body", ""),
            tags=tuple(data.get("tags", ())),
            created_at=data["created_at"],
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "tags": list(self.tags)}


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
        # sorted() is stable, so equal scores keep newest-first order.
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

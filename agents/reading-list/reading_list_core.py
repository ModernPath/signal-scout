"""Pure domain logic for Reading List: no file I/O, no network, no LLM.

Everything here is deterministic and unit-testable in isolation.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

MAX_NOTE_LENGTH = 500

_TAG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_HASHTAG = re.compile(r"(?<!\w)#([\w-]+)")

Tags = Union[str, Iterable[str], None]


class NotFoundError(LookupError):
    """Raised when a requested record does not exist."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_tags(tags: Tags) -> Tuple[str, ...]:
    """Accept "a, b" or ["A", "#b"]; return lowercase slugs, deduplicated, in order."""
    if tags is None:
        return ()
    raw = tags.split(",") if isinstance(tags, str) else tags
    slugs = (_TAG_INVALID_CHARS.sub("-", str(t).strip().lstrip("#").lower()).strip("-") for t in raw)
    return tuple(dict.fromkeys(slug for slug in slugs if slug))


def extract_hashtags(text: str) -> Tuple[str, Tuple[str, ...]]:
    """Split "Some note #dev" into ("Some note", ("dev",))."""
    tags = normalize_tags(_HASHTAG.findall(text))
    remaining = " ".join(_HASHTAG.sub("", text).split())
    return remaining, tags


def validate_url(url: Optional[str]) -> str:
    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL must be a valid http(s) address.")
    return cleaned


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    url: str
    note: str
    tags: Tuple[str, ...]
    added_at: str
    read_at: Optional[str] = None

    @classmethod
    def create(
        cls,
        title: Optional[str],
        url: Optional[str],
        note: Optional[str] = "",
        tags: Tags = None,
    ) -> "Item":
        cleaned_title = (title or "").strip()
        if not cleaned_title:
            raise ValueError("Title is required.")
        cleaned_url = validate_url(url)
        cleaned_note = (note or "").strip()
        if len(cleaned_note) > MAX_NOTE_LENGTH:
            raise ValueError(f"Note must be at most {MAX_NOTE_LENGTH} characters.")
        return cls(
            id=f"item_{uuid.uuid4().hex[:10]}",
            title=cleaned_title,
            url=cleaned_url,
            note=cleaned_note,
            tags=normalize_tags(tags),
            added_at=utc_now(),
            read_at=None,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Item":
        return cls(
            id=data["id"],
            title=data["title"],
            url=data["url"],
            note=data.get("note", "") or "",
            tags=tuple(data.get("tags", ())),
            added_at=data["added_at"],
            read_at=data.get("read_at"),
        )

    def to_dict(self) -> dict:
        return {**asdict(self), "tags": list(self.tags)}

    def with_tags(self, tags: Tags) -> "Item":
        """Merge new tags; raise ValueError if they normalize to nothing."""
        new = normalize_tags(tags)
        if not new:
            raise ValueError("No valid tags given.")
        return replace(self, tags=tuple(dict.fromkeys([*self.tags, *new])))

    def mark_read(self, when: Optional[str] = None) -> "Item":
        return self if self.read_at else replace(self, read_at=when or utc_now())


def tag_counts(items: Iterable[Item]) -> Dict[str, int]:
    counts = Counter(tag for item in items for tag in item.tags)
    return dict(counts.most_common())


def filter_items(
    items: Iterable[Item], *, unread: bool = False, tag: Optional[str] = None
) -> List[Item]:
    """Newest `added_at` first, optionally unread-only and/or restricted to one tag."""
    wanted = normalize_tags([tag]) if tag else ()
    if tag and not wanted:
        raise ValueError("tag has no usable characters")
    kept = [
        i for i in items
        if (not unread or not i.read_at) and (not wanted or wanted[0] in i.tags)
    ]
    return sorted(kept, key=lambda i: (i.added_at, i.id), reverse=True)


def read_next(items: Sequence[Item], *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Unread items ranked by tag boost (sum of each tag's list-wide usage count),
    ties broken by oldest `added_at`, then id."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    counts = tag_counts(items)
    scored = [(sum(counts[t] for t in i.tags), i) for i in items if not i.read_at]
    scored.sort(key=lambda pair: (-pair[0], pair[1].added_at, pair[1].id))
    ranking = []
    for position, (boost, item) in enumerate(scored, start=1):
        added = f"added {item.added_at[:10]}"
        if boost:
            reason = "tags " + ", ".join(f"{t} ({counts[t]})" for t in item.tags) + f"; {added}"
        else:
            reason = f"no tag boost; {added}"
        ranking.append({**item.to_dict(), "rank": position, "tag_boost": boost, "reason": reason})
    return ranking[:limit] if limit is not None else ranking


def summarize(items: Sequence[Item]) -> Dict[str, Any]:
    unread = sum(1 for i in items if not i.read_at)
    return {
        "total": len(items),
        "unread": unread,
        "read": len(items) - unread,
        "tags": tag_counts(items),
    }

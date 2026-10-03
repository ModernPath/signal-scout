"""Hacker News source adapter."""

from ..adapters import _candidate, _date, _invalid_linked_item, _terms
from ..collection import SourceResult

def collect(snapshot: dict, budget: int, http) -> SourceResult:
    if not _terms(snapshot):
        return SourceResult()
    base = "https://hacker-news.firebaseio.com/v0"
    ids = http.get_json(f"{base}/newstories.json")
    requests = 1
    items = []
    rejected = 0
    comments = []
    for item_id in ids[: min(12, max(0, budget - requests))]:
        record = http.get_json(f"{base}/item/{item_id}.json") or {}
        requests += 1
        if record.get("dead") or record.get("deleted") or record.get("type") != "story":
            continue
        source_url = f"https://news.ycombinator.com/item?id={item_id}"
        candidate = _candidate("hn", item_id, source_url, record.get("url"),
                               record.get("title"), record.get("text"), _date(record.get("time")),
                               "points", record.get("score"), snapshot)
        if candidate:
            items.append(candidate)
        elif _invalid_linked_item(source_url, record.get("title")):
            rejected += 1
        comments.extend((child, record.get("title")) for child in (record.get("kids") or [])[:2])
    for child_id, parent_title in comments[:max(0, budget - requests)]:
        record = http.get_json(f"{base}/item/{child_id}.json") or {}
        requests += 1
        if record.get("dead") or record.get("deleted") or record.get("type") != "comment":
            continue
        url = f"https://news.ycombinator.com/item?id={child_id}"
        candidate = _candidate("hn", child_id, url, url,
                               f"Comment on: {parent_title}", record.get("text"),
                               _date(record.get("time")), None, None, snapshot)
        if candidate:
            items.append(candidate)
        elif _invalid_linked_item(url, f"Comment on: {parent_title}"):
            rejected += 1
    return SourceResult(items=items, hit_count=requests - 1, request_count=requests,
                        rejected_count=rejected)

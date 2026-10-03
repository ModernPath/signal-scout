"""Xai source adapter."""

import json
import re
from urllib.parse import urlsplit
from ..adapters import _candidate, _date, _page_text, _public_feed_url, _terms
from ..collection import SourceResult, SourceUnavailable
from ..feed import canonical_url, safe_http_url


def _citation_identity(url: str, source: str) -> str:
    if source == "x" and urlsplit(url).hostname in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        match = re.search(r"/status/(\d+)(?:/|$)", urlsplit(url).path)
        if match:
            return "x-status:" + match.group(1)
    return canonical_url(url)


def collect(source: str, snapshot: dict, budget: int, env, http) -> SourceResult:
    key = env.get("XAIGROK_API_KEY")
    if not key:
        raise SourceUnavailable("missing_xai_key")
    terms = _terms(snapshot)[:3]
    if not terms or budget < 1:
        return SourceResult()
    schema = {"type": "object", "additionalProperties": False, "required": ["items"],
        "properties": {"items": {"type": "array", "items": {"type": "object",
            "additionalProperties": False,
            "required": ["url", "title", "snippet", "published_at", "engagement"],
            "properties": {"url": {"type": "string"}, "title": {"type": "string"},
                "snippet": {"type": "string"}, "published_at": {"type": ["string", "null"]},
                "engagement": {"type": ["integer", "null"]}}}}}}
    prompt = ("Use " + ("X Search to find up to five individual recent public posts" if source == "x"
                         else "Web Search to find up to five recent articles")
              + " matching: " + "; ".join(terms)
              + (f". Prefer items since {_date(snapshot.get('_since')).date().isoformat()}" if _date(snapshot.get("_since")) else "")
              + (". Return each direct x.com status URL and the post text as its snippet. "
                 if source == "x" else ". Return each article's original source URL and a useful snippet. ")
              + "Use only real source items found by the search tool. Do not invent URLs or engagement.")
    response = http.post_json("https://api.x.ai/v1/responses", {
        "model": "grok-4.7", "input": [{"role": "user", "content": prompt}],
        "reasoning": {"effort": "low"},
        "tools": [{"type": "x_search" if source == "x" else "web_search"}],
        "max_tool_calls": min(2, budget), "max_output_tokens": 1200,
        "text": {"format": {"type": "json_schema", "name": "source_items",
                            "schema": schema, "strict": True}},
    }, headers={"Authorization": f"Bearer {key}"})
    output_parts = [content for message in response.get("output", [])
                    if message.get("type") == "message"
                    for content in message.get("content", []) if content.get("type") == "output_text"]
    citation_urls = list(response.get("citations") or [])
    citation_urls.extend(annotation.get("url") for part in output_parts
                         for annotation in part.get("annotations") or []
                         if annotation.get("type") == "url_citation")
    citations = {_citation_identity(url, source) for url in citation_urls if safe_http_url(url)}
    output_text = output_parts[0].get("text") if output_parts else None
    data = json.loads(output_text or "{}")
    records = data.get("items", []) if isinstance(data, dict) else []
    items = []
    page_fetches = 0
    rejected = max(0, len(records) - 5)
    for record in records[:5]:
        url = safe_http_url(record.get("url"))
        if not url or _citation_identity(url, source) not in citations:
            rejected += 1
            continue
        if source == "x" and urlsplit(url).hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
            rejected += 1
            continue
        snippet = record.get("snippet")
        if source == "web" and page_fetches < min(2, budget - 1) and _public_feed_url(url):
            page_fetches += 1
            try:
                extracted = _page_text(http.get_public_text(url))
                if extracted:
                    snippet = extracted
            except Exception:
                pass  # A cited search result can remain useful when page retrieval fails.
        candidate = _candidate(source, url, url, url, record.get("title"),
            snippet, _date(record.get("published_at")),
            "likes" if source == "x" else None,
            record.get("engagement") if source == "x" else None, snapshot)
        if candidate:
            items.append(candidate)
        else:
            rejected += 1
    return SourceResult(items=items, hit_count=len(records), request_count=1 + page_fetches,
                        rejected_count=rejected)

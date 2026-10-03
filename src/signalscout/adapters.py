"""Bounded public source adapters; external HTTP stays behind one transport."""

import html
import ipaddress
import json
import os
import re
import socket
from http.client import HTTPConnection, HTTPSConnection
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .collection import SourceRateLimited, SourceTransientError, SourceUnavailable
from .feed import safe_http_url


USER_AGENT = "SignalScout/0.1 (local single-operator monitoring)"
MAX_RESPONSE_BYTES = 2_000_000


class HttpTransport:
    def _request(self, url: str, *, headers: dict | None = None,
                 data: bytes | None = None) -> bytes:
        request = Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            with urlopen(request, timeout=75 if urlsplit(url).hostname == "api.x.ai" else 10) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("Provider response too large")
                return body
        except HTTPError as error:
            if error.code == 429 or (error.code == 403 and error.headers.get("X-RateLimit-Remaining") == "0"):
                raise SourceRateLimited() from None
            if error.code in {500, 502, 503, 504}:
                raise SourceTransientError() from None
            if error.code in {401, 403}:
                raise SourceUnavailable("provider_access_rejected") from None
            raise ValueError("Provider request rejected") from None
        except URLError:
            raise SourceTransientError() from None

    def get_json(self, url: str, *, headers: dict | None = None):
        return json.loads(self._request(url, headers=headers))

    def get_text(self, url: str, *, headers: dict | None = None):
        return self._request(url, headers=headers).decode("utf-8", errors="replace")

    def get_public_text(self, url: str):
        if not _public_feed_url(url):
            raise SourceUnavailable("rss_url_not_public")
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
            raise SourceUnavailable("rss_url_not_public")
        pinned_address = addresses[0][4][0]
        connection = (HTTPSConnection if parsed.scheme == "https" else HTTPConnection)(host, port, timeout=10)
        connection._create_connection = lambda _target, timeout, source_address: socket.create_connection(
            (pinned_address, port), timeout, source_address)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        try:
            connection.request("GET", target, headers={"User-Agent": USER_AGENT})
            response = connection.getresponse()
            if response.status >= 300:
                raise ValueError("External page response rejected")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("Provider response too large")
            return body.decode("utf-8", errors="replace")
        finally:
            connection.close()

    def post_json(self, url: str, payload: dict, *, headers: dict | None = None):
        return json.loads(self._request(url, data=json.dumps(payload).encode(),
                                        headers={"Content-Type": "application/json", **(headers or {})}))

    def post_form(self, url: str, payload: dict, *, headers: dict | None = None):
        return json.loads(self._request(url, data=urlencode(payload).encode(),
                                        headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})}))


def _clean(value) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", str(value or ""))).split())


def _invalid_linked_item(url, title) -> bool:
    return safe_http_url(url) is None or not _clean(title)


class _PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.article = []
        self.body = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack)-1-self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if any(tag in self.stack for tag in ("script", "style", "nav", "header", "footer")):
            return
        if "article" in self.stack:
            self.article.append(data)
        if "body" in self.stack:
            self.body.append(data)


def _page_text(document: str) -> str:
    parser = _PageText()
    parser.feed(document)
    return _clean(" ".join(parser.article or parser.body))[:2000]


def _terms(snapshot: dict) -> list[str]:
    result = []
    for field in ("topics", "include", "competitors", "people"):
        for term in snapshot.get(field, []):
            if isinstance(term, str) and term.strip() and term.casefold() not in [v.casefold() for v in result]:
                result.append(term.strip())
    return result[:12]


def _matches(title: str, snippet: str, snapshot: dict) -> tuple[list[str], list[str]] | None:
    haystack = f"{title} {snippet}".casefold()
    if any(term.casefold() in haystack for term in snapshot.get("exclude", [])):
        return None
    matching = [term for term in _terms(snapshot) if term.casefold() in haystack]
    if not matching:
        return None
    topics = [topic for topic in snapshot.get("topics", []) if topic.casefold() in haystack]
    return topics, matching


def _date(value) -> datetime | None:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            try:
                return parsedate_to_datetime(value).astimezone(timezone.utc)
            except (TypeError, ValueError):
                return None
    return None


def _candidate(source: str, external_id: str, source_url: str, content_url: str | None,
               title: str, snippet: str, published_at: datetime | None, metric_name: str | None,
               metric_value: int | None, snapshot: dict) -> dict | None:
    source_url = safe_http_url(source_url)
    if not source_url:
        return None
    title, snippet = _clean(title)[:500], _clean(snippet)[:4000]
    match = _matches(title, snippet, snapshot)
    if not title or match is None:
        return None
    since = _date(snapshot.get("_since"))
    if since and published_at and published_at < since - timedelta(hours=1):
        return None
    topics, matched_terms = match
    return {"source_key": source, "external_id": str(external_id), "source_url": source_url,
            "content_url": safe_http_url(content_url) or source_url, "title": title,
            "snippet": snippet, "published_at": published_at, "metric_name": metric_name,
            "metric_value": metric_value if isinstance(metric_value, int) and metric_value >= 0 else None,
            "topics": topics, "matched_terms": matched_terms}


def _public_feed_url(url: str) -> bool:
    clean = safe_http_url(url)
    if not clean:
        return False
    host = urlsplit(clean).hostname
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def build_adapters(environment: Mapping[str, str] | None = None,
                   transport: HttpTransport | None = None):
    """Bind each isolated source adapter to its environment and HTTP transport."""
    from .sources import github, hacker_news, reddit, rss, xai

    env = os.environ if environment is None else environment
    http = transport or HttpTransport()
    return {
        "hn": lambda snapshot, budget: hacker_news.collect(snapshot, budget, http),
        "github": lambda snapshot, budget: github.collect(snapshot, budget, env, http),
        "rss": lambda snapshot, budget: rss.collect(snapshot, budget, env, http),
        "x": lambda snapshot, budget: xai.collect("x", snapshot, budget, env, http),
        "web": lambda snapshot, budget: xai.collect("web", snapshot, budget, env, http),
        "reddit": lambda snapshot, budget: reddit.collect(snapshot, budget, env, http),
    }

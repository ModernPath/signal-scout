"""Rss source adapter."""

from xml.etree import ElementTree
from ..adapters import _candidate, _date, _invalid_linked_item, _public_feed_url
from ..collection import SourceResult, SourceUnavailable

def collect(snapshot: dict, budget: int, env, http) -> SourceResult:
    urls = [url.strip() for url in env.get("RSS_FEED_URLS", "").split(",") if url.strip()][:3]
    if not urls:
        raise SourceUnavailable("no_rss_feeds")
    items, requests, hits, rejected = [], 0, 0, 0
    for url in urls[:budget]:
        if not _public_feed_url(url):
            raise SourceUnavailable("rss_url_not_public")
        root = ElementTree.fromstring(http.get_public_text(url))
        requests += 1
        entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in entries[:20]:
            def field(name):
                return entry.findtext(name) or entry.findtext("{http://www.w3.org/2005/Atom}" + name)
            link = field("link")
            if not link:
                atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
                link = atom_link.get("href") if atom_link is not None else None
            hits += 1
            candidate = _candidate("rss", field("guid") or field("id") or link,
                link, link, field("title"), field("description") or field("summary"),
                _date(field("pubDate") or field("updated") or field("published")),
                None, None, snapshot)
            if candidate:
                items.append(candidate)
            elif _invalid_linked_item(link, field("title")):
                rejected += 1
    return SourceResult(items=items, hit_count=hits, request_count=requests,
                        rejected_count=rejected)

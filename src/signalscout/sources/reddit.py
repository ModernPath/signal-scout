"""Reddit source adapter."""

import base64
from urllib.parse import urlencode
from ..adapters import _candidate, _date, _invalid_linked_item, _terms
from ..collection import SourceResult, SourceUnavailable

def collect(snapshot: dict, budget: int, env, http) -> SourceResult:
    if (env.get("REDDIT_APPROVED_ACCESS") != "true" or not env.get("REDDIT_CLIENT_ID")
            or not env.get("REDDIT_CLIENT_SECRET") or not env.get("REDDIT_USER_AGENT")):
        raise SourceUnavailable("reddit_access_unavailable")
    credentials = base64.b64encode((env["REDDIT_CLIENT_ID"] + ":" + env["REDDIT_CLIENT_SECRET"]).encode()).decode()
    token = http.post_form("https://www.reddit.com/api/v1/access_token",
        {"grant_type": "client_credentials"}, headers={
            "Authorization": f"Basic {credentials}", "User-Agent": env["REDDIT_USER_AGENT"]}).get("access_token")
    if not token:
        raise SourceUnavailable("reddit_token_unavailable")
    headers = {"Authorization": f"Bearer {token}", "User-Agent": env["REDDIT_USER_AGENT"]}
    items, requests, hits, rejected = [], 1, 0, 0
    for term in _terms(snapshot)[:2]:
        if requests >= budget:
            break
        url = "https://oauth.reddit.com/search.json?" + urlencode(
            {"q": term, "sort": "new", "limit": 10, "raw_json": 1})
        records = http.get_json(url, headers=headers).get("data", {}).get("children", [])[:10]
        requests += 1
        hits += len(records)
        for record in records:
            data = record.get("data", {})
            permalink = data.get("permalink")
            source_url = "https://www.reddit.com" + permalink if isinstance(permalink, str) and permalink.startswith("/") else None
            candidate = _candidate("reddit", data.get("name") or data.get("id"), source_url,
                data.get("url"), data.get("title"), data.get("selftext"),
                _date(data.get("created_utc")), "upvotes", data.get("score"), snapshot)
            if candidate:
                items.append(candidate)
            elif _invalid_linked_item(source_url, data.get("title")):
                rejected += 1
            if requests >= budget or not data.get("id"):
                continue
            comments = http.get_json(f"https://oauth.reddit.com/comments/{data['id']}.json?limit=5&raw_json=1",
                                     headers=headers)
            requests += 1
            for comment in (comments[1].get("data", {}).get("children", []) if isinstance(comments, list) and len(comments) > 1 else [])[:5]:
                body = comment.get("data", {})
                if comment.get("kind") != "t1":
                    continue
                hits += 1
                comment_url = "https://www.reddit.com" + body.get("permalink", "")
                item = _candidate("reddit", body.get("name") or body.get("id"), comment_url,
                    comment_url, f"Comment on: {data.get('title')}", body.get("body"),
                    _date(body.get("created_utc")), "upvotes", body.get("score"), snapshot)
                if item:
                    items.append(item)
                elif _invalid_linked_item(comment_url, f"Comment on: {data.get('title')}"):
                    rejected += 1
    return SourceResult(items=items, hit_count=hits, request_count=requests,
                        rejected_count=rejected)

"""Github source adapter."""

from urllib.parse import quote
from ..adapters import _candidate, _date, _invalid_linked_item, _terms
from ..collection import SourceRateLimited, SourceResult, SourceTransientError, SourceUnavailable

def collect(snapshot: dict, budget: int, env, http) -> SourceResult:
    terms = _terms(snapshot)[:2]
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if env.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {env['GITHUB_TOKEN']}"
    items, requests, hits, rejected = [], 0, 0, 0
    repositories = []
    for term in terms:
        for kind in ("repositories", "issues"):
            if requests >= budget:
                break
            since = _date(snapshot.get("_since"))
            cursor = (f" {'updated' if kind == 'issues' else 'pushed'}:>={since.date().isoformat()}"
                      if since else "")
            q = quote(term + (" is:issue" if kind == "issues" else "") + cursor)
            url = f"https://api.github.com/search/{kind}?q={q}&sort=updated&order=desc&per_page=10"
            records = http.get_json(url, headers=headers).get("items", [])[:10]
            requests += 1
            hits += len(records)
            for record in records:
                is_repo = kind == "repositories"
                if is_repo and isinstance(record.get("full_name"), str):
                    repositories.append(record["full_name"])
                candidate = _candidate("github", f"{kind}:{record.get('id')}",
                    record.get("html_url"), record.get("html_url"),
                    record.get("full_name") if is_repo else record.get("title"),
                    record.get("description") if is_repo else record.get("body"),
                    _date(record.get("pushed_at") if is_repo else record.get("created_at")),
                    "stars" if is_repo else "comments",
                    record.get("stargazers_count") if is_repo else record.get("comments"), snapshot)
                if candidate:
                    items.append(candidate)
                elif _invalid_linked_item(record.get("html_url"),
                                          record.get("full_name") if is_repo else record.get("title")):
                    rejected += 1
    if env.get("GITHUB_TOKEN"):
        query = ("query($owner:String!, $name:String!){repository(owner:$owner,name:$name){"
                 "discussions(first:5,orderBy:{field:UPDATED_AT,direction:DESC}){"
                 "nodes{id title bodyText url createdAt upvoteCount}}}}")
        for full_name in repositories[:2]:
            if requests >= budget or "/" not in full_name:
                break
            owner, name = full_name.split("/", 1)
            requests += 1
            try:
                response = http.post_json("https://api.github.com/graphql",
                    {"query": query, "variables": {"owner": owner, "name": name}}, headers=headers)
            except (TimeoutError, SourceRateLimited, SourceTransientError, SourceUnavailable, ValueError):
                rejected += 1
                continue  # Optional discussion lookup cannot discard REST results.
            nodes = (((response.get("data") or {}).get("repository") or {}).get("discussions") or {}).get("nodes") or []
            hits += len(nodes)
            for record in nodes[:5]:
                candidate = _candidate("github", f"discussion:{record.get('id')}",
                    record.get("url"), record.get("url"), record.get("title"),
                    record.get("bodyText"), _date(record.get("createdAt")),
                    "upvotes", record.get("upvoteCount"), snapshot)
                if candidate:
                    items.append(candidate)
                elif _invalid_linked_item(record.get("url"), record.get("title")):
                    rejected += 1
    return SourceResult(items=items, hit_count=hits, request_count=requests,
                        rejected_count=rejected)

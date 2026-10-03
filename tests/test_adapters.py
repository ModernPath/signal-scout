"""Provider adapters use only fixture transport responses in normal tests."""

from urllib.error import HTTPError

import pytest

from signalscout.collection import SourceUnavailable


PROFILE = {"topics": ["AI agents"], "include": [], "exclude": ["jobs"],
           "competitors": [], "people": [], "sources": {}}


class FixtureTransport:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, headers=None):
        self.calls.append(url)
        if url.endswith("/newstories.json"):
            return [101]
        if url.endswith("/item/101.json"):
            return {"id": 101, "type": "story", "title": "AI agents in production",
                    "url": "https://example.org/story", "time": 1790670000, "score": 42,
                    "text": "Useful details", "kids": [102]}
        if url.endswith("/item/102.json"):
            return {"id": 102, "type": "comment", "text": "AI agents need review",
                    "time": 1790670100, "parent": 101}
        if "/search/repositories?" in url:
            return {"items": [{"id": 7, "full_name": "owner/ai-agents", "html_url": "https://github.com/owner/ai-agents",
                               "description": "AI agents toolkit", "pushed_at": "2026-09-29T08:00:00Z", "stargazers_count": 12}]}
        if "/search/issues?" in url:
            return {"items": [{"id": 8, "title": "AI agents issue", "html_url": "https://github.com/owner/repo/issues/1",
                               "body": "A useful AI agents issue", "created_at": "2026-09-29T09:00:00Z",
                               "comments": 2}]}
        raise AssertionError(url)

    def get_text(self, url, *, headers=None):
        self.calls.append(url)
        return """<rss><channel><item><guid>entry-1</guid><title>AI agents today</title>
        <link>https://example.org/rss-story</link><description>Useful AI agents news</description>
        <pubDate>Tue, 29 Sep 2026 09:00:00 GMT</pubDate></item></channel></rss>"""

    def get_public_text(self, url):
        return self.get_text(url)

    def post_json(self, url, payload, *, headers=None):
        self.calls.append(url)
        return {"citations": ["https://x.com/user/status/123"], "output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"items":[{"url":"https://x.com/user/status/123","title":"AI agents update","snippet":"Actual cited post","published_at":"2026-09-29T09:00:00Z","engagement":4},{"url":"https://invented.example/fake","title":"Fake answer","snippet":"AI narrative","published_at":null,"engagement":0}]}'}]}]}


def test_hn_and_github_and_rss_normalize_real_items_with_budgets():
    from signalscout.adapters import build_adapters

    transport = FixtureTransport()
    adapters = build_adapters({"RSS_FEED_URLS": "https://feeds.example.org/news.xml"}, transport)
    hn = adapters["hn"](PROFILE, 8)
    github = adapters["github"](PROFILE, 8)
    rss = adapters["rss"](PROFILE, 8)
    assert {item["source_key"] for item in hn.items} == {"hn"}
    assert len(hn.items) == 2  # story and matching comment
    assert len(github.items) == 2  # repository and issue
    assert len(rss.items) == 1
    assert all(item["source_url"].startswith("https://") for result in (hn, github, rss) for item in result.items)
    assert all(result.request_count <= 8 for result in (hn, github, rss))


def test_xai_accepts_only_items_with_actual_tool_citations():
    from signalscout.adapters import build_adapters

    adapters = build_adapters({"XAIGROK_API_KEY": "placeholder"}, FixtureTransport())
    result = adapters["x"](PROFILE, 2)
    assert len(result.items) == 1
    assert result.items[0]["source_url"] == "https://x.com/user/status/123"
    assert result.items[0]["source_key"] == "x"
    assert result.rejected_count == 1


def test_xai_discovery_uses_low_reasoning_for_bounded_search_latency():
    from signalscout.adapters import build_adapters
    class SearchTransport(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            assert payload.get('reasoning') == {'effort':'low'}
            return super().post_json(url,payload,headers=headers)
    result=build_adapters({'XAIGROK_API_KEY':'placeholder'},SearchTransport())['x'](PROFILE,2)
    assert len(result.items) == 1


def test_unapproved_reddit_and_missing_rss_are_unavailable():
    from signalscout.adapters import build_adapters

    adapters = build_adapters({}, FixtureTransport())
    for source in ("reddit", "rss", "x", "web"):
        try:
            adapters[source](PROFILE, 2)
        except SourceUnavailable:
            pass
        else:
            raise AssertionError(f"{source} should be unavailable")


def test_incremental_cursor_limits_github_queries_and_old_feed_items():
    from signalscout.adapters import build_adapters

    transport = FixtureTransport()
    adapters = build_adapters({"RSS_FEED_URLS": "https://feeds.example.org/news.xml"}, transport)
    snapshot = {**PROFILE, "_since": "2026-09-30T00:00:00+00:00"}
    adapters["github"](snapshot, 4)
    assert any("updated%3A%3E%3D2026-09-30" in url for url in transport.calls)
    assert adapters["rss"](snapshot, 2).items == []


def test_http_transport_classifies_rate_limit_and_transient_status(monkeypatch):
    from signalscout.adapters import HttpTransport
    from signalscout.collection import SourceRateLimited, SourceTransientError
    from signalscout import adapters

    def fail_429(*_, **__):
        raise HTTPError('https://api.github.com/search/issues', 429, 'secret provider body', {}, None)
    monkeypatch.setattr(adapters, 'urlopen', fail_429)
    with pytest.raises(SourceRateLimited):
        HttpTransport().get_json('https://api.github.com/search/issues')

    def fail_503(*_, **__):
        raise HTTPError('https://api.github.com/search/issues', 503, 'secret provider body', {}, None)
    monkeypatch.setattr(adapters, 'urlopen', fail_503)
    with pytest.raises(SourceTransientError):
        HttpTransport().get_json('https://api.github.com/search/issues')


def test_web_fetches_bounded_page_text_only_for_cited_public_url():
    from signalscout.adapters import build_adapters

    class WebFixture(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            self.calls.append(url)
            return {"citations": ["https://example.org/article"], "output": [{"type": "message", "content": [
                {"type": "output_text", "text": '{"items":[{"url":"https://example.org/article","title":"AI agents report","snippet":"Short summary","published_at":"2026-09-29T09:00:00Z","engagement":null},{"url":"http://127.0.0.1/private","title":"AI agents private","snippet":"Do not fetch","published_at":null,"engagement":null}]}'}]}]}
        def get_public_text(self, url):
            self.calls.append(url)
            return '<html><body><nav>Navigation</nav><article><h1>AI agents report</h1><p>Specific field observations from the source article.</p></article><script>dangerous()</script></body></html>'

    transport=WebFixture()
    result=build_adapters({"XAIGROK_API_KEY":"placeholder"},transport)["web"](PROFILE,2)
    assert len(result.items)==1
    assert "Specific field observations" in result.items[0]["snippet"]
    assert "dangerous" not in result.items[0]["snippet"]
    assert transport.calls == ["https://api.x.ai/v1/responses", "https://example.org/article"]


def test_github_token_adds_public_discussions_within_budget():
    from signalscout.adapters import build_adapters

    class GitHubFixture(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            self.calls.append(url)
            assert url == "https://api.github.com/graphql"
            return {"data":{"repository":{"discussions":{"nodes":[{
                "id":"discussion-1", "title":"AI agents discussion",
                "bodyText":"Community thoughts about AI agents", "url":"https://github.com/owner/ai-agents/discussions/1",
                "createdAt":"2026-09-29T09:00:00Z", "upvoteCount":3}]}}}}

    transport=GitHubFixture()
    result=build_adapters({"GITHUB_TOKEN":"placeholder"},transport)["github"](PROFILE,6)
    assert len(result.items)==3
    assert any("/discussions/1" in item["source_url"] for item in result.items)
    assert result.request_count<=6


def test_xai_search_allows_longer_bounded_http_response(monkeypatch):
    from signalscout.adapters import HttpTransport
    from signalscout import adapters

    timeouts=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*_): return False
        def read(self,*_): return b'{}'
    def open_request(request, *, timeout):
        timeouts.append(timeout)
        return Response()
    monkeypatch.setattr(adapters,'urlopen',open_request)
    HttpTransport().get_json('https://api.x.ai/v1/responses')
    assert 60 <= timeouts[0] <= 90


def test_xai_raw_responses_uses_output_annotations_as_citation_proof():
    from signalscout.adapters import build_adapters

    class AnnotationFixture(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            response=super().post_json(url,payload,headers=headers)
            response.pop('citations')
            response['output'][0]['content'][0]['annotations']=[
                {'type':'url_citation','url':'https://x.com/user/status/123'}]
            return response

    result=build_adapters({'XAIGROK_API_KEY':'placeholder'},AnnotationFixture())['x'](PROFILE,2)
    assert len(result.items)==1
    assert result.rejected_count==1


def test_optional_github_discussion_failure_keeps_repositories_and_issues():
    from signalscout.adapters import build_adapters

    class DiscussionFailure(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            raise TimeoutError('GraphQL timed out')

    result=build_adapters({'GITHUB_TOKEN':'placeholder'},DiscussionFailure())['github'](PROFILE,6)
    assert len(result.items)==2
    assert result.rejected_count==1


def test_xai_limits_server_side_tool_calls():
    from signalscout.adapters import build_adapters

    class BudgetFixture(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            assert 1 <= payload['max_tool_calls'] <= 2
            assert payload['max_output_tokens'] <= 2000
            return super().post_json(url,payload,headers=headers)

    build_adapters({'XAIGROK_API_KEY':'placeholder'},BudgetFixture())['x'](PROFILE,2)


def test_xai_matches_same_post_id_across_x_citation_url_forms():
    from signalscout.adapters import build_adapters

    class StatusCitationFixture(FixtureTransport):
        def post_json(self, url, payload, *, headers=None):
            response=super().post_json(url,payload,headers=headers)
            response['citations']=['https://x.com/i/status/123']
            return response

    result=build_adapters({'XAIGROK_API_KEY':'placeholder'},StatusCitationFixture())['x'](PROFILE,2)
    assert len(result.items)==1


def test_public_page_fetch_pins_validated_dns_address(monkeypatch):
    from signalscout import adapters

    connections = []
    monkeypatch.setattr(adapters.socket, 'getaddrinfo', lambda *_args, **_kwargs:
                        [(None, None, None, None, ('93.184.215.14', 443))])
    def connect(address, timeout, source_address):
        connections.append(address)
        return object()
    monkeypatch.setattr(adapters.socket, 'create_connection', connect)

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def read(self, _limit): return b'<html><body>Public page</body></html>'
    class Connection:
        def __init__(self, host, port, **_kwargs):
            assert (host, port) == ('example.org', 443)
        def request(self, method, path, headers):
            assert (method, path) == ('GET', '/article')
            self._create_connection(('example.org', 443), 10, None)
        def getresponse(self): return Response()
        def close(self): pass
    monkeypatch.setattr(adapters, 'HTTPSConnection', Connection, raising=False)
    assert adapters.HttpTransport().get_public_text('https://example.org/article') == '<html><body>Public page</body></html>'
    assert connections == [('93.184.215.14', 443)]


def test_malformed_provider_hits_are_counted_as_rejected():
    from signalscout.adapters import build_adapters

    class MalformedTransport(FixtureTransport):
        def get_json(self, url, *, headers=None):
            if '/search/repositories?' in url:
                return {'items':[{'id':9,'full_name':'owner/ai-agents','description':'AI agents','html_url':None}]}
            if '/search/issues?' in url:
                return {'items':[]}
            return super().get_json(url, headers=headers)
        def get_public_text(self, url):
            return '<rss><channel><item><title>AI agents today</title><description>AI agents</description></item></channel></rss>'

    adapters = build_adapters({'RSS_FEED_URLS':'https://feeds.example.org/news.xml'}, MalformedTransport())
    assert adapters['github'](PROFILE, 2).rejected_count == 1
    assert adapters['rss'](PROFILE, 1).rejected_count == 1


def test_out_of_range_provider_timestamp_is_treated_as_missing():
    from signalscout.adapters import _date

    assert _date(10**30) is None

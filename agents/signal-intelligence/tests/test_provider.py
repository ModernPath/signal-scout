import pytest

import json

from intelligence_provider import GeminiProvider, extract_grounded_research, resolve_grounding_url


def test_research_extracts_only_grounding_supported_claims():
    payload = {"candidates": [{"content": {"parts": [{"text": "A cited claim. An uncited claim."}]},
                               "groundingMetadata": {
                                   "groundingChunks": [{"web": {"uri": "https://source.example/a"}}],
                                   "groundingSupports": [{"segment": {"text": "A cited claim."},
                                                          "groundingChunkIndices": [0]}]}}]}
    result = extract_grounded_research(payload)
    assert result["status"] == "partial"
    assert result["evidence"] == [{"source_url": "https://source.example/a",
                                    "claim": "A cited claim.", "stance": "unknown",
                                    "retrieved": True}]
    assert "uncited" not in result["summary"]


def test_research_refuses_response_without_grounded_source():
    with pytest.raises(RuntimeError, match="grounded"):
        extract_grounded_research({"candidates": [{"content": {"parts": [{"text": "Claim"}]}}]})


def test_research_preserves_grounded_conflict_label():
    payload = {"candidates": [{"groundingMetadata": {
        "groundingChunks": [{"web": {"uri": "https://source.example/contrary"}}],
        "groundingSupports": [{"segment": {"text": "CONFLICT: The release date is disputed."},
                               "groundingChunkIndices": [0]}]}}]}
    result = extract_grounded_research(payload)
    assert result["evidence"][0]["stance"] == "conflict"
    assert result["evidence"][0]["claim"] == "The release date is disputed."


def test_google_grounding_redirect_resolves_only_to_public_publisher_url():
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/token"

    class Response:
        status = 302
        headers = {"Location": "https://publisher.example/article"}

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == redirect
            assert request.get_method() == "HEAD"
            assert timeout <= 8
            return Response()

    assert resolve_grounding_url(redirect, opener=Opener()) == "https://publisher.example/article"
    Response.headers = {"Location": "http://127.0.0.1/private"}
    assert resolve_grounding_url(redirect, opener=Opener()) == redirect
    assert resolve_grounding_url("https://publisher.example/article", opener=Opener()) == \
        "https://publisher.example/article"


def test_grounded_research_uses_resolved_publisher_url():
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/token"
    payload = {"candidates": [{"groundingMetadata": {
        "groundingChunks": [{"web": {"uri": redirect}}],
        "groundingSupports": [{"segment": {"text": "SUPPORT: PageBreak was disclosed."},
                               "groundingChunkIndices": [0]}]}}]}
    result = extract_grounded_research(payload,
                                       resolve_url=lambda url: "https://blog.google/pagebreak")
    assert result["evidence"][0]["source_url"] == "https://blog.google/pagebreak"
    assert result["evidence"][0]["stance"] == "support"


def test_json_draft_request_bounds_gemini_thinking_tokens(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, *args):
            return b'{"candidates":[]}'

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data))
        return Response()

    monkeypatch.setattr("intelligence_provider.urlopen", fake_urlopen)
    GeminiProvider("test-key", model="gemini-2.5-flash")._generate("Draft", json_output=True)
    assert captured["generationConfig"]["thinkingConfig"]["thinkingBudget"] <= 512


def test_reply_prompt_does_not_assume_an_unseen_target_post(monkeypatch):
    provider = GeminiProvider("test-key", model="gemini-2.5-flash")
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"candidates": [{"content": {"parts": [{"text":
                '{"text":"PageBreak offers a useful case for security teams.","evidence_ids":[7]}'}]}}]}

    monkeypatch.setattr(provider, "_generate", fake_generate)
    provider.draft({"label": "PageBreak", "angle": "Verify findings", "why_now": "Recent"},
                   {"evidence": [{"id": 7, "claim": "PageBreak was disclosed",
                                  "source_url": "https://blog.google/pagebreak"}]},
                   {"voice": "Practical"}, "x", "reply")
    assert "no target post" in captured["prompt"].lower()
    assert "do not imply a prior conversation" in captured["prompt"].lower()
    assert "at most 220 characters" in captured["prompt"].lower()


def test_summary_does_not_repeat_claims_corroborated_by_multiple_sources():
    claim='The project verifies agent findings.'
    payload={'candidates':[{'groundingMetadata':{
        'groundingChunks':[{'web':{'uri':'https://source.example/a'}},{'web':{'uri':'https://source.example/b'}}],
        'groundingSupports':[{'segment':{'text':'SUPPORT: '+claim},'groundingChunkIndices':[0,1]}]}}]}
    result=extract_grounded_research(payload)
    assert result['summary']==claim
    assert len(result['evidence'])==2


def test_grounding_redirect_is_resolved_once_per_source():
    redirect='https://vertexaisearch.cloud.google.com/grounding-api-redirect/token'
    payload={'candidates':[{'groundingMetadata':{
        'groundingChunks':[{'web':{'uri':redirect}}],
        'groundingSupports':[{'segment':{'text':claim},'groundingChunkIndices':[0]}
                             for claim in ['Claim one','Claim two']]}}]}
    calls=[]
    def resolver(url):
        calls.append(url)
        return 'https://source.example/article'
    assert len(extract_grounded_research(payload,resolve_url=resolver)['evidence'])==2
    assert calls==[redirect]


def test_draft_prompt_requires_citations_for_all_numeric_claims(monkeypatch):
    provider=GeminiProvider('test-key')
    captured={}
    def generate(prompt,**kwargs):
        captured['prompt']=prompt
        return {'candidates':[{'content':{'parts':[{'text':'{"text":"Verify agent findings.","evidence_ids":[7]}'}]}}]}
    monkeypatch.setattr(provider,'_generate',generate)
    provider.draft({'label':'PageBreak','angle':'Verify findings','why_now':'Recent'},
                   {'evidence':[{'id':7,'claim':'Research found 500 flaws','source_url':'https://example.com/article'}]},
                   {'voice':'Practical'},'linkedin','reply')
    assert 'every factual claim' in captured['prompt'].lower()
    assert 'numbers must appear in the evidence records whose ids you cite' in captured['prompt'].lower()

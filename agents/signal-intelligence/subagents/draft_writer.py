#!/usr/bin/env python3
"""Write one draft variant from an immutable research snapshot."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import print_result, read_request
from agent_env import make_store
from intelligence_provider import GeminiProvider


def run(request: dict, store, provider) -> dict:
    id = request.get("opportunity_id")
    channel, format = request.get("channel"), request.get("format")
    if not isinstance(id, int) or id <= 0 or channel not in ("linkedin", "x") or \
            format not in ("post", "reply"):
        raise ValueError("A valid opportunity, channel, and format are required")
    opportunity = store.get_opportunity(id)
    research = store.latest_research(id)
    brief = store.get_brief()
    if not research or research["status"] != "complete" or not research["evidence"] or not brief:
        raise ValueError("Complete research and company brief are required")
    if request.get('retrieval_id'):
        from intelligence_retrieval import KnowledgeService
        knowledge=KnowledgeService(store.engine)
        company=knowledge.get_retrieval(request['retrieval_id'])
        factual=knowledge.get_retrieval(request['factual_retrieval_id'])
        if company['opportunity_id']!=id or factual['opportunity_id']!=id or factual['research_id']!=research['id'] or research['id']!=request['research_id']:
            raise ValueError('Draft inputs changed; retry with current research')
        if any(h['removed'] for h in company['hits']+factual['hits']):
            raise ValueError('Draft sources removed or expired')
        opportunity=dict(opportunity,company_context=company,factual_context=factual)
        ids={h['source_id'] for h in factual['hits']}
        if ids:
            research=dict(research,evidence=[e for e in research['evidence'] if e['id'] in ids])
    return provider.draft(opportunity, research, brief["brief"], channel, format)


if __name__ == "__main__":
    def action():
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("Draft provider is unavailable; configure GEMINI_API_KEY")
        return run(read_request(), make_store(), GeminiProvider(
            key, model=os.environ.get("SIGNAL_INTELLIGENCE_MODEL", "gemini-2.5-flash")))

    print_result(action)

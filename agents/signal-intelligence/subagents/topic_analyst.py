#!/usr/bin/env python3
"""Label one core-approved conversation candidate; never change membership."""

from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_cli import print_result, read_request
from agent_env import make_store
from intelligence_core import terms


def run(request: dict, store, *, provider=None, knowledge=None) -> dict:
    if 'opportunity_id' in request:
        from intelligence_retrieval import KnowledgeService
        from intelligence_provider import GeminiProvider
        id=request.get('opportunity_id')
        retrieval_id=request.get('retrieval_id')
        if any(not isinstance(v,int) or v<=0 for v in (id,retrieval_id,request.get('brief_id'))):
            raise ValueError('Valid opportunity, retrieval and brief IDs required')
        knowledge=knowledge or KnowledgeService(store.engine)
        retrieval=knowledge.get_retrieval(retrieval_id)
        brief=store.get_brief()
        if not brief or brief['id']!=request['brief_id'] or retrieval['opportunity_id']!=id or any(h['removed'] for h in retrieval['hits']):
            raise ValueError('Refinement inputs changed or unavailable')
        provider=provider or GeminiProvider(os.environ.get('GEMINI_API_KEY',''),model=os.environ.get('SIGNAL_INTELLIGENCE_MODEL','gemini-2.5-flash'))
        return provider.refine(store.get_opportunity(id),brief['brief'],retrieval)
    ids = request.get("signal_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 50 or any(
            not isinstance(id, int) or id <= 0 for id in ids):
        raise ValueError("signal_ids must contain 1-50 positive IDs")
    titles = store.signal_titles(ids)
    if len(titles) != len(ids):
        raise LookupError("Signal candidate not found")
    shared = set.intersection(*(terms(title) for title in titles)) if titles else set()
    label = " ".join(sorted(shared))[:160] if len(shared) >= 2 else titles[0][:160]
    return {"label": label, "summary": f"{len(titles)} signal(s) about {label}.",
            "accepted": True, "signal_ids": ids}


if __name__ == "__main__":
    print_result(lambda: run(read_request(), make_store()))

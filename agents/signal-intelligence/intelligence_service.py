"""Standalone intelligence use cases shared by CLI and future application API."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from intelligence_core import cluster_signals, rank_conversation

ALGORITHM_VERSION = "cluster-score-v1"
BRIEF_FIELDS = ("description", "audience", "expertise", "point_of_view", "voice")


def public_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        if parsed.scheme not in ("http", "https") or not host or parsed.username or parsed.password:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host
    except ValueError:
        return False


class IntelligenceService:
    def __init__(self, store, *, provider=None, subagent_runner=None, now=None, embedder=None):
        self.store = store
        self.provider = provider
        self.subagent_runner = subagent_runner
        self.embedder = embedder
        self.now = now or (lambda: datetime.now(timezone.utc))

    @property
    def knowledge(self):
        from intelligence_retrieval import KnowledgeService
        return KnowledgeService(self.store.engine, embedder=self.embedder)

    def search_knowledge(self, query: str, *, semantic=True) -> dict:
        from intelligence_retrieval import KnowledgeService
        knowledge=self.knowledge if semantic else KnowledgeService(self.store.engine)
        return knowledge.search(query, purpose='inspection')

    def refine_angle(self, opportunity_id: int) -> dict:
        opportunity = self.store.get_opportunity(opportunity_id)
        brief = self.store.get_brief()
        if not brief:
            raise ValueError('A complete company brief is required')
        retrieval = self.knowledge.search(opportunity['label'], opportunity_id=opportunity_id)
        if not retrieval['hits']:
            raise ValueError('No relevant company passages. Add content or adjust the topic before refinement.')
        if self.subagent_runner:
            result = self.subagent_runner.run('topic_analyst', {'opportunity_id':opportunity_id,
                   'retrieval_id':retrieval['id'], 'brief_id':brief['id']})
        elif self.provider and hasattr(self.provider, 'refine'):
            result = self.provider.refine(opportunity, brief['brief'], retrieval)
        else:
            raise RuntimeError('Angle provider is unavailable')
        allowed = {h['chunk_id'] for h in retrieval['hits']}
        passages = {h['chunk_id']:' '.join(h['passage'].split()).casefold() for h in retrieval['hits']}
        comparisons = result.get('comparisons', [])
        if not isinstance(comparisons,list) or not comparisons or len(comparisons)>8:
            raise RuntimeError('Angle provider returned unsupported comparisons')
        for row in comparisons:
            if not isinstance(row,dict) or row.get('chunk_id') not in allowed or row.get('verdict') not in ('repeated','different','uncertain'):
                raise RuntimeError('Angle provider cited unsupported company passages')
            if any(not isinstance(row.get(k),str) or not 1<=len(row[k])<=1000 for k in ('prior_claim','difference')):
                raise RuntimeError('Angle provider returned invalid comparison')
            if ' '.join(row['prior_claim'].split()).casefold() not in passages[row['chunk_id']]:
                raise RuntimeError('Angle provider returned unsupported prior claim')
        if any(not isinstance(result.get(k),str) or not 1<=len(result[k])<=2000 for k in ('why_us','angle','uncertainty')):
            raise RuntimeError('Angle provider returned invalid explanation')
        # Validate the source again after generation; deleted sources must not be republished.
        snapshot = self.knowledge.get_retrieval(retrieval['id'])
        if any(h['removed'] for h in snapshot['hits']):
            raise RuntimeError('Company source was removed during refinement')
        return self.knowledge.store.save_enrichment(opportunity_id,retrieval['id'],brief['id'],
                 {k:result[k] for k in ('comparisons','why_us','angle','uncertainty')},
                 result.get('model_version') or getattr(self.provider,'model','unknown'))

    def set_brief(self, brief: dict) -> dict:
        if not isinstance(brief, dict) or any(not str(brief.get(key, "")).strip()
                                              for key in BRIEF_FIELDS):
            raise ValueError("Company brief requires description, audience, expertise, point_of_view, and voice")
        cleaned = {key: str(brief.get(key, "")).strip()[:4000] for key in
                   (*BRIEF_FIELDS, "avoid_claims")}
        return self.store.set_brief(cleaned)

    def get_brief(self) -> dict | None:
        return self.store.get_brief()

    def clear_brief(self) -> dict:
        return self.store.clear_brief()

    def add_content(self, content: dict) -> dict:
        if not isinstance(content, dict) or not str(content.get("title", "")).strip() or \
                not str(content.get("text", "")).strip() or not str(content.get("channel", "")).strip():
            raise ValueError("Content requires title, text, and channel")
        if content.get("url") and not public_url(str(content["url"])):
            raise ValueError("Content URL must be a public HTTP(S) URL")
        cleaned = {"title": str(content["title"]).strip()[:300],
                   "text": str(content["text"]).strip()[:20000],
                   "channel": str(content["channel"]).strip()[:40],
                   "url": content.get("url")}
        return self.store.add_content(cleaned)

    def list_content(self) -> list[dict]:
        return self.store.list_content()

    def replace_content(self, content_id: int, content: dict) -> dict:
        self._validate_content(content)
        return self.store.replace_content(content_id, self._clean_content(content))

    def delete_content(self, content_id: int) -> dict:
        return self.store.delete_content(content_id)

    @staticmethod
    def _validate_content(content: dict) -> None:
        if not isinstance(content, dict) or not str(content.get("title", "")).strip() or \
                not str(content.get("text", "")).strip() or not str(content.get("channel", "")).strip():
            raise ValueError("Content requires title, text, and channel")
        if content.get("url") and not public_url(str(content["url"])):
            raise ValueError("Content URL must be a public HTTP(S) URL")

    @staticmethod
    def _clean_content(content: dict) -> dict:
        return {"title": str(content["title"]).strip()[:300],
                "text": str(content["text"]).strip()[:20000],
                "channel": str(content["channel"]).strip()[:40],
                "url": content.get("url")}

    def create_chat_session(self) -> dict:
        return self.store.create_chat_session(self.now() + timedelta(days=90))

    def append_chat_turn(self, session_id: int, role: str, content: str) -> dict:
        if role not in ("user", "assistant") or not isinstance(content, str) or \
                not content.strip() or len(content) > 4000:
            raise ValueError("Chat turn requires a valid role and 1-4000 characters")
        current = self.now()
        return self.store.append_chat_turn(session_id, role, content.strip(), now=current,
                                           expires_at=current + timedelta(days=90))

    def chat_history(self, session_id: int) -> list[dict]:
        return self.store.chat_history(session_id, self.now())

    def delete_chat_session(self, session_id: int) -> dict:
        return self.store.delete_chat_session(session_id)

    def cleanup_expired(self) -> dict:
        return self.store.cleanup_expired(self.now())

    def analyze(self, *, days: int = 30, limit: int = 500) -> dict:
        if not 1 <= days <= 90 or not 1 <= limit <= 1000:
            raise ValueError("Analysis days and limit are out of range")
        current = self.now()
        signals = self.store.load_signals(days=days, limit=limit, now=current)
        brief = self.store.get_brief()
        content = self.store.list_content()
        fingerprint_input = {"version": ALGORITHM_VERSION, "day": current.date().isoformat(),
                             "days": days, "limit": limit, "brief": brief,
                             "content": content,
                             "signals": [{"id": s["id"], "title": s["title"],
                                          "snippet": s["snippet"],
                                          "published_at": s["published_at"].isoformat() if s["published_at"] else None,
                                          "topics": s["topics"],
                                          "source_item_ids": [item["id"] for item in s["source_items"]]}
                                         for s in signals]}
        fingerprint = hashlib.sha256(json.dumps(fingerprint_input, sort_keys=True,
                                                 default=str).encode()).hexdigest()
        cached = self.store.get_run(fingerprint)
        if cached:
            return cached
        groups = []
        topics = tuple(sorted({topic for signal in signals for topic in signal["topics"]}))
        for group in cluster_signals(signals):
            score = rank_conversation(group["signals"], brief["brief"] if brief else None,
                                      content, current, topics=topics)
            label = max(group["signals"], key=lambda s: len(s["title"]))["title"][:160]
            if self.subagent_runner is not None:
                try:
                    proposal = self.subagent_runner.run("topic_analyst",
                                                        {"signal_ids": group["signal_ids"]})
                    if isinstance(proposal.get("label"), str) and 1 <= len(proposal["label"]) <= 160:
                        label = proposal["label"].strip() or label
                except RuntimeError:
                    pass  # Deterministic title remains available offline.
            groups.append({"signal_ids": group["signal_ids"], "reason": group["reason"],
                           "label": label,
                           "score": score})
        groups.sort(key=lambda row: (-row["score"]["total"], min(row["signal_ids"])))
        return self.store.save_analysis(fingerprint, groups)

    def opportunities(self) -> dict:
        return self.store.list_opportunities() or {"run_id": None, "opportunities": []}

    def opportunity(self, opportunity_id: int) -> dict:
        return self.store.get_opportunity(opportunity_id)

    def opportunity_detail(self, opportunity_id: int) -> dict:
        item = self.store.get_opportunity(opportunity_id)
        from intelligence_retrieval import KnowledgeService
        preview=KnowledgeService(self.store.engine).search(item['label'],persist=False)
        drafts=self.store.list_drafts(opportunity_id)
        for draft in drafts:
            draft['company_context']=self.knowledge.get_retrieval(draft['retrieval_id']) if draft['retrieval_id'] else None
            draft['factual_context']=self.knowledge.get_retrieval(draft['factual_retrieval_id']) if draft['factual_retrieval_id'] else None
        return {**item,
                "source_items": self.store.source_evidence(item["evidence_source_item_ids"]),
                "research": self.store.latest_research(opportunity_id),
                "drafts": drafts,
                "knowledge": self.knowledge.store.latest(opportunity_id) or preview,
                "enrichment": self.knowledge.store.enrichment(opportunity_id)}

    def research(self, opportunity_id: int) -> dict:
        opportunity = self.store.get_opportunity(opportunity_id)
        if self.provider is None and self.subagent_runner is None:
            raise RuntimeError("Research provider is unavailable; configure GEMINI_API_KEY")
        source_items = self.store.source_evidence(opportunity["evidence_source_item_ids"])
        if not source_items:
            raise ValueError("Opportunity has no source evidence")
        try:
            result = (self.subagent_runner.run("evidence_researcher", {"opportunity_id": opportunity_id})
                      if self.subagent_runner is not None else
                      self.provider.research(opportunity, source_items))
            if result.get("status") not in ("complete", "partial") or \
                    not isinstance(result.get("summary"), str) or not isinstance(result.get("evidence"), list):
                raise RuntimeError("Research provider returned invalid data")
            allowed = {item["source_url"] for item in source_items}
            evidence = []
            for item in result["evidence"][:12]:
                url = item.get("source_url", "")
                if not public_url(url) or (url not in allowed and not item.get("retrieved")):
                    raise RuntimeError("Research provider returned unverified source URL")
                if item.get("stance") not in ("support", "conflict", "unknown"):
                    raise RuntimeError("Research provider returned invalid stance")
                evidence.append({"source_url": url, "claim": str(item.get("claim", ""))[:1000],
                                 "stance": item["stance"], "retrieved_at": self.now(),
                                 "excerpt_expires_at": self.now() + timedelta(days=90)})
            if not evidence:
                raise RuntimeError("Research provider returned no verifiable evidence")
        except (RuntimeError, TypeError, AttributeError, KeyError):
            self.store.save_research(opportunity_id, {
                "status": "partial", "summary": "Research could not complete.",
                "error_summary": "Research provider failed or returned unusable evidence",
                "model_version": getattr(self.provider, "model", "unknown"), "evidence": []})
            raise RuntimeError("Research provider failed or returned unusable evidence") from None
        source_confirmed = any(item["source_url"] in allowed for item in evidence)
        status = result["status"] if source_confirmed else "partial"
        summary = result["summary"][:6000]
        if not source_confirmed:
            summary = ("No starting source URL was confirmed. Review these related search results "
                       "before using them for a draft. " + summary)[:6000]
        return self.store.save_research(opportunity_id, {"status": status,
                                                         "summary": summary,
                                                         "evidence": evidence,
                                                         "model_version": result.get("model_version") or
                                                         getattr(self.provider, "model", "unknown")})

    def draft(self, opportunity_id: int, channel: str, format: str) -> dict:
        if channel not in ("linkedin", "x") or format not in ("post", "reply"):
            raise ValueError("Choose linkedin|x and post|reply")
        opportunity = self.store.get_opportunity(opportunity_id)
        research = self.store.latest_research(opportunity_id)
        if not research or research["status"] != "complete" or not research["evidence"]:
            raise ValueError("Complete research with evidence is required before drafting")
        research=dict(research,evidence=[e for e in research['evidence'] if e['claim'] not in ('[expired]','') and (not e.get('excerpt_expires_at') or e['excerpt_expires_at']>self.now())])
        if not research['evidence']:
            raise ValueError('Complete research with unexpired evidence is required before drafting')
        brief = self.store.get_brief()
        if not brief:
            raise ValueError("A complete company brief is required before drafting")
        if self.provider is None and self.subagent_runner is None:
            raise RuntimeError("Draft provider is unavailable; configure GEMINI_API_KEY")
        company = self.knowledge.search(opportunity['label'],opportunity_id=opportunity_id,purpose='draft-company')
        factual = self.knowledge.search(opportunity['label'],opportunity_id=opportunity_id,
                                       research_id=research['id'],purpose='draft-factual')
        opportunity = dict(opportunity,company_context=company,factual_context=factual)
        selected = {h['source_id'] for h in factual['hits']}
        if selected:
            research = dict(research,evidence=[e for e in research['evidence'] if e['id'] in selected])
        result = (self.subagent_runner.run("draft_writer", {"opportunity_id": opportunity_id,
                                                             "channel": channel, "format": format,
             "retrieval_id":company["id"],"factual_retrieval_id":factual["id"],"research_id":research["id"]})
                  if self.subagent_runner is not None else
                  self.provider.draft(opportunity, research, brief["brief"], channel, format))
        if not isinstance(result, dict) or not str(result.get("text", "")).strip():
            raise RuntimeError("Draft provider returned no text")
        allowed = {item["id"] for item in research["evidence"]}
        cited = result.get("evidence_ids", [])
        if not cited or not set(cited) <= allowed:
            raise RuntimeError("Draft provider cited unsupported evidence")
        company_cited=result.get('company_chunk_ids',[])
        if not isinstance(company_cited,list) or not set(company_cited)<={h['chunk_id'] for h in company['hits']}:
            raise RuntimeError('Draft provider cited unsupported company passages')
        if any(h['removed'] for h in self.knowledge.get_retrieval(company['id'])['hits']):
            raise RuntimeError('Company source was removed during drafting')
        if any(h['removed'] for h in self.knowledge.get_retrieval(factual['id'])['hits']):
            raise RuntimeError('Factual source expired during drafting')
        limit = 280 if channel == "x" else 3000
        draft_text = result["text"].strip()
        if len(draft_text) > limit:
            raise RuntimeError("Draft exceeds channel length limit")
        prohibited = [part.strip().casefold() for part in
                      re.split(r"[;\n]", brief["brief"].get("avoid_claims", "")) if part.strip()]
        if any(part in draft_text.casefold() for part in prohibited):
            raise RuntimeError("Draft contains a prohibited claim")
        evidence_text = " ".join(item["claim"] for item in research["evidence"]
                                 if item["id"] in cited)
        unsupported_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", draft_text)) - \
            set(re.findall(r"\b\d+(?:\.\d+)?%?\b", evidence_text))
        if unsupported_numbers:
            raise RuntimeError("Draft contains unsupported numeric claims")
        return self.store.save_draft(opportunity_id, research["id"], channel,
                                     format, draft_text, cited,
                                     retrieval_id=company["id"],factual_retrieval_id=factual["id"],
                                     model_version=result.get("model_version") or
                                     getattr(self.provider, "model", "unknown"))

"""PostgreSQL access for the standalone agent; application Alembic owns the schema."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine


class IntelligenceStore:
    def __init__(self, engine: Engine):
        self.engine = engine

    def check_schema(self) -> None:
        with self.engine.connect() as connection:
            ready = connection.execute(text("SELECT to_regclass('agent_chat_session') IS NOT NULL "
                                            "AND to_regclass('opportunity') IS NOT NULL")).scalar_one()
        if not ready:
            raise RuntimeError("Apply application migrations through 0006_agent_memory first")

    def set_brief(self, brief: dict) -> dict:
        with self.engine.begin() as connection:
            version = connection.execute(text("SELECT COALESCE(MAX(version),0)+1 FROM company_brief")).scalar_one()
            id = connection.execute(text("INSERT INTO company_brief (version,brief) "
                                         "VALUES (:version,CAST(:brief AS jsonb)) RETURNING id"),
                                    {"version": version, "brief": json.dumps(brief)}).scalar_one()
        return {"id": id, "version": version, "brief": brief}

    def get_brief(self) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT id,version,brief FROM company_brief "
                                          "WHERE active=true ORDER BY version DESC LIMIT 1")).mappings().first()
        return dict(row) if row else None

    def clear_brief(self) -> dict:
        with self.engine.begin() as connection:
            latest = connection.execute(text("SELECT id FROM company_brief WHERE active=true "
                                             "ORDER BY version DESC LIMIT 1")).scalar_one_or_none()
            if latest is None:
                raise LookupError("Company brief not found")
            connection.execute(text("UPDATE company_brief SET active=false,brief='{}'::jsonb "
                                    "WHERE active=true"))
        return {"id": latest, "deleted": True}

    def add_content(self, item: dict) -> dict:
        digest = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
        with self.engine.begin() as connection:
            id = connection.execute(text("INSERT INTO company_content "
                                         "(title,content_text,url,channel,content_hash) "
                                         "VALUES (:title,:content_text,:url,:channel,:hash) "
                                         "ON CONFLICT (content_hash) DO UPDATE SET title=EXCLUDED.title "
                                         "RETURNING id"),
                                    {"title": item["title"], "content_text": item["text"],
                                     "url": item.get("url"), "channel": item["channel"],
                                     "hash": digest}).scalar_one()
        return {"id": id, **item}

    def list_content(self) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT id,title,content_text,url,channel "
                                           "FROM company_content WHERE active=true ORDER BY id")).mappings().all()
        return [{"id": row["id"], "title": row["title"], "text": row["content_text"],
                 "url": row["url"], "channel": row["channel"]} for row in rows]

    def replace_content(self, content_id: int, item: dict) -> dict:
        with self.engine.begin() as connection:
            old = connection.execute(text("SELECT id FROM company_content "
                                          "WHERE id=:id AND active=true FOR UPDATE"),
                                     {"id": content_id}).first()
            if not old:
                raise LookupError("Content item not found")
            connection.execute(text("UPDATE company_content SET active=false WHERE id=:id"),
                               {"id": content_id})
            digest = hashlib.sha256((json.dumps(item, sort_keys=True) + str(content_id)).encode()).hexdigest()
            new_id = connection.execute(text("INSERT INTO company_content "
                                             "(title,content_text,url,channel,content_hash,replaces_id) "
                                             "VALUES (:title,:content_text,:url,:channel,:hash,:replaces_id) "
                                             "RETURNING id"),
                                        {"title": item["title"], "content_text": item["text"],
                                         "url": item.get("url"), "channel": item["channel"],
                                         "hash": digest, "replaces_id": content_id}).scalar_one()
        return {"id": new_id, "replaces_id": content_id, **item}

    def delete_content(self, content_id: int) -> dict:
        with self.engine.begin() as connection:
            rows = connection.execute(text(
                "WITH RECURSIVE lineage AS ("
                "SELECT id,replaces_id FROM company_content WHERE id=:id AND active=true "
                "UNION ALL SELECT parent.id,parent.replaces_id FROM company_content parent "
                "JOIN lineage child ON child.replaces_id=parent.id) "
                "UPDATE company_content SET active=false,title='[deleted]',"
                "content_text='',url=NULL,content_hash='deleted-' || id::text "
                "WHERE id IN (SELECT id FROM lineage) RETURNING id"),
                {"id": content_id}).all()
        if not rows:
            raise LookupError("Content item not found")
        return {"id": content_id, "deleted": True}

    def create_chat_session(self, expires_at: datetime) -> dict:
        with self.engine.begin() as connection:
            row = connection.execute(text("INSERT INTO agent_chat_session (expires_at) "
                                          "VALUES (:expires_at) RETURNING id,created_at,expires_at"),
                                     {"expires_at": expires_at}).mappings().one()
        return dict(row)

    def append_chat_turn(self, session_id: int, role: str, content: str,
                         *, now: datetime, expires_at: datetime) -> dict:
        with self.engine.begin() as connection:
            exists = connection.execute(text("UPDATE agent_chat_session "
                                             "SET updated_at=:now,expires_at=:expires_at "
                                             "WHERE id=:id AND expires_at>:now RETURNING id"),
                                        {"now": now, "expires_at": expires_at,
                                         "id": session_id}).first()
            if not exists:
                raise LookupError("Chat session not found")
            row = connection.execute(text("INSERT INTO agent_chat_turn (session_id,role,content) "
                                          "VALUES (:id,:role,:content) RETURNING id,role,content,created_at"),
                                     {"id": session_id, "role": role,
                                      "content": content}).mappings().one()
        return dict(row)

    def chat_history(self, session_id: int, now: datetime, *, limit: int = 40) -> list[dict]:
        with self.engine.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM agent_chat_session "
                                             "WHERE id=:id AND expires_at>:now"),
                                        {"id": session_id, "now": now}).first()
            if not exists:
                raise LookupError("Chat session not found")
            rows = connection.execute(text("SELECT id,role,content,created_at FROM "
                                           "(SELECT id,role,content,created_at FROM agent_chat_turn "
                                           "WHERE session_id=:id ORDER BY id DESC LIMIT :limit) turns "
                                           "ORDER BY id"),
                                      {"id": session_id, "limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def delete_chat_session(self, session_id: int) -> dict:
        with self.engine.begin() as connection:
            row = connection.execute(text("DELETE FROM agent_chat_session WHERE id=:id RETURNING id"),
                                     {"id": session_id}).first()
        if not row:
            raise LookupError("Chat session not found")
        return {"id": session_id, "deleted": True}

    def cleanup_expired(self, now: datetime) -> dict:
        with self.engine.begin() as connection:
            sessions = connection.execute(text("DELETE FROM agent_chat_session "
                                               "WHERE expires_at<=:now RETURNING id"),
                                          {"now": now}).all()
            excerpts = connection.execute(text("UPDATE research_evidence "
                                               "SET claim='[expired]' "
                                               "WHERE excerpt_expires_at<=:now AND claim<>'[expired]' "
                                               "RETURNING id"), {"now": now}).all()
        return {"chat_sessions_deleted": len(sessions), "research_excerpts_expired": len(excerpts)}

    def signal_titles(self, signal_ids: list[int]) -> list[str]:
        if not signal_ids:
            return []
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT title FROM signal WHERE id=ANY(:ids) ORDER BY id"),
                                      {"ids": signal_ids}).scalars().all()
        return list(rows)


    def load_signals(self, *, days: int = 30, limit: int = 500,
                     now: datetime | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT s.id,s.title,s.snippet,"
                                           "COALESCE(s.published_at,s.created_at) AS published_at "
                                           "FROM signal s LEFT JOIN signal_state st ON st.signal_id=s.id "
                                           "WHERE COALESCE(st.dismissed,false)=false "
                                           "AND COALESCE(s.published_at,s.created_at) >= :since "
                                           "AND COALESCE(s.published_at,s.created_at) <= :now "
                                           "ORDER BY COALESCE(s.published_at,s.created_at) DESC,s.id DESC LIMIT :limit"),
                                      {"since": now - timedelta(days=days), "now": now,
                                       "limit": limit}).mappings().all()
            result = []
            for row in rows:
                topics = connection.execute(text("SELECT topic FROM signal_topic WHERE signal_id=:id "
                                                 "ORDER BY topic"), {"id": row["id"]}).scalars().all()
                items = connection.execute(text("SELECT id,source_key,source_url,published_at "
                                                "FROM source_item WHERE signal_id=:id ORDER BY id"),
                                           {"id": row["id"]}).mappings().all()
                result.append({**dict(row), "topics": tuple(topics),
                               "sources": tuple(sorted({item["source_key"] for item in items})),
                               "source_items": [dict(item) for item in items]})
        return result

    def get_run(self, fingerprint: str) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT id FROM intelligence_run "
                                          "WHERE fingerprint=:fingerprint AND status='complete'"),
                                     {"fingerprint": fingerprint}).first()
        return self.load_run(row[0]) if row else None

    def save_analysis(self, fingerprint: str, groups: list[dict]) -> dict:
        with self.engine.begin() as connection:
            run_id = connection.execute(text("INSERT INTO intelligence_run (fingerprint,status) "
                                             "VALUES (:fingerprint,'complete') "
                                             "ON CONFLICT (fingerprint) DO NOTHING RETURNING id"),
                                        {"fingerprint": fingerprint}).scalar_one_or_none()
            if run_id is None:
                run_id = connection.execute(text("SELECT id FROM intelligence_run "
                                                 "WHERE fingerprint=:fingerprint"),
                                            {"fingerprint": fingerprint}).scalar_one()
            else:
                for rank, group in enumerate(groups, 1):
                    conversation_id = connection.execute(text(
                        "INSERT INTO conversation (run_id,label,reason) "
                        "VALUES (:run_id,:label,:reason) RETURNING id"),
                        {"run_id": run_id, "label": group["label"],
                         "reason": group["reason"]}).scalar_one()
                    for signal_id in group["signal_ids"]:
                        connection.execute(text("INSERT INTO conversation_signal "
                                                "(conversation_id,signal_id) VALUES (:conversation_id,:signal_id)"),
                                           {"conversation_id": conversation_id, "signal_id": signal_id})
                    score = group["score"]
                    connection.execute(text("INSERT INTO opportunity "
                                            "(conversation_id,rank,score,confidence,components,why_now,"
                                            "why_us,angle,evidence_source_item_ids,prior_content_matches) "
                                            "VALUES (:conversation_id,:rank,:score,:confidence,"
                                            "CAST(:components AS jsonb),:why_now,:why_us,:angle,"
                                            "CAST(:evidence AS jsonb),CAST(:matches AS jsonb))"),
                                       {"conversation_id": conversation_id, "rank": rank,
                                        "score": score["total"], "confidence": score["confidence"],
                                        "components": json.dumps(score["components"]),
                                        "why_now": score["why_now"], "why_us": score["why_us"],
                                        "angle": score["angle"],
                                        "evidence": json.dumps(score["evidence_source_item_ids"]),
                                        "matches": json.dumps(score["prior_content_matches"])})
        return self.load_run(run_id)

    def load_run(self, run_id: int) -> dict:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT o.*,c.label,c.reason,c.run_id "
                                           "FROM opportunity o JOIN conversation c ON c.id=o.conversation_id "
                                           "WHERE c.run_id=:run_id ORDER BY o.rank"),
                                      {"run_id": run_id}).mappings().all()
            opportunities = []
            for row in rows:
                ids = connection.execute(text("SELECT signal_id FROM conversation_signal "
                                              "WHERE conversation_id=:id ORDER BY signal_id"),
                                         {"id": row["conversation_id"]}).scalars().all()
                opportunities.append({"id": row["id"], "label": row["label"],
                                      "signal_ids": list(ids), "reason": row["reason"],
                                      "rank": row["rank"], "total": row["score"],
                                      "confidence": row["confidence"], "components": row["components"],
                                      "why_now": row["why_now"], "why_us": row["why_us"],
                                      "angle": row["angle"],
                                      "evidence_source_item_ids": row["evidence_source_item_ids"],
                                      "prior_content_matches": row["prior_content_matches"]})
        return {"run_id": run_id, "opportunities": opportunities}

    def list_opportunities(self) -> dict | None:
        with self.engine.connect() as connection:
            run_id = connection.execute(text("SELECT id FROM intelligence_run "
                                             "WHERE status='complete' ORDER BY id DESC LIMIT 1")).scalar_one_or_none()
        return self.load_run(run_id) if run_id else None

    def get_opportunity(self, opportunity_id: int) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT c.run_id FROM opportunity o "
                                          "JOIN conversation c ON c.id=o.conversation_id "
                                          "WHERE o.id=:id"), {"id": opportunity_id}).first()
        if not row:
            raise LookupError("Opportunity not found")
        return next(item for item in self.load_run(row[0])["opportunities"]
                    if item["id"] == opportunity_id)

    def source_evidence(self, source_item_ids: list[int]) -> list[dict]:
        if not source_item_ids:
            return []
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT id,title,snippet,source_url FROM source_item "
                                           "WHERE id = ANY(:ids) ORDER BY id"),
                                      {"ids": source_item_ids}).mappings().all()
        return [dict(row) for row in rows]

    def save_research(self, opportunity_id: int, result: dict) -> dict:
        with self.engine.begin() as connection:
            run_id = connection.execute(text("INSERT INTO research_run "
                                             "(opportunity_id,status,summary,model_version,error_summary) "
                                             "VALUES (:id,:status,:summary,:model_version,:error_summary) RETURNING id"),
                                        {"id": opportunity_id, "status": result["status"],
                                         "summary": result["summary"],
                                         "model_version": result.get("model_version", "unknown"),
                                         "error_summary": result.get("error_summary")}).scalar_one()
            evidence = []
            for item in result["evidence"]:
                id = connection.execute(text("INSERT INTO research_evidence "
                                             "(research_run_id,source_url,claim,stance,retrieved_at,"
                                             "excerpt_expires_at) VALUES (:run_id,:url,:claim,:stance,"
                                             ":retrieved_at,:expires_at) RETURNING id"),
                                        {"run_id": run_id, "url": item["source_url"],
                                         "claim": item["claim"], "stance": item["stance"],
                                         "retrieved_at": item["retrieved_at"],
                                         "expires_at": item["excerpt_expires_at"]}).scalar_one()
                evidence.append({"id": id, **item})
        return {"id": run_id, "opportunity_id": opportunity_id,
                "status": result["status"], "summary": result["summary"],
                "model_version": result.get("model_version", "unknown"),
                "error_summary": result.get("error_summary"), "evidence": evidence}

    def latest_research(self, opportunity_id: int) -> dict | None:
        with self.engine.connect() as connection:
            run = connection.execute(text("SELECT id,status,summary,model_version,error_summary FROM research_run "
                                          "WHERE opportunity_id=:id ORDER BY id DESC LIMIT 1"),
                                     {"id": opportunity_id}).mappings().first()
            if not run:
                return None
            evidence = connection.execute(text("SELECT id,source_url,claim,stance,retrieved_at,excerpt_expires_at "
                                               "FROM research_evidence WHERE research_run_id=:id ORDER BY id"),
                                          {"id": run["id"]}).mappings().all()
        return {**dict(run), "evidence": [dict(item) for item in evidence]}

    def save_draft(self, opportunity_id: int, research_id: int, channel: str,
                   format: str, draft_text: str, evidence_ids: list[int],
                   *, model_version: str = "unknown", retrieval_id=None, factual_retrieval_id=None) -> dict:
        with self.engine.begin() as connection:
            valid=connection.execute(text("SELECT id FROM research_evidence WHERE research_run_id=:research "
                   "AND id=ANY(:ids) AND claim NOT IN ('[expired]','') AND excerpt_expires_at>now() ORDER BY id FOR SHARE"),
                   {'research':research_id,'ids':evidence_ids}).scalars().all()
            if set(valid)!=set(evidence_ids):
                raise RuntimeError('Factual evidence changed during generation; retry')
            from memory.knowledge import KnowledgeStore
            knowledge=KnowledgeStore(self.engine)
            for snapshot in (retrieval_id,factual_retrieval_id):
                if snapshot:
                    knowledge.validate_snapshot(connection,snapshot)
            id = connection.execute(text("INSERT INTO content_draft "
                                         "(opportunity_id,research_run_id,channel,format,draft_text,evidence_ids,"
                                         "model_version,prompt_version,retrieval_id,factual_retrieval_id) VALUES (:opportunity,:research,:channel,"
                                         ":format,:draft,CAST(:evidence AS jsonb),:model_version,'draft-rag-v1',:retrieval,:factual) "
                                         "RETURNING id"),
                                    {"opportunity": opportunity_id, "research": research_id,
                                     "channel": channel, "format": format, "draft": draft_text,
                                     "evidence": json.dumps(evidence_ids),
                                     "model_version": model_version,"retrieval":retrieval_id,"factual":factual_retrieval_id}).scalar_one()
        return {"id": id, "opportunity_id": opportunity_id, "research_run_id": research_id,
                "channel": channel, "format": format, "text": draft_text,
                "evidence_ids": evidence_ids, "status": "draft",
                "model_version": model_version, "prompt_version": "draft-v1"}

    def list_drafts(self, opportunity_id: int) -> list[dict]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("SELECT id,channel,format,draft_text,evidence_ids,"
                                           "research_run_id,status,created_at,retrieval_id,factual_retrieval_id,model_version,revises_id FROM content_draft "
                                           "WHERE opportunity_id=:id ORDER BY id DESC LIMIT 20"),
                                      {"id": opportunity_id}).mappings().all()
        return [{"id": row["id"], "channel": row["channel"], "format": row["format"],
                 "text": row["draft_text"], "evidence_ids": row["evidence_ids"],
                 "research_run_id": row["research_run_id"], "status": row["status"],
                 "created_at": row["created_at"],"retrieval_id":row["retrieval_id"],
                 "factual_retrieval_id":row["factual_retrieval_id"],"model_version":row["model_version"],
                 "revises_id":row["revises_id"]} for row in rows]


def main() -> None:
    """Inspect and maintain PostgreSQL agent memory without a web server."""
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent_cli import print_result
    from agent_env import make_service

    parser = argparse.ArgumentParser(description="SignalScout agent PostgreSQL memory")
    parser.add_argument("command", choices=("brief", "content", "opportunities", "research",
                                             "drafts", "chat", "chat-delete", "cleanup"))
    parser.add_argument("id", type=int, nargs="?")
    args = parser.parse_args()
    service = make_service(use_subagents=False)

    def action():
        if args.command == "brief":
            return service.get_brief()
        if args.command == "content":
            return service.list_content()
        if args.command == "opportunities":
            return service.opportunities()
        if args.command == "cleanup":
            return service.cleanup_expired()
        if args.id is None or args.id <= 0:
            raise ValueError("A positive ID is required")
        if args.command == "research":
            return service.store.latest_research(args.id)
        if args.command == "drafts":
            return service.store.list_drafts(args.id)
        if args.command == "chat":
            return service.chat_history(args.id)
        return service.delete_chat_session(args.id)

    print_result(action)


if __name__ == "__main__":
    main()

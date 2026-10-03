"""FastAPI surface for the independent SignalScout intelligence agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agent_env import make_service
from intelligence_chat import chat_reply


class BriefIn(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=4000)
    expertise: str = Field(min_length=1, max_length=4000)
    point_of_view: str = Field(min_length=1, max_length=4000)
    voice: str = Field(min_length=1, max_length=4000)
    avoid_claims: str = Field(default="", max_length=4000)


class ContentIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=20000)
    channel: str = Field(min_length=1, max_length=40)
    url: str | None = None


class AnalyzeIn(BaseModel):
    days: int = Field(default=30, ge=1, le=90)
    limit: int = Field(default=500, ge=1, le=1000)


class DraftIn(BaseModel):
    channel: str
    format: str


class KnowledgeIn(BaseModel):
    query: str = Field(min_length=1,max_length=1200)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None
    offline: bool = False


def create_app(service=None) -> FastAPI:
    app = FastAPI(title="SignalScout intelligence agent", version="0.2")
    app.state.service = service

    def active_service():
        if app.state.service is None:
            app.state.service = make_service()
        return app.state.service

    @app.exception_handler(ValueError)
    async def bad_input(_: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(LookupError)
    async def not_found(_: Request, exc: LookupError):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(RuntimeError)
    async def unavailable(_: Request, exc: RuntimeError):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        return JSONResponse({"detail": "Agent operation failed"}, status_code=500)

    @app.middleware("http")
    async def same_origin_mutations(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if ((origin is None and fetch_site != "same-origin") or
                    (origin is not None and origin != expected) or
                    fetch_site not in (None, "same-origin")):
                return JSONResponse({"detail": "Cross-origin request forbidden"}, status_code=403)
        return await call_next(request)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.get('/knowledge/status')
    def knowledge_status(agent=Depends(active_service)):
        return agent.knowledge.status()

    @app.post('/knowledge/index')
    def index_knowledge(agent=Depends(active_service)):
        agent.knowledge.store.retry()
        return agent.knowledge.index_pending()

    @app.post('/knowledge/search')
    def search_knowledge(payload: KnowledgeIn, agent=Depends(active_service)):
        return agent.search_knowledge(payload.query)

    @app.post('/opportunities/{opportunity_id}/refine-angle')
    def refine_angle(opportunity_id: int, agent=Depends(active_service)):
        return agent.refine_angle(opportunity_id)

    @app.get("/health")
    def health(agent=Depends(active_service)):
        agent.store.check_schema()
        return {"status": "ok"}

    @app.get("/brief")
    def get_brief(agent=Depends(active_service)):
        return agent.get_brief()

    @app.put("/brief")
    def set_brief(payload: BriefIn, agent=Depends(active_service)):
        return agent.set_brief(payload.model_dump())

    @app.delete("/brief")
    def clear_brief(agent=Depends(active_service)):
        return agent.clear_brief()

    @app.get("/content")
    def list_content(agent=Depends(active_service)):
        return agent.list_content()

    @app.post("/content")
    def add_content(payload: ContentIn, agent=Depends(active_service)):
        return agent.add_content(payload.model_dump())

    @app.put("/content/{content_id}")
    def replace_content(content_id: int, payload: ContentIn, agent=Depends(active_service)):
        return agent.replace_content(content_id, payload.model_dump())

    @app.delete("/content/{content_id}")
    def delete_content(content_id: int, agent=Depends(active_service)):
        return agent.delete_content(content_id)

    @app.post("/analyze")
    def analyze(payload: AnalyzeIn, agent=Depends(active_service)):
        return agent.analyze(days=payload.days, limit=payload.limit)

    @app.get("/opportunities")
    def opportunities(agent=Depends(active_service)):
        return agent.opportunities()

    @app.get("/opportunities/{opportunity_id}")
    def opportunity(opportunity_id: int, agent=Depends(active_service)):
        return agent.opportunity_detail(opportunity_id)

    @app.post("/opportunities/{opportunity_id}/research")
    def research(opportunity_id: int, agent=Depends(active_service)):
        return agent.research(opportunity_id)

    @app.post("/opportunities/{opportunity_id}/draft")
    def draft(opportunity_id: int, payload: DraftIn, agent=Depends(active_service)):
        return agent.draft(opportunity_id, payload.channel, payload.format)

    @app.post("/chat")
    def chat(payload: ChatIn, agent=Depends(active_service)):
        result = chat_reply(agent, payload.message, session_id=payload.session_id,
                            offline=payload.offline)
        return {"reply": result.reply, "session_id": result.session_id,
                "history": result.history, "used_llm": result.used_llm,
                "tools_used": result.tools_used}

    @app.get("/chat/{session_id}")
    def chat_history(session_id: int, agent=Depends(active_service)):
        return {"session_id": session_id, "history": agent.chat_history(session_id)}

    @app.delete("/chat/{session_id}")
    def delete_chat(session_id: int, agent=Depends(active_service)):
        return agent.delete_chat_session(session_id)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("AGENT_BIND_HOST", "127.0.0.1"),
                port=int(os.environ.get("AGENT_API_PORT", "8013")))

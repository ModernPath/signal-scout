#!/usr/bin/env python3
"""
FastAPI REST API for Example Agent.

Run:
  python api/main.py                                    # http://localhost:8012/docs
  uvicorn api.main:app --reload --port 8012             # from the agent folder
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import example_service as service  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from example_chat import chat_reply  # noqa: E402
from example_core import MAX_TITLE_LENGTH  # noqa: E402
from memory.memory import NoteStore  # noqa: E402

load_agent_environment()

DEFAULT_PORT = 8012

app = FastAPI(
    title="Example Agent API",
    version="1.0.0",
    description="Notes managed by an AI agent — a template for new agents.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --------------------------------------------------------------------------- #
# Dependencies and error mapping
# --------------------------------------------------------------------------- #


def get_store() -> NoteStore:
    """Override in tests with app.dependency_overrides[get_store]."""
    return NoteStore()


@app.exception_handler(ValueError)
async def _bad_request(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.exception_handler(LookupError)
async def _not_found(_: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(service.SubagentError)
async def _subagent_failed(_: Request, exc: service.SubagentError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class NoteIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)
    body: str = ""
    tags: List[str] = Field(default_factory=list)


class NoteOut(NoteIn):
    id: str
    created_at: str


class SummaryIn(BaseModel):
    tag: Optional[str] = None
    offline: bool = False


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1)
    history: List[ChatTurn] = Field(default_factory=list)
    offline: bool = False


class ChatOut(BaseModel):
    reply: str
    history: List[ChatTurn]
    used_llm: bool
    tools_used: List[str]


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/notes", response_model=List[NoteOut])
def list_notes(
    q: str = "",
    tag: Optional[str] = None,
    limit: int = 20,
    store: NoteStore = Depends(get_store),
) -> List[Dict[str, Any]]:
    return service.find_notes(store, q, tag=tag, limit=limit)


@app.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteIn, store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.add_note(store, payload.title, payload.body, payload.tags)


@app.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: str, store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.get_note(store, note_id)


@app.delete("/notes/{note_id}", response_model=NoteOut)
def delete_note(note_id: str, store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.delete_note(store, note_id)


@app.get("/overview")
def overview(store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.overview(store)


@app.post("/summary")
def summary(payload: SummaryIn, store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.summarize_notes(store, tag=payload.tag, offline=payload.offline)


@app.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    history = [turn.model_dump() for turn in payload.history]
    result = chat_reply(store, payload.message, history=history, offline=payload.offline)
    return {
        "reply": result.reply,
        "history": result.history,
        "used_llm": result.used_llm,
        "tools_used": result.tools_used,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("API_PORT", DEFAULT_PORT)))

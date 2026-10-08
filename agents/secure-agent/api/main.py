#!/usr/bin/env python3
"""
FastAPI REST API for Secure Agent.

Every route except /health needs `Authorization: Bearer <token>`. Create a
user and its token with `python manage_users.py add <user>`.

Run:
  python api/main.py                                    # http://127.0.0.1:8013/docs

Compared with example-agent:
  - no CORS middleware: a web page on another origin cannot call this API
    from a visitor's browser (example-agent allowed every origin);
  - every request acts as the token's user, and another user's note or action
    answers 404, exactly like a missing one;
  - the agent's deletions wait in /actions until the user approves them with
    the digest of the preview they were shown.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import example_service as service  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from example_chat import MAX_HISTORY_TURNS, chat_reply  # noqa: E402
from example_core import (  # noqa: E402
    MAX_BODY_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_TAGS,
    MAX_TITLE_LENGTH,
    ActionStateError,
)
from memory.memory import NoteStore, UserStore  # noqa: E402

load_agent_environment()

DEFAULT_PORT = 8013
MAX_MESSAGE_LENGTH = 2000

app = FastAPI(
    title="Secure Agent API",
    version="1.0.0",
    description="Notes managed by an AI agent, with per-user access and approval for deletions.",
)
bearer = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------- #
# Dependencies and error mapping
# --------------------------------------------------------------------------- #


def get_store() -> NoteStore:
    """Override in tests with app.dependency_overrides[get_store]."""
    return NoteStore()


def current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    store: NoteStore = Depends(get_store),
) -> str:
    """The user the token belongs to. Every data route depends on this."""
    user = UserStore(store.data_dir).authenticate(credentials.credentials if credentials else None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@app.exception_handler(ValueError)
async def _bad_request(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.exception_handler(LookupError)
async def _not_found(_: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(ActionStateError)
async def _conflict(_: Request, exc: ActionStateError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(service.SubagentError)
async def _subagent_failed(_: Request, exc: service.SubagentError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class NoteIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)
    body: str = Field("", max_length=MAX_BODY_LENGTH)
    tags: List[str] = Field(default_factory=list, max_length=MAX_TAGS)


class NoteOut(BaseModel):
    id: str
    title: str
    body: str
    tags: List[str]
    created_at: str


class SummaryIn(BaseModel):
    tag: Optional[str] = Field(None, max_length=50)
    offline: bool = False


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=MAX_MESSAGE_LENGTH * 2)


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: List[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS * 2)
    offline: bool = False


class ChatOut(BaseModel):
    reply: str
    history: List[ChatTurn]
    used_llm: bool
    tools_used: List[str]
    pending_actions: List[Dict[str, Any]]


class ApproveIn(BaseModel):
    digest: str = Field(..., min_length=1, max_length=64)


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
    user: str = Depends(current_user),
    store: NoteStore = Depends(get_store),
) -> List[Dict[str, Any]]:
    if len(q) > MAX_QUERY_LENGTH:
        raise ValueError(f"q must be at most {MAX_QUERY_LENGTH} characters.")
    return service.find_notes(store, user, q, tag=tag, limit=limit)


@app.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteIn, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.add_note(store, user, payload.title, payload.body, payload.tags)


@app.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: str, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.get_note(store, user, note_id)


@app.delete("/notes/{note_id}", response_model=NoteOut)
def delete_note(note_id: str, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    """A person deleting their own note. The agent's deletions go through /actions instead."""
    return service.delete_note(store, user, note_id)


@app.get("/overview")
def overview(user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.overview(store, user)


@app.post("/summary")
def summary(payload: SummaryIn, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.summarize_notes(store, user, tag=payload.tag, offline=payload.offline)


@app.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    history = [turn.model_dump() for turn in payload.history]
    result = chat_reply(store, user, payload.message, history=history, offline=payload.offline)
    return {
        "reply": result.reply,
        "history": result.history,
        "used_llm": result.used_llm,
        "tools_used": result.tools_used,
        "pending_actions": result.pending_actions,
    }


@app.get("/actions")
def list_actions(
    status_filter: Optional[str] = "pending",
    user: str = Depends(current_user),
    store: NoteStore = Depends(get_store),
) -> List[Dict[str, Any]]:
    return service.list_actions(store, user, status=status_filter or None)


@app.get("/actions/{action_id}")
def get_action(action_id: str, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.get_action(store, user, action_id)


@app.post("/actions/{action_id}/approve")
def approve_action(
    action_id: str,
    payload: ApproveIn,
    user: str = Depends(current_user),
    store: NoteStore = Depends(get_store),
) -> Dict[str, Any]:
    """Run the action once. `digest` must be the one shown with the preview."""
    return service.approve_action(store, user, action_id, payload.digest)


@app.post("/actions/{action_id}/reject")
def reject_action(action_id: str, user: str = Depends(current_user), store: NoteStore = Depends(get_store)) -> Dict[str, Any]:
    return service.reject_action(store, user, action_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("API_PORT", DEFAULT_PORT)))

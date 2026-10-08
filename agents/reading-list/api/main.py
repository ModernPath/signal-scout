#!/usr/bin/env python3
"""
FastAPI REST API for Reading List (local, loopback only, no authentication).

Run:
  python api/main.py                                    # http://127.0.0.1:8013/docs
  uvicorn api.main:app --reload --port 8013             # from the agent folder
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reading_list_service as service  # noqa: E402
from agent_env import load_agent_environment  # noqa: E402
from reading_list_chat import chat_reply  # noqa: E402
from memory.memory import ReadingListStore  # noqa: E402

load_agent_environment()

DEFAULT_PORT = 8013

app = FastAPI(
    title="Reading List API",
    version="1.0.0",
    description="A reading list with deterministic read-next ranking.",
)


# --------------------------------------------------------------------------- #
# Dependencies and error mapping
# --------------------------------------------------------------------------- #


def get_store() -> ReadingListStore:
    """Override in tests with app.dependency_overrides[get_store]."""
    return ReadingListStore()


@app.exception_handler(ValueError)
async def _bad_request(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


@app.exception_handler(LookupError)
async def _not_found(_: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class ItemIn(BaseModel):
    # Validation lives in the core so every surface rejects bad input with 400.
    title: str = ""
    url: str = ""
    note: str = ""
    tags: List[str] = Field(default_factory=list)


class TagsIn(BaseModel):
    tags: List[str]


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


@app.get("/items")
def list_items(
    unread: bool = False,
    tag: Optional[str] = None,
    store: ReadingListStore = Depends(get_store),
) -> Dict[str, Any]:
    return service.list_items(store, unread=unread, tag=tag)


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemIn, store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
    return service.add_item(store, payload.title, payload.url, payload.note, payload.tags)


@app.get("/items/{item_id}")
def get_item(item_id: str, store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
    return service.get_item(store, item_id)


@app.post("/items/{item_id}/tags")
def tag_item(
    item_id: str, payload: TagsIn, store: ReadingListStore = Depends(get_store)
) -> Dict[str, Any]:
    return service.tag_item(store, item_id, payload.tags)


@app.post("/items/{item_id}/read")
def mark_read(item_id: str, store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
    return service.mark_read_item(store, item_id)


@app.delete("/items/{item_id}")
def delete_item(item_id: str, store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
    return service.delete_item(store, item_id)


@app.get("/rank")
def rank(limit: Optional[int] = None, store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
    return service.rank_items(store, limit=limit)


@app.get("/summary")
def summary(store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
    return service.summarize_items(store)


@app.post("/chat", response_model=ChatOut)
def chat(payload: ChatIn, store: ReadingListStore = Depends(get_store)) -> Dict[str, Any]:
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

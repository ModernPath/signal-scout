"""Conversational layer for Example Agent, shared by CLI, API, and UI.

Two modes:
  - LLM mode: Gemini decides which tools to call (automatic function calling).
  - Offline mode: a small, deterministic command router. Used when no API key
    is set, when the caller asks for it, or if the LLM call fails.
"""

# No `from __future__ import annotations` here: google-genai checks tool arguments
# with isinstance(value, annotation), which fails when annotations are strings.

import functools
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import agent_llm
import example_service as service
from agent_env import AGENT_DIR
from example_core import extract_hashtags
from memory.memory import NoteStore

log = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 20
MAX_TOOL_CALLS_PER_TURN = 8

SYSTEM_PROMPT = """\
You are Example Agent, a concise assistant that manages the user's notes.

Rules:
- Use the tools to read or change notes. Never invent note contents or ids.
- Before deleting, make sure you have the exact note id (search first if needed).
- Keep answers short; list notes as "- title (#tags)".
"""

OFFLINE_HELP = (
    "I can help with notes. Try:\n"
    "- add Buy oat milk #shopping\n"
    "- find milk\n"
    "- list notes\n"
    "- delete note_ab12cd34ef\n"
    "- summarize"
)

History = List[Dict[str, str]]


@dataclass
class ChatResult:
    reply: str
    history: History = field(default_factory=list)
    used_llm: bool = False
    tools_used: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def chat_reply(
    store: NoteStore,
    message: str,
    *,
    history: Optional[History] = None,
    offline: bool = False,
) -> ChatResult:
    history = list(history or [])
    text = (message or "").strip()
    if not text:
        return ChatResult(reply="Please enter a message.", history=history)

    result = ChatResult(reply="")
    if not offline and agent_llm.llm_available():
        try:
            result.reply = _llm_reply(store, text, history, result.tools_used)
            result.used_llm = True
        except Exception:  # noqa: BLE001 — any LLM failure degrades to offline mode
            log.exception("LLM call failed; falling back to offline mode")
            result.tools_used.clear()

    if not result.used_llm:
        result.reply = offline_reply(store, text, result.tools_used)

    result.history = [
        *history,
        {"role": "user", "content": text},
        {"role": "assistant", "content": result.reply},
    ][-MAX_HISTORY_TURNS * 2 :]
    return result


# --------------------------------------------------------------------------- #
# LLM mode
# --------------------------------------------------------------------------- #


def build_tools(store: NoteStore, tools_used: List[str]) -> List[Callable[..., Dict[str, Any]]]:
    """Expose service functions to Gemini as plain Python callables.

    The SDK builds each function declaration from the signature and docstring,
    so these docstrings are the tool descriptions the model sees.
    """

    def tool(fn: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
        @functools.wraps(fn)
        def wrapper(**kwargs: Any) -> Dict[str, Any]:
            tools_used.append(fn.__name__)
            try:
                return fn(**kwargs)
            except (ValueError, LookupError, RuntimeError) as exc:
                return {"error": str(exc)}

        return wrapper

    @tool
    def add_note(title: str, body: str = "", tags: str = "") -> Dict[str, Any]:
        """Save a new note.

        Args:
          title: One-line title of the note.
          body: Optional longer text.
          tags: Optional comma-separated tags, e.g. "work, ideas".
        """
        return service.add_note(store, title, body, tags)

    @tool
    def search_notes(query: str = "", tag: str = "") -> Dict[str, Any]:
        """Find notes by keywords and/or tag. Leave both empty to list recent notes.

        Args:
          query: Space-separated keywords matched against title, tags, and body.
          tag: Only return notes with this tag.
        """
        return {"notes": service.find_notes(store, query, tag=tag or None)}

    @tool
    def delete_note(note_id: str) -> Dict[str, Any]:
        """Delete a note by its exact id (e.g. "note_ab12cd34ef").

        Args:
          note_id: The id returned by search_notes or add_note.
        """
        return service.delete_note(store, note_id)

    @tool
    def summarize_notes(tag: str = "") -> Dict[str, Any]:
        """Summarize notes, optionally only those with one tag. Delegates to a subagent.

        Args:
          tag: Optional tag to restrict the summary to.
        """
        return service.summarize_notes(store, tag=tag or None)

    return [add_note, search_notes, delete_note, summarize_notes]


def build_system_prompt(store: NoteStore) -> str:
    snapshot = service.overview(store)
    tags = ", ".join(f"#{t}" for t in snapshot["tags"]) or "none"
    return "\n\n".join(
        [
            SYSTEM_PROMPT,
            f"Current state: {snapshot['total']} note(s). Tags in use: {tags}.",
            "Skills:\n" + load_skills(),
        ]
    )


def load_skills() -> str:
    files = sorted((AGENT_DIR / "skills").glob("*.md"))
    return "\n\n---\n\n".join(f.read_text(encoding="utf-8") for f in files)


def _llm_reply(store: NoteStore, text: str, history: History, tools_used: List[str]) -> str:
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=build_system_prompt(store),
        tools=build_tools(store, tools_used),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=MAX_TOOL_CALLS_PER_TURN,
        ),
    )
    # Keep a reference: the SDK closes its HTTP connection when the client is garbage-collected.
    client = agent_llm.get_client()
    chat = client.chats.create(
        model=agent_llm.model_name(),
        config=config,
        history=[_to_content(turn) for turn in history[-MAX_HISTORY_TURNS * 2 :]],
    )
    response = chat.send_message(text)
    return (response.text or "").strip() or "Done."


def _to_content(turn: Dict[str, str]):
    from google.genai import types

    role = "user" if turn["role"] == "user" else "model"
    return types.Content(role=role, parts=[types.Part(text=turn["content"])])


# --------------------------------------------------------------------------- #
# Offline mode
# --------------------------------------------------------------------------- #


def offline_reply(store: NoteStore, text: str, tools_used: Optional[List[str]] = None) -> str:
    """Route simple commands to service functions with regexes. No LLM involved."""
    tools_used = tools_used if tools_used is not None else []
    for pattern, handler in _OFFLINE_ROUTES:
        match = pattern.match(text)
        if match:
            tools_used.append(handler.__name__.lstrip("_"))
            try:
                return handler(store, match)
            except (ValueError, LookupError, RuntimeError) as exc:
                return f"Sorry: {exc}"
    return OFFLINE_HELP


def _add_note(store: NoteStore, match: re.Match) -> str:
    title, tags = extract_hashtags(match.group("text"))
    note = service.add_note(store, title, tags=tags)
    return f"Saved {_format_note(note)} [{note['id']}]"


def _search_notes(store: NoteStore, match: re.Match) -> str:
    notes = service.find_notes(store, match.group("query"))
    if not notes:
        return f"No notes match '{match.group('query')}'."
    return "Found:\n" + "\n".join(_format_note(n) for n in notes)


def _list_notes(store: NoteStore, match: re.Match) -> str:
    notes = service.find_notes(store)
    if not notes:
        return "No notes yet. Try: add Buy oat milk #shopping"
    return "Your notes:\n" + "\n".join(_format_note(n) for n in notes)


def _delete_note(store: NoteStore, match: re.Match) -> str:
    note = service.delete_note(store, match.group("note_id"))
    return f"Deleted '{note['title']}'."


def _summarize_notes(store: NoteStore, match: re.Match) -> str:
    return service.summarize_notes(store, offline=True)["summary"]


def _format_note(note: Dict[str, Any]) -> str:
    tags = " ".join(f"#{t}" for t in note["tags"])
    return f"- {note['title']}" + (f" ({tags})" if tags else "")


_OFFLINE_ROUTES = [
    (re.compile(r"^(?:add|save|note)(?:\s+note)?[:\s]+(?P<text>.+)$", re.I), _add_note),
    (re.compile(r"^(?:list|show)(?:\s+(?:all|my))?\s+notes?\b", re.I), _list_notes),
    (re.compile(r"^(?:find|search)(?:\s+(?:for|notes?))*\s+(?P<query>.+)$", re.I), _search_notes),
    (re.compile(r"^(?:delete|remove)\s+(?:note\s+)?(?P<note_id>note_\w+)", re.I), _delete_note),
    (re.compile(r"^summari[sz]e\b", re.I), _summarize_notes),
]

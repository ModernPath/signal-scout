"""Conversational layer for Reading List, shared by CLI and API.

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
import reading_list_service as service
from agent_env import AGENT_DIR
from reading_list_core import extract_hashtags
from memory.memory import ReadingListStore

log = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 20
MAX_TOOL_CALLS_PER_TURN = 8

SYSTEM_PROMPT = """\
You are Reading List, a concise assistant that manages the user's reading list.

Rules:
- Use the tools to read or change items. Never invent item contents, URLs or ids.
- Only http(s) URLs are accepted. Before deleting, make sure you have the exact item id.
- Ranking and counts come from the tools; report them as returned.
- Keep answers short; list items as "- title (#tags)".
"""

OFFLINE_HELP = (
    "I can manage your reading list. Commands:\n"
    "- add Title https://example.com note: why #tag1 #tag2\n"
    "- list [unread]\n"
    "- tag item_ab12cd34ef tag1, tag2\n"
    "- rank\n"
    "- read item_ab12cd34ef\n"
    "- delete item_ab12cd34ef\n"
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
    store: ReadingListStore,
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


def build_tools(store: ReadingListStore, tools_used: List[str]) -> List[Callable[..., Dict[str, Any]]]:
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
    def add_item(title: str, url: str, note: str = "", tags: str = "") -> Dict[str, Any]:
        """Save a reading-list item.

        Args:
          title: Title of the item.
          url: http(s) URL.
          note: Optional note, at most 500 characters.
          tags: Optional comma-separated tags.
        """
        return service.add_item(store, title, url, note, tags)

    @tool
    def list_items(unread: bool = False, tag: str = "") -> Dict[str, Any]:
        """List items, newest first, optionally unread only and/or with one tag.

        Args:
          unread: Only items not yet read.
          tag: Only items with this tag.
        """
        return service.list_items(store, unread=unread, tag=tag or None)

    @tool
    def tag_item(item_id: str, tags: str) -> Dict[str, Any]:
        """Add comma-separated tags to an item by its exact id.

        Args:
          item_id: The id returned by list_items or add_item.
          tags: Comma-separated tags.
        """
        return service.tag_item(store, item_id, tags)

    @tool
    def rank_items() -> Dict[str, Any]:
        """Rank unread items to read next, with a reason for each."""
        return service.rank_items(store)

    @tool
    def mark_read_item(item_id: str) -> Dict[str, Any]:
        """Mark an item as read by its exact id.

        Args:
          item_id: The id returned by list_items or add_item.
        """
        return service.mark_read_item(store, item_id)

    @tool
    def delete_item(item_id: str) -> Dict[str, Any]:
        """Delete an item by its exact id.

        Args:
          item_id: The id returned by list_items or add_item.
        """
        return service.delete_item(store, item_id)

    @tool
    def summarize_items() -> Dict[str, Any]:
        """Counts of total, unread and read items plus per-tag counts."""
        return service.summarize_items(store)

    return [add_item, list_items, tag_item, rank_items, mark_read_item, delete_item, summarize_items]


def build_system_prompt(store: ReadingListStore) -> str:
    snapshot = service.summarize_items(store)
    tags = ", ".join(f"#{t}" for t in snapshot["tags"]) or "none"
    return "\n\n".join(
        [
            SYSTEM_PROMPT,
            f"Current state: {snapshot['total']} item(s), {snapshot['unread']} unread. Tags in use: {tags}.",
            "Skills:\n" + load_skills(),
        ]
    )


def load_skills() -> str:
    files = sorted((AGENT_DIR / "skills").glob("*.md"))
    return "\n\n---\n\n".join(f.read_text(encoding="utf-8") for f in files)


def _llm_reply(store: ReadingListStore, text: str, history: History, tools_used: List[str]) -> str:
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


def offline_reply(store: ReadingListStore, text: str, tools_used: Optional[List[str]] = None) -> str:
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


_URL = re.compile(r"https?://\S+", re.I)
_NOTE_PREFIX = re.compile(r"^note\s*:\s*", re.I)


def _add_item(store: ReadingListStore, match: re.Match) -> str:
    text = match.group("text").strip()
    found = _URL.search(text)
    if not found:
        raise ValueError("Please include an http(s) URL: add Title https://example.com note: why #tag")
    title = text[: found.start()].strip()
    rest, tags = extract_hashtags(text[found.end():])
    item = service.add_item(store, title, found.group(0), _NOTE_PREFIX.sub("", rest), tags)
    return f"Saved {_format_item(item)} [{item['id']}]"


def _list_items(store: ReadingListStore, match: re.Match) -> str:
    unread = bool(match.group("unread"))
    items = service.list_items(store, unread=unread)["items"]
    if not items:
        return "No unread items." if unread else "Your reading list is empty. Try: add Title https://example.com #tag"
    label = "Unread items" if unread else "Your items"
    return f"{label}:\n" + "\n".join(f"{_format_item(i)} [{i['id']}]" for i in items)


def _tag_item(store: ReadingListStore, match: re.Match) -> str:
    item = service.tag_item(store, match.group("item_id"), match.group("tags"))
    return f"Tagged {_format_item(item)}"


def _rank_items(store: ReadingListStore, match: re.Match) -> str:
    ranking = service.rank_items(store)["ranking"]
    if not ranking:
        return "Nothing unread to rank."
    return "Read next:\n" + "\n".join(
        f"{r['rank']}. {r['title']} [{r['id']}] — {r['reason']}" for r in ranking
    )


def _read_item(store: ReadingListStore, match: re.Match) -> str:
    item = service.mark_read_item(store, match.group("item_id"))
    return f"Marked '{item['title']}' as read."


def _delete_item(store: ReadingListStore, match: re.Match) -> str:
    item = service.delete_item(store, match.group("item_id"))
    return f"Deleted '{item['title']}'."


def _summarize_items(store: ReadingListStore, match: re.Match) -> str:
    s = service.summarize_items(store)
    line = f"{s['total']} item(s): {s['unread']} unread, {s['read']} read."
    if s["tags"]:
        line += " Tags: " + ", ".join(f"#{t} ({c})" for t, c in s["tags"].items()) + "."
    return line


def _format_item(item: Dict[str, Any]) -> str:
    tags = " ".join(f"#{t}" for t in item["tags"])
    return f"- {item['title']}" + (f" ({tags})" if tags else "")


_OFFLINE_ROUTES = [
    (re.compile(r"^add\s+(?P<text>.+)$", re.I), _add_item),
    (re.compile(r"^list(?:\s+(?P<unread>unread))?\s*$", re.I), _list_items),
    (re.compile(r"^tag\s+(?P<item_id>item_\w+)\s+(?P<tags>.+)$", re.I), _tag_item),
    (re.compile(r"^rank\b", re.I), _rank_items),
    (re.compile(r"^read\s+(?P<item_id>item_\w+)", re.I), _read_item),
    (re.compile(r"^(?:delete|remove)\s+(?P<item_id>item_\w+)", re.I), _delete_item),
    (re.compile(r"^summari[sz]e\b", re.I), _summarize_items),
]

# Reading list agent — technical spec

**Behavior:** [Task spec](task_spec.md)

## Process and ownership

Build `agents/reading-list/` as a domain-specific adaptation of
[`agents/example-agent/`](../../../agents/example-agent/), keeping its
dependency direction:

```text
CLI / API chat ──> chat ──> service ──> pure core
                     │          └──────> memory
                     └── model-callable wrappers around service functions
Tool CLIs ────────────────────────────────> service
```

Replace the note domain with the reading-list domain in every module, rename
each `example_*` module and `EXAMPLE_AGENT_*` setting to the names below, and
delete `subagents/` and `ui/` (the brief requests no subagents and no UI;
`reading_list_service` therefore makes no subprocess calls and has no
`SubagentError` path). All chat model tools, offline routes, tool CLIs, and
API routes resolve to the same `reading_list_service` use cases.
`agent_env.py` loads `.env`/`.env.local` only from the agent folder plus the
process environment and never walks parent directories.

## Modules and environment

| Name | Purpose |
|---|---|
| `reading_list_agent.py` | CLI entry point: `--chat`, single query, `--offline` (mirrors `example_agent.py`) |
| `reading_list_core.py` | Pure domain logic: `Item` model, title/URL/note validation, tag normalization, `read_next` ranking, tag summary. No file I/O, no network, no LLM |
| `reading_list_service.py` | Use cases shared by every surface: `add_item`, `list_items`, `get_item`, `tag_item`, `mark_read_item`, `delete_item`, `rank_items`, `summarize_items` |
| `reading_list_chat.py` | Chat layer: model-callable tool wrappers and the deterministic offline command router |
| `agent_env.py`, `agent_llm.py`, `agent_cli.py` | Kept from the reference: scoped env loading, Gemini key lookup/offline switch, single JSON envelope for tool and memory CLIs |
| `memory/memory.py` | `ReadingListStore`: JSON-file persistence (`items.json`, atomic temp-file + rename writes) plus an inspection CLI (`list`, `get --id`, `delete --id`, `stats`) |
| `memory/item_schema.json` | Data schema for one item record |
| `tools/add_item.py`, `tools/list_items.py`, `tools/tag_item.py`, `tools/mark_read_item.py`, `tools/delete_item.py`, `tools/rank_items.py`, `tools/summarize_items.py` | One CLI per action, all using `agent_cli.run_and_print` |
| `skills/*.md` | Kebab-case skill Markdown loaded into the chat system prompt (item management, read-next ranking, list and summary) |
| `api/main.py` | Local FastAPI, loopback-only, `API_PORT` default 8013 |
| `tests/` | pytest: core, memory+service, chat, tool CLIs, API — all offline, temp data dir |

Environment variables (upper-snake prefix of the agent name):

| Variable | Purpose |
|---|---|
| `READING_LIST_OFFLINE=1` | Force offline mode even when a provider key is set |
| `READING_LIST_DATA_DIR` | Store `items.json` somewhere other than `memory/data/` |
| `READING_LIST_MODEL` | Model override (reference default), LLM chat mode only |
| `GEMINI_API_KEY` / `GOOGLE_AI_STUDIO_KEY` | Optional; enable LLM chat mode, otherwise offline |
| `API_PORT` | API port (default 8013) |

## Memory

One record per item in a single JSON array at `memory/data/items.json`
(or `$READING_LIST_DATA_DIR/items.json`), written atomically (temp file +
rename) as in the reference:

```json
{
  "id": "item_a1b2c3d4e5",
  "title": "text, 1–120 chars, required, stripped",
  "url": "text, required, must start with http:// or https:// — syntactic check only, never fetched",
  "note": "text, 0–500 chars, optional (default \"\")",
  "tags": ["lowercase slugs, deduplicated, insertion order kept"],
  "added_at": "ISO-8601 UTC, seconds precision, set on add",
  "read_at": "ISO-8601 UTC, seconds precision, or null until marked read"
}
```

- `id` is `item_` + 10 hex chars, assigned once at creation (deterministic
  format, random value), like the reference's `note_` ids.
- Tag normalization reuses the reference rule: lowercase, non-`[a-z0-9-]`
  runs become `-`, surrounding dashes trimmed, empties dropped, duplicates
  removed keeping first occurrence (`" Dev ,DEV, #dev"` → `["dev"]`).
- Retention: records persist until `delete_item` removes them from the array;
  no expiry, no history, no tombstones. Duplicates are allowed (each add is a
  new item; there is no deduplication rule in the brief).
- `NotFoundError(LookupError)` for unknown ids; `ValueError` for bad input —
  the reference's error vocabulary.

## Ranking (pure core)

`read_next(items, limit=5)`:

```text
unread  = [i for i in items if i.read_at is None]
usage   = Counter(tag for item in items for tag in item.tags)   # whole list, read + unread
boost(i) = sum(usage[t] for t in i.tags)
order   = unread sorted by (-boost(i), added_at, id)
```

- "Most used tags" means the operator's usage across the whole list — every
  item carrying a tag counts once for that tag, including the item itself,
  read or unread.
- Each ranked entry is the item dict plus `rank` (1-based), `tag_boost`, and
  `reason`, a deterministic string:
  `"<tag-part>; added <YYYY-MM-DD>"` where `<tag-part>` is
  `` "`dev` (5), `ai` (2) contribute 7" `` (tags ordered by usage desc, then
  name) when `tag_boost > 0`, else `"no tag boost"`.
- No model call, no clock reads of the wall time, no randomness: the same
  stored state always yields the same order, boost, and reasons.

`summarize(items)` returns `{"total": n, "unread": u, "read": r,
"tags": {tag: count, …}}` over the whole list.

## Tool JSON contracts

Each tool CLI runs one service use case through `agent_cli.run_and_print` and
prints exactly one JSON object on stdout: `{"status": "success", "data": …}`
with exit 0, or `{"status": "error", "error": <message>}` with exit 1 for
`ValueError`/`LookupError`.

| Tool | Arguments | `data` on success |
|---|---|---|
| `tools/add_item.py` | `--title --url [--note] [--tags "a,b"]` | created item |
| `tools/list_items.py` | `[--tag T] [--unread] [--limit N]` | `{"items": [item, …]}` newest by `added_at` first |
| `tools/tag_item.py` | `--id item_… --tags "a,b"` | updated item |
| `tools/mark_read_item.py` | `--id item_…` | item with `read_at` set |
| `tools/delete_item.py` | `--id item_…` | deleted item |
| `tools/rank_items.py` | `[--limit N]` | `{"ranking": [{item fields, "rank", "tag_boost", "reason"}, …]}` |
| `tools/summarize_items.py` | — | `{"total", "unread", "read", "tags"}` |

There is no subagent contract: the brief names none and the service performs
no subprocess launches.

## Chat

`reading_list_chat.py` mirrors the reference: bounded history, a per-turn cap
on model tool calls, skills Markdown loaded into the system prompt, and
`build_tools()` exposing plain Python callables that wrap the service
functions (`add_item`, `list_items`, `tag_item`, `mark_read_item`,
`delete_item`, `rank_items`, `summarize_items`) so the LLM and every other
surface share one implementation. With no key, with `--offline` or
`READING_LIST_OFFLINE=1`, or on any provider failure, the deterministic
offline router (case-insensitive regexes) handles:

| Command | Service action |
|---|---|
| `add <title> <url> [note: <text>] [#tag …]` | `add_item`; the URL is the first token matching `https?://\S+`, the text before it (joined) is the title, a `note:` token starts the note (consuming following non-`#` tokens), `#tag` tokens are tags |
| `list [unread]` | `list_items(unread=…)` |
| `tag <item_id> <tags>` | `tag_item` |
| `rank [n]` | `rank_items(limit=n)` |
| `summarize` | `summarize_items` |
| `read <item_id>` | `mark_read_item` |
| `delete <item_id>` | `delete_item` |

An unmatched command returns help text listing these commands — never an
exception. `read` and `delete` are in the router in addition to the five
commands the brief names (add, list, tag, rank, summarize) because the memory
contract requires `read_at` to be set and items to be deletable by the
operator through the same surfaces.

## API

`api/main.py` keeps the reference shape (FastAPI, `get_store` dependency
overridable in tests, exception handlers, `uvicorn` bound to `127.0.0.1`). It
drops wildcard CORS (there is no separate origin: the brief asks for no UI)
and the `SubagentError` → 502 handler (there are no subagents).

| Route | Service action |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /items?tag=&unread=&limit=` | `list_items` |
| `POST /items` (201) | `add_item` |
| `GET /items/{item_id}` | `get_item` |
| `POST /items/{item_id}/tags` | `tag_item` |
| `POST /items/{item_id}/read` | `mark_read_item` |
| `DELETE /items/{item_id}` | `delete_item` |
| `GET /rank?limit=` | `rank_items` |
| `GET /summary` | `summarize_items` |
| `POST /chat` | `reading_list_chat.chat_reply` |

`ValueError` → 400, `LookupError`/`NotFoundError` → 404. `GET /rank` and
`GET /summary` are top-level routes to avoid shadowing `GET /items/{item_id}`.
Request bodies validate the same limits as the core (title 1–120, URL
http(s), note ≤ 500).

## Safety and limits

- No URL or page fetch anywhere: `url` is validated syntactically, stored, and
  printed, and nothing in the agent resolves, requests, or caches page
  content.
- The only network path is the optional Gemini chat provider; every offline
  path must work with provider keys removed from the environment.
- No secrets in code, `.env.example`, tests, or data files; live records stay
  in the gitignored data dir.
- Model output is never persisted as an item: items are created only through
  the validated service use cases.
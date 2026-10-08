# Reading list agent — task spec

**Technical design:** [Technical spec](technical_spec.md)
**Verification:** [Test plan](test_plan.md)
**Derived from:** factory brief [`001-reading-list.md`](../../../factory/briefs/001-reading-list.md)
**Status:** Specified by the factory spec stage on 2026-10-08; not yet implemented.

## Outcome

`agents/reading-list/` is a complete, fully offline-capable local agent: one
operator keeps a reading list of article links with a short note and tags, and
asks which items to read next. All state is a single JSON file in the agent's
own data directory; no database, UI, subagent, or product integration is
involved, and no page content is ever fetched.

## Contract

| | |
|---|---|
| Purpose | A single local operator keeps a reading list of article links with a short note and tags, and asks which items to read next. |
| Inputs | Article title, URL, optional note and tags, typed in chat or passed to a tool CLI (and the local API). |
| Outputs | The stored list, a "read next" ranking with the reason for each rank, and a summary count by tag. |
| Permissions | Reads and writes only its own data directory. Never fetches a URL, never calls the network except the optional model provider for chat. |
| Side effects | None outside its data directory. |
| Offline behavior | Chat commands (add, list, tag, rank, summarize) and every tool CLI work with no provider key. Ranking is deterministic: oldest unread first, boosted by the operator's most used tags. |
| Memory records | One JSON record per item: `id`, `title`, `url`, `note`, `tags`, `added_at`, `read_at`, in the agent data directory (`memory/data/items.json`, or `$READING_LIST_DATA_DIR`). |
| Retention | Kept until the operator deletes the item; deleting clears it from the file. No expiry, no tombstones, no other deletion path. |
| Surfaces | Chat CLI (`reading_list_agent.py` with `--chat`, one-shot query, `--offline`), JSON tool CLIs in `tools/`, local FastAPI in `api/main.py`. No UI, no subagents. |

## In scope

- Item lifecycle as shared service use cases reachable from every surface: add (required title and http(s) URL, optional note and tags), list (all/unread, optional tag filter), tag (merge tags into an item), mark read, delete.
- Deterministic "read next" ranking with a per-rank reason, and a summary of counts by tag (plus total/unread/read).
- JSON-file memory with the record schema above, atomic writes, `READING_LIST_DATA_DIR` override, and an inspection CLI (`memory/memory.py`).
- Offline chat command router and model-callable tools that wrap the same service functions; provider absence or failure degrades to offline behavior.
- Local loopback-only FastAPI with the reference agent's error mapping (bad input → 400, missing item → 404).

## Boundaries

The agent never fetches or summarizes page content, and has no accounts,
sharing, authentication, UI, publishing, or subagents. It makes no network call
except the optional model provider for chat. The API binds to `127.0.0.1` and
has no authentication and no CORS. All writes go to the agent's own data
directory. URL handling is syntactic only (scheme check); nothing is crawled,
fetched, or cached.

## Acceptance criteria

1. Adding an item through the core/service, offline chat, `tools/add_item.py`, or `POST /items` stores a record with a stable `item_*` id, required title, required http(s) URL, optional note (max 500 chars) and normalized lowercase slug tags (deduplicated, order preserved), `added_at` set, `read_at` null. Missing title, non-http(s) URL, or an over-long/blank-required field is rejected as bad input on every surface (`ValueError` → 400 / error envelope / chat error line, never a store write).
2. Listing through the service, `list`/`list unread` in offline chat, `tools/list_items.py`, or `GET /items` returns stored items (id, title, url, note, tags, added_at, read_at) newest by `added_at` first, with the unread-only and tag filters; an empty list is a clear empty result, not an error.
3. The read-next ranking (offline chat `rank`, `tools/rank_items.py`, `GET /rank`) returns only unread items ordered by descending tag boost — the sum, over the item's tags, of each tag's usage count across the whole list — with ties broken by oldest `added_at`, then id. Every entry carries the item fields, a 1-based `rank`, its `tag_boost`, and a deterministic `reason` naming the contributing tags with their counts (or stating there is no tag boost) and the added date; identical stored state yields identical order and reasons.
4. Tagging an item (chat `tag <id> <tags>`, `tools/tag_item.py`, `POST /items/{id}/tags`) merges the new tags into the item, deduplicates case-insensitively, and is visible on every surface; an unknown item id is a not-found error, and a tag list that normalizes to no valid tags is bad input.
5. Marking an item read (chat `read <id>`, `tools/mark_read_item.py`, `POST /items/{id}/read`) sets `read_at` on first call and keeps that value on repeated calls; the item then disappears from the read-next ranking; an unknown id is not-found.
6. Deleting an item (chat `delete <id>`, `tools/delete_item.py`, `DELETE /items/{id}`) removes the record from `items.json`; the item is then not-found on get/list/rank, and retention is exactly "until deleted" — no expiry, no other removal.
7. Summarizing (offline chat `summarize`, `tools/summarize_items.py`, `GET /summary`) returns total, unread, and read counts plus per-tag counts over the whole list.
8. With no provider key, offline chat routes `add`, `list`, `tag`, `rank`, `summarize` (and `read`, `delete`, needed by the memory contract) to the same service actions as the tools and API; the replies reflect stored state; an unrecognized command returns help text listing the supported commands, never a traceback.
9. Every tool CLI prints exactly one JSON object on stdout: `{"status": "success", "data": …}` with exit code 0 on success, and `{"status": "error", "error": …}` with exit code 1 for bad input or an unknown id.
10. The API binds to `127.0.0.1` only (default port 8013, `API_PORT` override), returns JSON, and maps `ValueError` → 400 and `LookupError`/`NotFoundError` → 404 while agreeing with service state seen by the tools and chat.
11. `READING_LIST_DATA_DIR` redirects all reads and writes to the given directory; with `READING_LIST_OFFLINE=1` or no provider key, every surface works with no network call; `agent_env.py` loads environment only from the agent folder, never from parent directories.